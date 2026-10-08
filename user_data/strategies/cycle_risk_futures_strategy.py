"""CycleRisk 合约回测版：USDT逐仓、1倍做多、BTC连续两天弱势退出。

历史资金费目录由 cycle_risk_funding_data_dir 指定，读取下载器冻结的结算率与标记价。
保持已验证回测的成交时点与账户估值；本入口不支持实时模拟盘或实盘。
现货正式策略仍为 cycle_risk_strategy.py。
"""
from datetime import datetime
from pathlib import Path
import math
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.data.history import load_pair_history
from freqtrade.enums import CandleType, RunMode
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, timeframe_to_prev_date

class BtcCoinGuardCycleRiskFuturesStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1d"
    startup_candle_count = 60
    process_only_new_candles = True
    minimal_roi = {"0": 100}
    stoploss = -0.99
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    position_adjustment_enable = True
    max_entry_position_adjustment = -1
    BTC_PAIR = "BTC/USDT:USDT"
    TREND_MA_DAYS = 150
    RECOVERY_EMA_DAYS = 10
    TREND_EXIT_DAYS = 2
    COIN_EXIT_DAYS = 2
    RECOVERY_COOLDOWN_DAYS = 14
    REARM_COOLDOWN_DAYS = 14
    STAGE_KEY = 'equity_risk_filled_fraction'
    ORDER_PREFIX = 'equity_risk_target_'

    def __init__(self, config):
        if config.get('runmode') in (RunMode.LIVE, RunMode.DRY_RUN, 'live', 'dry_run'):
            raise ValueError('此合约入口依赖冻结资金费数据，仅支持回测，尚未接入实时资金费账本。')
        if config.get('trading_mode') != 'futures' or config.get('margin_mode') != 'isolated':
            raise ValueError('合约版需要 trading_mode=futures、margin_mode=isolated。')
        if not config.get('cycle_risk_funding_data_dir'):
            raise ValueError('请设置 cycle_risk_funding_data_dir 为历史资金费 raw 目录。')
        self._futures_funding_prefix = {}
        super().__init__(config)
        self._history_cache = {}
        self._risk_fraction = 1.0
        self._risk_peak = None
        self._risk_candle = None
        self._pending_initial_fraction = {}
        self.risk_trace = []
        self._previous_bull = False
        self._last_rearm_candle = None

    def informative_pairs(self):
        # 周线不参与正式版决策，仅订阅BTC日线。
        return [(self.BTC_PAIR,self.timeframe)]

    def _history(self, pair: str, timeframe: str) -> DataFrame:
        if self.dp.runmode in (RunMode.DRY_RUN, RunMode.LIVE):
            return self.dp.get_pair_dataframe(pair, timeframe)
        key = (pair, timeframe)
        if key not in self._history_cache:
            self._history_cache[key] = load_pair_history(
                pair=pair, timeframe=timeframe,
                datadir=Path(self.config["datadir"]),
                data_format=self.config.get("dataformat_ohlcv"),
                candle_type=CandleType.FUTURES,
            )
        return self._history_cache[key].copy()

    def _last_closed_row(self, pair: str, current_time: datetime) -> pd.Series | None:
        """正在执行的 K 线之前最后一根完整日线（跟信号在下一根开盘执行的时点一致）。"""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        rows = dataframe.loc[dataframe["date"] < self._executing_candle_start(current_time)]
        return None if rows.empty else rows.iloc[-1]

    def _slots(self) -> int:
        slots = self.config.get("max_open_trades", -1)
        if slots is None or slots <= 0 or math.isinf(slots):
            return max(1, len(self.dp.current_whitelist()))
        return int(slots)

    def _executing_candle_start(self, current_time: datetime) -> datetime:
        # 回测里 current_time 是正在执行那根 K 线的开盘时间，实盘里是这根 K 线内的某个时刻，
        # 两者向下取整都得到同一根 K 线的开盘时间。
        return timeframe_to_prev_date(self.timeframe, current_time)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if dataframe.empty:
            return dataframe
        coin = self._history(metadata['pair'],self.timeframe)[['date','close']].copy()
        coin['ema20'] = coin.close.ewm(span=20,adjust=False).mean()
        coin['ema50'] = coin.close.ewm(span=50,adjust=False).mean()
        coin['own_candles'] = np.arange(1,len(coin)+1)
        ma = coin.close.rolling(self.TREND_MA_DAYS).mean()
        ema = coin.close.ewm(span=self.RECOVERY_EMA_DAYS,adjust=False).mean()
        recovery = (coin.close>ema) & (ema>ema.shift(1))
        valid = ma.notna()
        coin['coin_risk_on'] = valid & ((coin.close>ma) | recovery)
        weak = valid & (coin.close<ma) & ~recovery
        coin['coin_risk_off'] = weak.rolling(self.COIN_EXIT_DAYS).sum()==self.COIN_EXIT_DAYS
        frame = dataframe.merge(coin[['date','ema20','ema50','own_candles','coin_risk_on','coin_risk_off']],on='date',how='left')
        btc = self._history(self.BTC_PAIR,self.timeframe)[['date','close']].copy()
        ma = btc.close.rolling(self.TREND_MA_DAYS).mean()
        ema = btc.close.ewm(span=self.RECOVERY_EMA_DAYS,adjust=False).mean()
        recovery = (btc.close>ema) & (ema>ema.shift(1))
        valid = ma.notna()
        btc['exposure_entry'] = valid & ((btc.close>ma) | recovery)
        weak = valid & (btc.close<ma) & ~recovery
        btc['exposure_exit'] = weak.rolling(self.TREND_EXIT_DAYS).sum()==self.TREND_EXIT_DAYS
        btc['cooldown_btc_strict'] = btc.close>ma
        return frame.merge(btc[['date','exposure_entry','exposure_exit','cooldown_btc_strict']],on='date',how='left')

    def populate_entry_trend(self, dataframe, metadata):
        allowed = ((dataframe.own_candles>self.startup_candle_count)
                   & (dataframe.volume>0) & dataframe.exposure_entry.fillna(False))
        dataframe.loc[allowed,['enter_long','enter_tag']] = [1,'trend_full_exposure']
        dataframe.loc[allowed & dataframe.cooldown_btc_strict.fillna(False),'enter_tag'] = 'phase_full_entry'
        dataframe.loc[allowed & ~dataframe.cooldown_btc_strict.fillna(False),'enter_tag'] = 'phase_reduced_entry'
        dataframe.loc[~dataframe.coin_risk_on.fillna(False),'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        return dataframe

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair,current_time)
        if row is None:
            return None
        signal = row.get('exposure_exit',False)
        if pd.notna(signal) and bool(signal):
            return 'trend_to_cash'
        signal = row.get('coin_risk_off',False)
        return 'coin_trend_to_cash' if pd.notna(signal) and bool(signal) else None

    def confirm_trade_entry(
        self, pair: str, current_time: datetime, **kwargs,
    ) -> bool:
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return False
        strict = row.get("cooldown_btc_strict", False)
        if pd.notna(strict) and bool(strict):
            return True
        closed = [t for t in Trade.get_trades_proxy(pair=pair, is_open=False)
                  if t.close_date_utc is not None and t.close_date_utc <= current_time]
        if not closed:
            return True
        latest = max(t.close_date_utc for t in closed)
        return (current_time - latest).total_seconds() >= self.RECOVERY_COOLDOWN_DAYS * 86400

    def _pair_budget(self, pair):
        # 固定初始本金，不能将未平仓交易的部分兑现利润重复计入本金。
        if not hasattr(self, '_phase_initial_capital'):
            capital = float(self.wallets.get_starting_balance())
            if 'available_capital' not in self.config:
                capital -= sum((float(t.realized_profit or 0.0) for t in Trade.get_trades_proxy(is_open=True))) * float(self.config.get('tradable_balance_ratio', 1.0))
            self._phase_initial_capital = max(0.0, capital)
        profits = sum((float(t.close_profit_abs or 0.0) for t in Trade.get_trades_proxy(pair=pair, is_open=False)))
        return max(0.0, self._phase_initial_capital / self._slots() + profits)

    @staticmethod
    def next_fraction(previous, drawdown):
        if drawdown >= .35:
            return .5
        if previous == 1.0:
            return .75 if drawdown >= .25 else 1.0
        if drawdown <= .20:
            return 1.0
        if previous == .5:
            return .75 if drawdown <= .30 else .5
        return .75

    def _closed_price(self, pair, current_time):
        history = self._history(pair, self.timeframe)
        closed = history.loc[history['date'] < self._executing_candle_start(current_time)]
        return None if closed.empty else float(closed.iloc[-1]['close'])

    def _futures_funding_total(self, pair, when):
        """累计每单位持仓资金费成本；结算时点的记录包含在内。"""
        if pair not in self._futures_funding_prefix:
            import json
            path = Path(self.config['cycle_risk_funding_data_dir']) / (pair.split('/')[0] + '.json')
            records = json.loads(path.read_text())['funding']['rows']
            if not records:
                raise ValueError(f'{pair} 缺少真实资金费记录，不能按零费率回测。')
            frame = pd.DataFrame(records)
            dates = pd.DatetimeIndex(pd.to_datetime(frame.fundingTime, unit='ms', utc=True)).as_unit('ns')
            series = pd.Series((frame.fundingRate.astype(float) * frame.markPrice.astype(float)).to_numpy(), index=dates).sort_index()
            if series.index.has_duplicates:
                raise ValueError(f'{pair} 资金费结算时点重复。')
            self._futures_funding_prefix[pair] = series.cumsum()
        prefix = self._futures_funding_prefix[pair]
        count = prefix.index.searchsorted(pd.Timestamp(when), side='right')
        return float(prefix.iloc[count - 1]) if count else 0.0

    def _futures_equity(self, current_time):
        """按实际订单重建上一完整日净值，避免将保证金再加一遍市值。"""
        cutoff = pd.Timestamp(current_time).floor('D') - pd.Timedelta(nanoseconds=1)
        cash = float(self.config['dry_run_wallet'])
        quantities = {}
        for trade in Trade.get_trades_proxy(is_open=True) + Trade.get_trades_proxy(is_open=False):
            pair = trade.pair
            for order in trade.orders:
                if order.ft_is_open or not order.filled or order.order_filled_date is None:
                    continue
                when = pd.Timestamp(order.order_filled_utc)
                if when > cutoff:
                    continue
                qty = float(order.safe_amount_after_fee)
                rate = float(order.safe_price)
                entry = order.ft_order_side == trade.entry_side
                delta = qty if entry else -qty
                cash += -qty * rate * (1 + trade.fee_open) if entry else qty * rate * (1 - trade.fee_close)
                cash -= delta * (self._futures_funding_total(pair, cutoff) - self._futures_funding_total(pair, when))
                quantities[pair] = quantities.get(pair, 0.0) + delta
        for pair, qty in quantities.items():
            if abs(qty) > 1e-8:
                price = self._closed_price(pair, current_time)
                if price is None:
                    raise ValueError(f'{pair} 缺少上一完整日价格。')
                cash += qty * price
        return cash

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side, **kwargs):
        return 1.0

    def _update_equity_risk(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return

        try:
            equity = self._futures_equity(current_time)
        except Exception:
            import traceback
            traceback.print_exc()
            raise SystemExit(2)
        if self._risk_peak is None:
            self._risk_peak = float(self.wallets.get_starting_balance())
        self._risk_peak = max(self._risk_peak, equity)
        dd = max(0.0, 1 - equity / self._risk_peak) if self._risk_peak > 0 else 0.0
        self._risk_fraction = self.next_fraction(self._risk_fraction, dd)
        self._risk_candle = candle
        self.risk_trace.append({'execution_date':str(candle), 'prior_closed_equity':equity,
                                'peak':self._risk_peak, 'drawdown':dd,
                                'risk_fraction':self._risk_fraction})

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fee = .001 if self.config.get('fee') is None else float(self.config['fee'])
        amount = min(self._risk_fraction * self._pair_budget(pair) / (1 + fee), max_stake)
        if amount < (min_stake or 0.0):
            return 0.0
        self._pending_initial_fraction[pair] = self._risk_fraction
        return amount

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._risk_fraction
        previous = trade.get_custom_data(self.STAGE_KEY)
        if previous is None:
            previous = 1.0
        if desired == previous:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        cash = max(0.0, self._pair_budget(trade.pair) + float(trade.realized_profit or 0.0)
                   - float(trade.stake_amount) * (1 + fee))
        delta = desired * (cash + value) - value
        minimum = max(1.0, min_stake or 0.0)
        tag = self.ORDER_PREFIX + str(desired)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, tag) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, tag)
        return None

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        tag = order.ft_order_tag or ''
        if tag.startswith(self.ORDER_PREFIX):
            trade.set_custom_data(self.STAGE_KEY, float(tag[len(self.ORDER_PREFIX):]))
        elif order.ft_order_side == trade.entry_side and trade.get_custom_data(self.STAGE_KEY) is None:
            trade.set_custom_data(self.STAGE_KEY, self._pending_initial_fraction.pop(pair, 1.0))

    def _btc_bull_confirmed(self, current_time):
        history = self._history(self.BTC_PAIR, self.timeframe)
        close = history.loc[history['date'] < self._executing_candle_start(current_time), 'close']
        if len(close) < 201:
            return False
        return bool((close.iloc[-2:] > close.rolling(200).mean().iloc[-2:]).all())

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        self._update_equity_risk(current_time, **kwargs)
        if self._risk_candle != candle:
            return
        bull = self._btc_bull_confirmed(current_time)
        allowed = (self._last_rearm_candle is None or
                   (candle-self._last_rearm_candle).days >= self.REARM_COOLDOWN_DAYS)
        reset = bull and not self._previous_bull and allowed and self._risk_fraction < 1.0
        if reset:
            self._risk_peak = self.risk_trace[-1]['prior_closed_equity']
            self._risk_fraction = 1.0
            self._last_rearm_candle = candle
            self.risk_trace[-1].update(peak=self._risk_peak,drawdown=0.0,risk_fraction=1.0)
        self.risk_trace[-1]['risk_epoch_reset'] = bool(reset)
        self._previous_bull = bool(bull)
