"""正式版 CycleRisk：直接继承 IStrategy，保留原有交易规则。

日线只做多；BTC与个币MA150/EMA10共同允许入场；BTC弱势一日退出，
个币弱势两日退出；BTC未站上MA150时，同币平仓后等待14日。
按币独立复利预算，账户回撤25%/35%降至75%/50%；恢复规则不变。
BTC新一轮连续两日站上MA200时，可重启内部风险峰值，间隔至少14日。
不保留永久核心仓、不熊市分档囤币、不使用周线仓位。
账户风险状态尚未持久化；每笔交易的实际成交风险档位保存在交易数据。
旧继承链与研究入口见 user_data/archive/cycle_risk_flatten_20261007。
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

class BtcCoinGuardCycleRiskStrategy(IStrategy):
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
    BTC_PAIR = "BTC/USDT"
    TREND_MA_DAYS = 150
    RECOVERY_EMA_DAYS = 10
    TREND_EXIT_DAYS = 1
    COIN_EXIT_DAYS = 2
    RECOVERY_COOLDOWN_DAYS = 14
    REARM_COOLDOWN_DAYS = 14
    STAGE_KEY = 'equity_risk_filled_fraction'
    ORDER_PREFIX = 'equity_risk_target_'

    def __init__(self, config):
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
                candle_type=CandleType.SPOT,
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

    def _update_equity_risk(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        self.wallets.update()
        equity = float(self.wallets.get_free(self.config['stake_currency']))
        equity += float(self.wallets.get_used(self.config['stake_currency']))
        for trade in Trade.get_trades_proxy(is_open=True):
            price = self._closed_price(trade.pair, current_time)
            if price is None:
                return
            # 模拟钱包在退出交易时结算剩余的开仓手续费。
            # 先扣除尚未结算的费用，使权益与实际成交现金账本一致。
            if self.config.get('dry_run', False):
                equity -= float(trade.stake_amount) * float(trade.fee_open)
            equity += float(trade.amount) * price
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
