"""MA200+EMA 趋势策略（单币版）。2026-09-23 提升为正式策略，取代已归档的"退出确认版"。

规则：
- 进场：日线 收盘 > EMA20 > EMA50 > MA200，且 EMA20、EMA50 都在上升。
- 退出：收盘 < MA200 或 EMA20 < EMA50，连续 2 根完整日线成立才清仓。
- 仓位：持仓期间，周线 EMA20 > EMA50（周线多头）时满仓，否则减到 50%。50% 状态下
  每根日线开盘把仓位拉回正好 50%（跌了补、涨了卖），每根日线最多调一次，低于交易所
  最小下单额的零碎调仓跳过（2026-09-23 修复：之前实盘每次循环都会调仓）。
  周线数据用 Freqtrade 标准的 informative_pairs + merge_informative_pair 读取。
- 止损：-99%（等于不设），风控靠退出规则。固定 10%/25% 和 3 倍 ATR 止损都测过，全部否决。

使用场景：
- 一个账户只跑一个币（max_open_trades = 1），比如单独跑 BTC 或 ETH。
- 不要放进多币共用的钱包：本策略的目标仓位 = 目标比例 x（持仓市值 + 全部可用现金），
  多币共用时第一个开仓的币会吃掉全部现金，其他币进不去。回测里原版放进 10 币钱包，
  回撤是 -47%～-85%。多币请用 ma200_ema_alignment_weekly_sized_portfolio_strategy.py。

验证结论（九个山寨币 + BTC，五个市场区间，见
../validation/ma200_ema_alignment_robustness_20260922/REPORT.md 和 FINAL_REPORT.md）：
- 跟退出确认版相比，九个资产的回撤全部改善（常常接近减半），熊市亏损大约减半。
- 熊市区间 8/8 跑赢买入持有；全周期 6/9 跑赢。
- 代价集中在 BNB 这类低波动、长期单边上涨的资产：周线正常回调时减仓，会让出一部分收益。

已知且接受的局限：
- 每个单边牛市区间里，所有测试资产都跑输买入持有（均线退出规则固有的滞后）。
- LINK、XRP、ZEC 全周期跑输买入持有（反复假突破磨损 / 进场滞后）。
- 每个币要先攒够约 200 根日线（MA200）才能交易，新币要等半年以上。
- 全部是样本内验证，还没有样本外或 dry-run 验证。
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, timeframe_to_prev_date
from pandas import DataFrame


class Ma200EmaAlignmentWeeklySizedStrategy(IStrategy):
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

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._adjusted_at: dict[int, datetime] = {}

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

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: float | None, max_stake: float,
        leverage: float, entry_tag: str | None, side: str, **kwargs,
    ) -> float:
        target = self._target_fraction(pair, current_time)
        if target is None:
            return proposed_stake
        return min(proposed_stake * target, max_stake)

    def adjust_trade_position(
        self, trade: Trade, current_time: datetime, current_rate: float,
        current_profit: float, min_stake: float | None, max_stake: float,
        current_entry_rate: float, current_exit_rate: float,
        current_entry_profit: float, current_exit_profit: float, **kwargs,
    ) -> float | None:
        # 实盘里 current_time 是 now()，每次循环都不同；按日线 K 线的开盘时间比较，
        # 才能跟回测一样每根 K 线最多检查一次（开仓当根不调）。
        candle = timeframe_to_prev_date(self.timeframe, current_time)
        if trade.has_open_orders or trade.open_date_utc >= candle:
            return None
        target = self._target_fraction(trade.pair, current_time)
        if target is None:
            return None
        key = int(trade.id or id(trade))
        if self._adjusted_at.get(key) == candle:
            return None
        self._adjusted_at[key] = candle
        position_value = float(trade.amount) * current_rate
        cash = float(self.wallets.get_available_stake_amount())
        desired = target * (position_value + cash)
        difference = desired - position_value
        if abs(difference) < max(1.0, min_stake or 0.0):
            return None
        if difference > 0:
            return min(difference, max_stake)
        return -min(float(trade.stake_amount) * -difference / position_value,
                    float(trade.stake_amount) * 0.999)
