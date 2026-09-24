"""MA200+EMA 策略的合约杠杆分级版（研究用，验证未通过，不建议实盘）。

规则：进场、退出和周线仓位信号跟 Ma200EmaAlignmentWeeklySizedStrategy 一样。
进场时，如果周线 EMA20 > EMA50 也确认多头，就用 3 倍杠杆，否则用 1 倍。
自定义止损让止损点大约保持在离开仓价 10% 的标的价格处（杠杆不同时一样）。
文件末尾的 Ma200EmaAlignmentWeeklySizedOneXControlStrategy 是对照组：信号相同，全部 1 倍。

使用场景：只用于研究"周线确认时加杠杆"是否划算，不用于 dry-run 或实盘。

验证结论（2026-09-23，失败）：
- 在 48 组有重叠的样本内币安 USDT 永续回测里，杠杆分级版只有 11/48 组跑赢 1 倍对照组，
  收益差的中位数 -30.00 个百分点，回撤差的中位数 -30.58 个百分点（回撤更深）。
- 2024-01-01 到 2026-09-20 的共同区间里，只有 2/10 个资产跑赢买入持有。
- 回测中没有出现模拟爆仓，但这不能说明实盘安全。

已知问题（未修，因为本策略不用于实盘）：adjust_trade_position 用 current_time 判断
"每根 K 线只调一次"，实盘里 current_time 是 now()，每次循环都不同，防护失效，会在一天内
反复调仓；1 USDT 的阈值也低于交易所最小下单额。单币版 2026-09-23 已修同样的问题
（改用日线 K 线开盘时间），如果要复用这里的代码必须先照着修。
详见 ../validation/ma200_ema_alignment_robustness_20260922/LEVERAGE_MATRIX_REPORT.md。
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, stoploss_from_open
from pandas import DataFrame


class Ma200EmaAlignmentWeeklySizedLeverageStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    timeframe = "1d"
    startup_candle_count = 210
    process_only_new_candles = True
    minimal_roi = {"0": 100}
    stoploss = -0.30
    use_custom_stoploss = True
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

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if (
            side == "long"
            and entry_tag == "ema_alignment"
            and self._weekly_bull(pair, current_time)
        ):
            return min(3.0, max_leverage)
        return 1.0

    def _weekly_bull(self, pair: str, current_time: datetime) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return False
        rows = dataframe.loc[dataframe["date"] <= current_time]
        if rows.empty:
            return False
        return bool(rows.iloc[-1]["weekly_bull"])

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> float:
        underlying_stop = -0.10 * max(float(trade.leverage), 1.0)
        return stoploss_from_open(
            underlying_stop,
            current_profit,
            is_short=trade.is_short,
            leverage=max(float(trade.leverage), 1.0),
        )

    def _target_fraction(self, pair: str, current_time: datetime) -> float | None:
        weekly_bull = self._weekly_bull(pair, current_time)
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        rows = dataframe.loc[dataframe["date"] <= current_time]
        if rows.empty:
            return None
        return 1.0 if weekly_bull else 0.5

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        target = self._target_fraction(pair, current_time)
        if target is None:
            return proposed_stake
        return min(proposed_stake * target, max_stake)

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> float | None:
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        target = self._target_fraction(trade.pair, current_time)
        if target is None:
            return None
        key = int(trade.id or id(trade))
        if self._adjusted_at.get(key) == current_time:
            return None

        leverage = max(float(trade.leverage), 1.0)
        position_value = float(trade.amount) * current_rate
        cash = float(self.wallets.get_available_stake_amount())
        equity_in_position = float(trade.stake_amount) * (1 + current_profit)
        total_equity = max(equity_in_position, 0.0) + cash
        desired_value = target * total_equity * leverage
        difference = desired_value - position_value
        if abs(difference) < 1.0:
            return None
        self._adjusted_at[key] = current_time
        if difference > 0:
            return min(difference / leverage, max_stake)
        return -min(
            float(trade.stake_amount) * -difference / position_value,
            float(trade.stake_amount) * 0.999,
        )


class Ma200EmaAlignmentWeeklySizedOneXControlStrategy(
    Ma200EmaAlignmentWeeklySizedLeverageStrategy
):
    """1 倍对照组：信号和约 10% 的标的价格止损都跟 3 倍版一样，只是不加杠杆。"""

    stoploss = -0.10

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        return 1.0
