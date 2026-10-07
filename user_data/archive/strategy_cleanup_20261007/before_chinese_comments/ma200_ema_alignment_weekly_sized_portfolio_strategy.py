"""MA200+EMA 趋势策略（多币组合版）。2026-09-23 提升为正式策略；单币原版保留在
ma200_ema_alignment_weekly_sized_strategy.py。

规则：进出场信号和周线 100%/50% 仓位规则跟原版完全一样，只改了仓位算法，让多个币
能共用一个钱包：
- 每个币一个槽位 = 账户市值 / max_open_trades。开仓金额 = 周线目标（1.0 或 0.5）x 槽位，
  不超过可用现金。
- 持仓期间只在周线目标翻转时调仓：1.0 -> 0.5 卖掉一半，0.5 -> 1.0 补足到一个槽位
  （不超过可用现金）。价格涨跌造成的偏离不做再平衡，赚钱的仓位不会因为涨多了被砍。
- 上次应用的周线目标存在 trade custom data 里，bot 重启后不会丢。

止损：-99%（等于不设），风控靠退出规则。止损类实验全部否决
（../validation/ma200_btc_regime_20260923/REVIEW_20260923.md 第七节）。

使用场景：
- 多个币共用一个账户，max_open_trades = 币的数量（每个币一个槽位）。
- 目标是用"币的数量"提高交易频率、降低整体回撤，单币规则不变。
- 只跑一个币时要把 max_open_trades 设成 1，否则只会动用 1/max_open_trades 的资金。

验证结论（../validation/ma200_weekly_sized_portfolio_20260923/REPORT.md）：
- 10 个币（BTC ETH BNB LINK XRP UNI ZEC DOGE SOL ARB）共用 1000 USDT、10 个槽位：
  组合每年 17～28 笔交易（单币每年约 2 笔）；五个区间的市值回撤 -10%～-41%，
  等权买入持有是 -50%～-84%。
- 每个区间去掉贡献最高和最低的币后，全周期、2024 年至今、熊市、牛熊交替 4 个区间
  仍然收益和回撤都赢过等权持有。
- 小组合效果有限：BTC+ETH+SOL、BTC+ETH+BNB+XRP 回撤 5/5 更小，但收益只有 2/5 跑赢持有，
  每年只有约 3～14 笔交易。组合的优势主要来自币的数量多、彼此相关性低。
- max_open_trades = 1 时结果跟原版很接近（交易笔数相同）；唯一区别是原版在 50% 状态下
  会每天把仓位拉回正好 50%，本版减半一次后就让它自由浮动。
- 时点币池（每年 1 月 1 日按成交额取前 10，含 LUNA、EOS 等，逐年复利，2019-01 ->
  2026-09，见 ../validation/ma200_btc_regime_20260923/REVIEW_20260923.md 第六节）：
  +525%，等权持有 +904%；最大回撤 -59.7%，持有 -85.3%。收益和回撤都不如 BTC 定牛熊版
  （+771% / -59.6%），多币账户优先用那个版本。

已知局限：
- 牛市（2020-10 -> 2021-11）去掉 DOGE 后，组合 +580%，持有 +1687%：单币"单边牛市
  跑输持有"的问题没有被解决，完整组合只是在有超级大赢家时把它盖住了。
- 资金利用率偏低，平均只有约 30%～60% 的资金在场内。
- 赢家不减仓，会集中到单个币：2025-11-17 ZEC 占账户 68%，随后回落造成 -37.6% 回撤。
  单币归零时账户损失 = 它的占比，单币仓位上限还没有实现。
- 不看 BTC 牛熊，BTC 转熊后仍可能持有小币：OM 2025-04-13 崩盘时持有，单笔 -91%，
  账户 -8.4%（那时刚重新进场、仓位只有一个槽位，否则约 -25%）。
- 手挑币池有幸存者偏差；时点币池已测（见上），全部是样本内结果，还没有 dry-run。
"""

from __future__ import annotations

import math
from datetime import datetime

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, timeframe_to_prev_date
from pandas import DataFrame


class Ma200EmaAlignmentWeeklySizedPortfolioStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1d"
    startup_candle_count = 210
    process_only_new_candles = True
    minimal_roi = {"0": 100}
    stoploss = -0.99
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    position_adjustment_enable = True
    max_entry_position_adjustment = -1

    TARGET_KEY = "weekly_target"

    def informative_pairs(self):
        return [(pair, "1w") for pair in self.dp.current_whitelist()]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = dataframe["close"].ewm(span=20, adjust=False).mean()
        dataframe["ema50"] = dataframe["close"].ewm(span=50, adjust=False).mean()
        dataframe["ma200"] = dataframe["close"].rolling(200).mean()

        weekly = self.dp.get_pair_dataframe(metadata["pair"], "1w")
        weekly["ema20_w"] = weekly["close"].ewm(span=20, adjust=False).mean()
        weekly["ema50_w"] = weekly["close"].ewm(span=50, adjust=False).mean()
        weekly["weekly_bull"] = weekly["ema20_w"] > weekly["ema50_w"]
        dataframe = merge_informative_pair(dataframe, weekly, self.timeframe, "1w", ffill=True)
        dataframe["weekly_bull"] = dataframe["weekly_bull_1w"].fillna(False)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        aligned = (
            (dataframe["close"] > dataframe["ema20"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["ema50"] > dataframe["ma200"])
            & (dataframe["ema20"] > dataframe["ema20"].shift(1))
            & (dataframe["ema50"] > dataframe["ema50"].shift(1))
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[aligned, ["enter_long", "enter_tag"]] = [1, "ema_alignment"]
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        invalid = (
            (dataframe["close"] < dataframe["ma200"])
            | (dataframe["ema20"] < dataframe["ema50"])
        )
        confirmed = invalid & invalid.shift(1).fillna(False)
        dataframe.loc[confirmed, ["exit_long", "exit_tag"]] = [1, "trend_alignment_lost_confirmed"]
        return dataframe

    def _target_fraction(self, pair: str, current_time: datetime) -> float | None:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        rows = dataframe.loc[dataframe["date"] <= current_time]
        if rows.empty:
            return None
        return 1.0 if bool(rows.iloc[-1]["weekly_bull"]) else 0.5

    def _slots(self) -> int:
        slots = self.config.get("max_open_trades", -1)
        if slots is None or slots <= 0 or math.isinf(slots):
            return max(1, len(self.dp.current_whitelist()))
        return int(slots)

    def _executing_candle_start(self, current_time: datetime) -> datetime:
        # 回测里 current_time 是正在执行那根 K 线的开盘时间，实盘里是这根 K 线内的某个时刻，
        # 两者向下取整都得到同一根 K 线的开盘时间，所以不需要区分运行模式。
        return timeframe_to_prev_date(self.timeframe, current_time)

    def _last_close(self, pair: str, current_time: datetime) -> float | None:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        candle_start = self._executing_candle_start(current_time)
        closed = dataframe.loc[dataframe["date"] < candle_start]
        if closed.empty:
            return None
        return float(closed.iloc[-1]["close"])

    def _slot_value(
        self, current_time: datetime, current_pair: str, current_rate: float
    ) -> float:
        equity = float(self.wallets.get_free(self.config["stake_currency"]))
        candle_start = self._executing_candle_start(current_time)
        for trade in Trade.get_trades_proxy(is_open=True):
            if trade.pair == current_pair:
                rate = current_rate
            elif trade.open_date_utc >= candle_start:
                rate = float(trade.open_rate)
            else:
                rate = self._last_close(trade.pair, current_time) or float(trade.open_rate)
            equity += float(trade.amount) * rate
        return equity / self._slots()

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: float | None, max_stake: float,
        leverage: float, entry_tag: str | None, side: str, **kwargs,
    ) -> float:
        target = self._target_fraction(pair, current_time)
        if target is None:
            return proposed_stake
        return min(target * self._slot_value(current_time, pair, current_rate), max_stake)

    def adjust_trade_position(
        self, trade: Trade, current_time: datetime, current_rate: float,
        current_profit: float, min_stake: float | None, max_stake: float,
        current_entry_rate: float, current_exit_rate: float,
        current_entry_profit: float, current_exit_profit: float, **kwargs,
    ) -> float | None:
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        target = self._target_fraction(trade.pair, current_time)
        if target is None:
            return None
        previous = trade.get_custom_data(self.TARGET_KEY)
        if previous is None:
            previous = self._target_fraction(trade.pair, trade.open_date_utc) or target
        previous = float(previous)
        if target == previous:
            return None
        trade.set_custom_data(self.TARGET_KEY, target)
        if target < previous:
            return -float(trade.stake_amount) * (1 - target / previous)
        top_up = (
            self._slot_value(current_time, trade.pair, current_rate)
            - float(trade.amount) * current_rate
        )
        if top_up < 1.0:
            return None
        return min(top_up, max_stake)
