"""Full-cycle core-hold strategy with configurable research settings.

Defaults retain the original entry rules, 50% core and two-day BTC exit.
Early entries and alternative parameters require out-of-sample validation.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from freqtrade.data.history import load_pair_history
from freqtrade.enums import CandleType, RunMode
from freqtrade.persistence import Order, Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, timeframe_to_prev_date
from pandas import DataFrame


logger = logging.getLogger(__name__)

BULL_TAG = "bull_btc_regime_ema_alignment"
BEAR_TAG = "bear_accumulate"


class Ma200BtcRegimeFullCycleCoreHoldStrategy(IStrategy):
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

    # Research knobs: sweep via strategy subclasses, without changing live config.
    CORE_RETAIN_FRACTION = 0.50
    BTC_BEAR_CONFIRM_DAYS = 2
    BULL_ENTRY_MODE = "alignment"  # "early": close > rising EMA20, BTC above MA200
    # Optional growth experiments: restore trimmed exposure after coin recovery,
    # and let handed-over bear positions use the same core rules as bull entries.
    CORE_RESTORE_ON_RECOVERY = False
    BULL_WEEKLY_SIZING = True
    HANDOVER_CORE_HOLD = False
    CORE_RESTORE_TAG = "bull_core_restore"
    HANDOVER_TOP_UP_TAG = "handover_top_up"
    CORE_TRIM_KEY = "core_hold_trimmed"
    CORE_TRIM_TAG = "bull_core_trim"

    BTC_PAIR = "BTC/USDT"
    # 仓位调节用的高一级周期（正式版是周线）。快速测试版改成 1h。
    INFORMATIVE_TIMEFRAME = "1w"
    TARGET_KEY = "weekly_target"
    BULL_ENABLED = True
    BEAR_ENABLED = True
    # (BTC 相对 MA200 的偏离率, 该偏离下累计投入资金的比例)
    BEAR_TIERS = [(-0.10, 0.20), (-0.20, 0.40), (-0.30, 0.60), (-0.40, 0.80), (-0.50, 1.00)]
    # 熊市只囤这些币（None = 币池里所有币等权）。给了列表时，每个币 = 1 / 列表长度。
    BEAR_PAIRS: list[str] | None = None
    # 分档依据："ma200" = BTC 相对 MA200 的偏离率（BEAR_TIERS）；"ath" = BTC 距历史最高收盘价
    # 的跌幅（BEAR_ATH_TIERS）。MA200 在熊市里自己会往下掉，按偏离率分档会买早（2022 年 6 月、
    # BTC 约 19000 时就满仓了，11 月真正的底 15500 时偏离只有 -29%）。
    # 注意：实盘 DataProvider 只有约 1000 根日线，历史最高价比这更早时会算错。
    BEAR_TIER_BASIS = "ma200"
    BEAR_ATH_TIERS = [(-0.50, 0.25), (-0.65, 0.50), (-0.75, 0.75), (-0.85, 1.00)]
    # True：BTC 站回 MA200 时不卖熊市囤的币，交给牛市部分，按牛市规则卖出（BTC 转熊或该币死叉）。
    HANDOVER_TO_BULL = True
    # True：交接给牛市部分之后，这个币的 EMA20 > EMA50 出现过一次之前，只在 BTC 转熊时卖，
    # 不看它自己的死叉。BTC 刚站回 MA200 时很多山寨币还没转强，不加这条会在交接第二天卖掉。
    HANDOVER_GRACE = False
    # True：交接时把熊市仓位补到满槽位（跟牛市部分新开仓一样大），之后按周线调仓。
    # 不补的话，熊市仓位（比如 60% 那档）一直占着这个币唯一的持仓位置，牛市部分没法再开满仓。
    HANDOVER_TOP_UP = False
    HANDOVER_KEY = "handover_topped_up"
    # True：牛市开仓直接满槽位；持仓期间周线出现过一次多头之后，周线转空才减到半槽位。
    BULL_ENTRY_FULL = True
    WEEKLY_SEEN_KEY = "weekly_bull_seen"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        if not 0 < self.CORE_RETAIN_FRACTION <= 1:
            raise ValueError("CORE_RETAIN_FRACTION must be in (0, 1].")
        if (isinstance(self.BTC_BEAR_CONFIRM_DAYS, bool)
                or not isinstance(self.BTC_BEAR_CONFIRM_DAYS, int)
                or self.BTC_BEAR_CONFIRM_DAYS < 1):
            raise ValueError("BTC_BEAR_CONFIRM_DAYS must be a positive integer.")
        if self.BULL_ENTRY_MODE not in ("alignment", "early"):
            raise ValueError("BULL_ENTRY_MODE must be alignment or early.")
        if self.CORE_RESTORE_ON_RECOVERY and self.BULL_WEEKLY_SIZING:
            raise ValueError("CORE_RESTORE_ON_RECOVERY requires BULL_WEEKLY_SIZING=False.")
        if self.HANDOVER_CORE_HOLD and not (self.HANDOVER_TO_BULL and self.HANDOVER_TOP_UP):
            raise ValueError("HANDOVER_CORE_HOLD requires bull handover and top-up.")
        self._history_cache: dict[tuple[str, str], DataFrame] = {}

    def informative_pairs(self):
        pairs = [(pair, self.INFORMATIVE_TIMEFRAME) for pair in self.dp.current_whitelist()]
        return pairs + [(self.BTC_PAIR, self.timeframe)]

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

    @staticmethod
    def _tier(value: float, tiers: list[tuple[float, float]]) -> float:
        target = 0.0
        for level, fraction in tiers:
            if value <= level:
                target = max(target, fraction)
        return target

    # ---- 指标和信号 ----

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if dataframe.empty:
            return dataframe
        daily = self._history(metadata["pair"], self.timeframe)[["date", "close"]].copy()
        daily["ema20"] = daily["close"].ewm(span=20, adjust=False).mean()
        daily["ema50"] = daily["close"].ewm(span=50, adjust=False).mean()
        daily["own_candles"] = np.arange(1, len(daily) + 1)
        dataframe = dataframe.merge(
            daily[["date", "ema20", "ema50", "own_candles"]], on="date", how="left"
        )

        btc = self._history(self.BTC_PAIR, self.timeframe)[["date", "close"]].copy()
        btc["btc_ma200"] = btc["close"].rolling(200).mean()
        btc["btc_dev"] = btc["close"] / btc["btc_ma200"] - 1
        # BTC 当天 K 线缺失或 MA200 没算出来时，这几列都是 False：不开仓，也不按 BTC 卖出。
        btc["btc_above"] = btc["close"] > btc["btc_ma200"]
        btc["btc_below"] = btc["close"] < btc["btc_ma200"]
        btc["btc_bull_2d"] = btc["btc_above"] & btc["btc_above"].shift(1, fill_value=False)
        btc["btc_bear_2d"] = btc["btc_below"] & btc["btc_below"].shift(1, fill_value=False)
        if self.BEAR_TIER_BASIS == "ath":
            drawdown = btc["close"] / btc["close"].cummax() - 1
            tiers = drawdown.map(lambda v: self._tier(v, self.BEAR_ATH_TIERS))
        else:
            tiers = btc["btc_dev"].map(lambda v: self._tier(v, self.BEAR_TIERS))
        btc["bear_target"] = np.where(btc["btc_bear_2d"], tiers, 0.0)
        dataframe = dataframe.merge(
            btc[["date", "btc_ma200", "btc_dev", "btc_above", "btc_below",
                 "btc_bull_2d", "bear_target"]],
            on="date", how="left",
        )
        if pd.isna(dataframe["btc_ma200"].iloc[-1]):
            logger.warning("%s: BTC 日线缺少 %s 的数据，本根 K 线不开仓也不按 BTC 卖出",
                           metadata["pair"], dataframe["date"].iloc[-1])
        for col in ("btc_above", "btc_below", "btc_bull_2d"):
            dataframe[col] = dataframe[col].astype("boolean").fillna(False).astype(bool)
        dataframe["bear_target"] = dataframe["bear_target"].fillna(0.0)

        # 牛市部分的退出条件：BTC 转熊或该币死叉，连续 2 根日线
        invalid = dataframe["btc_below"] | (dataframe["ema20"] < dataframe["ema50"])
        dataframe["bull_exit"] = invalid & invalid.shift(1, fill_value=False)
        dataframe["btc_exit"] = (
            dataframe["btc_below"].rolling(self.BTC_BEAR_CONFIRM_DAYS,
                                           min_periods=self.BTC_BEAR_CONFIRM_DAYS).sum()
            == self.BTC_BEAR_CONFIRM_DAYS
        )
        coin_weak = dataframe["ema20"] < dataframe["ema50"]
        dataframe["coin_weak_2d"] = coin_weak & coin_weak.shift(1, fill_value=False)
        dataframe["coin_recovered"] = (
            dataframe["btc_above"]
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["ema20"] > dataframe["ema20"].shift(1))
        )

        weekly = self._history(metadata["pair"], self.INFORMATIVE_TIMEFRAME)
        weekly["ema20_w"] = weekly["close"].ewm(span=20, adjust=False).mean()
        weekly["ema50_w"] = weekly["close"].ewm(span=50, adjust=False).mean()
        weekly["weekly_bull"] = weekly["ema20_w"] > weekly["ema50_w"]
        dataframe = merge_informative_pair(
            dataframe, weekly, self.timeframe, self.INFORMATIVE_TIMEFRAME, ffill=True
        )
        dataframe["weekly_bull"] = dataframe[f"weekly_bull_{self.INFORMATIVE_TIMEFRAME}"].fillna(False)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        has_volume = dataframe["volume"] > 0
        if self.BEAR_ENABLED:
            # 新币要有 startup_candle_count 根自己的日线才参与（熊市囤币策略单独跑时是 30 根，
            # 这里跟牛市部分统一成 60 根，回测和实盘才一致）。
            bear_allowed = self.BEAR_PAIRS is None or metadata["pair"] in self.BEAR_PAIRS
            bear = (
                (dataframe["own_candles"] > self.startup_candle_count)
                & (dataframe["bear_target"] > 0)
                & has_volume
                & bear_allowed
            )
            dataframe.loc[bear, ["enter_long", "enter_tag"]] = [1, BEAR_TAG]
        if self.BULL_ENABLED:
            # 回测会切掉每个币最前面 startup_candle_count 根 K 线，实盘不会，所以显式要求
            # 至少有这么多根自己的日线，实盘和回测才一致。
            bull = (
                (dataframe["own_candles"] > self.startup_candle_count)
                & dataframe["btc_above"]
                & (dataframe["close"] > dataframe["ema20"])
                & (dataframe["ema20"] > dataframe["ema20"].shift(1))
                & has_volume
            )
            if self.BULL_ENTRY_MODE == "alignment":
                bull &= ((dataframe["ema20"] > dataframe["ema50"])
                         & (dataframe["ema50"] > dataframe["ema50"].shift(1)))
            dataframe.loc[bull, ["enter_long", "enter_tag"]] = [1, BULL_TAG]
        return dataframe

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float, time_in_force: str,
        current_time: datetime, entry_tag: str | None, side: str, **kwargs,
    ) -> bool:
        """同一轮熊市里，某个币的囤币仓位被止损过（归零、崩盘），就不再买它，直到 BTC 站回 MA200。
        2022-05 LUNA 被 -99% 止损后，不加这条会第二天、第三天接着买。"""
        if entry_tag != BEAR_TAG:
            return True
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        for trade in Trade.get_trades_proxy(pair=pair, is_open=False):
            if trade.enter_tag != BEAR_TAG or trade.exit_reason != "stop_loss":
                continue
            since = dataframe.loc[(dataframe["date"] >= trade.close_date_utc)
                                  & (dataframe["date"] < self._executing_candle_start(current_time))]
            if not since["btc_bull_2d"].any():
                return False
        return True

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 两边的退出条件不同，按开仓标签在 custom_exit 里判断。
        return dataframe

    def _last_closed_row(self, pair: str, current_time: datetime) -> pd.Series | None:
        """正在执行的 K 线之前最后一根完整日线（跟信号在下一根开盘执行的时点一致）。"""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        rows = dataframe.loc[dataframe["date"] < self._executing_candle_start(current_time)]
        return None if rows.empty else rows.iloc[-1]

    def custom_exit(
        self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
        current_profit: float, **kwargs,
    ) -> str | None:
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return None
        if (trade.enter_tag == BEAR_TAG and self.HANDOVER_CORE_HOLD
                and self._bull_seen_since_open(pair, trade, current_time)):
            return "handover_btc_bear_core_exit" if bool(row["btc_exit"]) else None
        if trade.enter_tag == BEAR_TAG:
            if not self.HANDOVER_TO_BULL:
                return "bear_btc_above_ma200" if bool(row["btc_bull_2d"]) else None
            # 交给牛市部分：BTC 站回 MA200 之后，按牛市规则卖出
            if not self._bull_seen_since_open(pair, trade, current_time):
                return None
            if self.HANDOVER_GRACE and not self._golden_cross_since_handover(pair, trade, current_time):
                # 缓冲期：这个币交接后还没转强过，只在 BTC 转熊时卖
                return "handover_grace_btc_bear" if bool(row["btc_exit"]) else None
            return "handover_btc_regime_or_alignment_lost" if bool(row["bull_exit"]) else None
        # Bull positions keep their core through coin-level pullbacks.
        # The remaining core exits after the configured BTC bear confirmation.
        return "bull_btc_bear_core_exit" if bool(row["btc_exit"]) else None

    def _golden_cross_since_handover(self, pair: str, trade: Trade, current_time: datetime) -> bool:
        """交接（开仓后第一次 BTC 连续 2 天站上 MA200）之后，这个币的 EMA20 > EMA50 出现过没有。"""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        held = dataframe.loc[(dataframe["date"] >= trade.open_date_utc)
                             & (dataframe["date"] < self._executing_candle_start(current_time))]
        bull_rows = held.index[held["btc_bull_2d"]]
        if len(bull_rows) == 0:
            return False
        after = held.loc[bull_rows[0]:]
        return bool((after["ema20"] > after["ema50"]).any())

    def _bull_seen_since_open(self, pair: str, trade: Trade, current_time: datetime) -> bool:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        held = dataframe.loc[(dataframe["date"] >= trade.open_date_utc)
                             & (dataframe["date"] < self._executing_candle_start(current_time))]
        return bool(held["btc_bull_2d"].any())

    # ---- 仓位 ----

    def _slots(self) -> int:
        slots = self.config.get("max_open_trades", -1)
        if slots is None or slots <= 0 or math.isinf(slots):
            return max(1, len(self.dp.current_whitelist()))
        return int(slots)

    def _executing_candle_start(self, current_time: datetime) -> datetime:
        # 回测里 current_time 是正在执行那根 K 线的开盘时间，实盘里是这根 K 线内的某个时刻，
        # 两者向下取整都得到同一根 K 线的开盘时间。
        return timeframe_to_prev_date(self.timeframe, current_time)

    def _last_close(self, pair: str, current_time: datetime) -> float | None:
        row = self._last_closed_row(pair, current_time)
        return None if row is None else float(row["close"])

    def _equity(self, current_time: datetime, current_pair: str, current_rate: float) -> float:
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
        return equity

    def _capital(self) -> float:
        """熊市部分的资金 = 现金 + 持仓成本。"""
        capital = float(self.wallets.get_free(self.config["stake_currency"]))
        for trade in Trade.get_trades_proxy(is_open=True):
            capital += float(trade.stake_amount)
        return capital

    def _weekly_target(self, pair: str, current_time: datetime) -> float | None:
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return None
        return 1.0 if bool(row["weekly_bull"]) else 0.5

    def _bear_target_cost(self, pair: str, current_time: datetime) -> float:
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return 0.0
        weight = 1 / len(self.BEAR_PAIRS) if self.BEAR_PAIRS else 1 / self._slots()
        return float(row["bear_target"]) * self._capital() * weight

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: float | None, max_stake: float,
        leverage: float, entry_tag: str | None, side: str, **kwargs,
    ) -> float:
        if entry_tag == BEAR_TAG:
            return min(self._bear_target_cost(pair, current_time), max_stake)
        target = 1.0 if self.BULL_ENTRY_FULL else self._weekly_target(pair, current_time)
        if target is None:
            return proposed_stake
        slot = self._equity(current_time, pair, current_rate) / self._slots()
        return min(target * slot, max_stake)

    def adjust_trade_position(
        self, trade: Trade, current_time: datetime, current_rate: float,
        current_profit: float, min_stake: float | None, max_stake: float,
        current_entry_rate: float, current_exit_rate: float,
        current_entry_profit: float, current_exit_profit: float, **kwargs,
    ) -> float | tuple[float, str] | None:
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        handed_over = False
        if trade.enter_tag == BEAR_TAG:
            handed_over = (self.HANDOVER_TO_BULL and self.HANDOVER_TOP_UP
                           and self._bull_seen_since_open(trade.pair, trade, current_time))
            if not handed_over:
                top_up = self._bear_target_cost(trade.pair, current_time) - float(trade.stake_amount)
                if top_up < max(1.0, min_stake or 0):
                    return None
                return min(top_up, max_stake)
            if not trade.get_custom_data(self.HANDOVER_KEY):
                row = self._last_closed_row(trade.pair, current_time)
                if row is None or not bool(row["btc_above"]):
                    return None
                top_up = (
                    self._equity(current_time, trade.pair, current_rate) / self._slots()
                    - float(trade.amount) * current_rate
                )
                minimum = max(1.0, min_stake or 0.0)
                if top_up < minimum:
                    # The position already meets the slot target within exchange limits.
                    trade.set_custom_data(self.HANDOVER_KEY, True)
                    trade.set_custom_data(self.TARGET_KEY, 1.0)
                    return None
                amount = min(top_up, max_stake)
                if amount < minimum:
                    return None
                return amount, self.HANDOVER_TOP_UP_TAG

        core_position = (trade.enter_tag == BULL_TAG
                         or (handed_over and self.HANDOVER_CORE_HOLD))
        if core_position:
            row = self._last_closed_row(trade.pair, current_time)
            if row is None or bool(row["btc_exit"]):
                return None
            if trade.get_custom_data(self.CORE_TRIM_KEY):
                if not self.CORE_RESTORE_ON_RECOVERY or not bool(row["coin_recovered"]):
                    return None
                top_up = (
                    self._equity(current_time, trade.pair, current_rate) / self._slots()
                    - float(trade.amount) * current_rate
                )
                minimum = max(1.0, min_stake or 0.0)
                if top_up < minimum:
                    trade.set_custom_data(self.CORE_TRIM_KEY, False)
                    return None
                amount = min(top_up, max_stake)
                return (amount, self.CORE_RESTORE_TAG) if amount >= minimum else None
            if bool(row["coin_weak_2d"]):
                sell_fraction = 1 - self.CORE_RETAIN_FRACTION
                reduction = float(trade.stake_amount) * sell_fraction
                position_value = float(trade.amount) * current_exit_rate
                minimum = min_stake or 0.0
                if (reduction <= 0 or position_value * sell_fraction < minimum
                        or position_value * self.CORE_RETAIN_FRACTION < minimum):
                    return None
                return -reduction, self.CORE_TRIM_TAG
        if not self.BULL_WEEKLY_SIZING and (core_position or handed_over):
            return None

        target = self._weekly_target(trade.pair, current_time)
        if target is None:
            return None
        if self.BULL_ENTRY_FULL:
            # 周线多头出现之前一直按满槽位算（开仓就是满的）
            if target == 1.0:
                trade.set_custom_data(self.WEEKLY_SEEN_KEY, True)
            elif not trade.get_custom_data(self.WEEKLY_SEEN_KEY):
                target = 1.0
        previous = trade.get_custom_data(self.TARGET_KEY)
        if previous is None:
            previous = 1.0 if self.BULL_ENTRY_FULL else (
                self._weekly_target(trade.pair, trade.open_date_utc) or target)
        previous = float(previous)
        if target == previous:
            return None
        trade.set_custom_data(self.TARGET_KEY, target)
        if target < previous:
            return -float(trade.stake_amount) * (1 - target / previous)
        top_up = (
            self._equity(current_time, trade.pair, current_rate) / self._slots()
            - float(trade.amount) * current_rate
        )
        if top_up < 1.0:
            return None
        return min(top_up, max_stake)

    def order_filled(
        self, pair: str, trade: Trade, order: Order, current_time: datetime, **kwargs,
    ) -> None:
        # A rejected/cancelled order must not freeze a position that was never trimmed.
        if (order.ft_order_side == trade.exit_side
                and order.ft_order_tag == self.CORE_TRIM_TAG):
            trade.set_custom_data(self.CORE_TRIM_KEY, True)
        elif order.ft_order_side == trade.entry_side:
            if order.ft_order_tag == self.CORE_RESTORE_TAG:
                trade.set_custom_data(self.CORE_TRIM_KEY, False)
            elif order.ft_order_tag == self.HANDOVER_TOP_UP_TAG:
                trade.set_custom_data(self.HANDOVER_KEY, True)
                trade.set_custom_data(self.TARGET_KEY, 1.0)


class BtcTrendFullCycleStrategy(Ma200BtcRegimeFullCycleCoreHoldStrategy):
    """Experimental full trend exposure with cash exits and coin capital.

    Rejected for default adoption: cross-regime drawdowns are too large.
    No permanent core or bear accumulation. Research comparison and limits:
    validation/core_hold/trend_exposure/REPORT.md. Existing Growth is preserved.
    """

    BEAR_ENABLED = False
    TREND_MA_DAYS = 150
    RECOVERY_EMA_DAYS = 10
    TREND_EXIT_DAYS = 2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        if dataframe.empty:
            return dataframe
        btc = self._history(self.BTC_PAIR, self.timeframe)[["date", "close"]].copy()
        trend = btc["close"].rolling(self.TREND_MA_DAYS).mean()
        recovery_ema = btc["close"].ewm(span=self.RECOVERY_EMA_DAYS, adjust=False).mean()
        recovery = ((btc["close"] > recovery_ema)
                    & (recovery_ema > recovery_ema.shift(1)))
        valid = trend.notna()
        btc["exposure_entry"] = valid & ((btc["close"] > trend) | recovery)
        weak = valid & (btc["close"] < trend) & ~recovery
        btc["exposure_exit"] = weak.rolling(self.TREND_EXIT_DAYS).sum() == self.TREND_EXIT_DAYS
        return dataframe.merge(
            btc[["date", "exposure_entry", "exposure_exit"]], on="date", how="left"
        )

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        allowed = ((dataframe["own_candles"] > self.startup_candle_count)
                   & (dataframe["volume"] > 0)
                   & dataframe["exposure_entry"].fillna(False))
        dataframe.loc[allowed, ["enter_long", "enter_tag"]] = [1, "trend_full_exposure"]
        return dataframe

    def confirm_trade_entry(self, **kwargs) -> bool:
        return True

    def custom_exit(
        self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
        current_profit: float, **kwargs,
    ) -> str | None:
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return None
        exit_signal = row.get("exposure_exit", False)
        return "trend_to_cash" if pd.notna(exit_signal) and bool(exit_signal) else None

    def adjust_trade_position(self, *args, **kwargs) -> None:
        return None

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: float | None, max_stake: float,
        leverage: float, entry_tag: str | None, side: str, **kwargs,
    ) -> float:
        capital = self.wallets.get_starting_balance() / self._slots()
        profits = sum(float(t.close_profit_abs or 0.)
                      for t in Trade.get_trades_proxy(pair=pair, is_open=False))
        budget = max(0., capital + profits)
        configured_fee = self.config.get("fee")
        fee = .001 if configured_fee is None else float(configured_fee)
        stake = min(budget / (1 + fee), max_stake)
        return stake if stake >= (min_stake or 0.) else 0.


class BtcTrendFullCycleDefensiveStrategy(BtcTrendFullCycleStrategy):
    """Experimental strict MA150 trend/cash profile; no bear rebound entry.

    Not a replacement for Growth: compare full-cycle risk in the research report.
    """

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = Ma200BtcRegimeFullCycleCoreHoldStrategy.populate_indicators(
            self, dataframe, metadata
        )
        if dataframe.empty:
            return dataframe
        btc = self._history(self.BTC_PAIR, self.timeframe)[["date", "close"]].copy()
        trend = btc["close"].rolling(self.TREND_MA_DAYS).mean()
        btc["exposure_entry"] = btc["close"] > trend
        weak = btc["close"] < trend
        btc["exposure_exit"] = weak.rolling(self.TREND_EXIT_DAYS).sum() == self.TREND_EXIT_DAYS
        return dataframe.merge(
            btc[["date", "exposure_entry", "exposure_exit"]], on="date", how="left"
        )

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: float | None, max_stake: float,
        leverage: float, entry_tag: str | None, side: str, **kwargs,
    ) -> float:
        return Ma200BtcRegimeFullCycleCoreHoldStrategy.custom_stake_amount(
            self, pair, current_time, current_rate, proposed_stake, min_stake,
            max_stake, leverage, entry_tag, side, **kwargs
        )


class BtcTrendRecoveryCooldownStrategy(BtcTrendFullCycleStrategy):
    """Trend recovery with a 14-day cooldown below BTC's MA150.

    After an exit, do not chase another sub-MA150 rebound during the cooldown.
    A confirmed close above MA150 permits reentry immediately. No permanent core.
    Measured results and tradeoffs: validation/core_hold/trend_cooldown/REPORT.md.
    """

    RECOVERY_COOLDOWN_DAYS = 14

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        if dataframe.empty:
            return dataframe
        btc = self._history(self.BTC_PAIR, self.timeframe)[["date", "close"]].copy()
        btc["cooldown_btc_strict"] = (
            btc["close"] > btc["close"].rolling(self.TREND_MA_DAYS).mean()
        )
        return dataframe.merge(btc[["date", "cooldown_btc_strict"]], on="date", how="left")

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


class BtcTrendPhasedStrategy(BtcTrendRecoveryCooldownStrategy):
    """75% trend-recovery exposure below MA150, full exposure above.

    Reduce risk when the long trend fails; restore it after confirmation.
    No permanent core. Research results: validation/core_hold/trend_phased/REPORT.md.
    """
    EARLY_EXPOSURE = 0.75
    PHASE_KEY = 'trend_filled_exposure'
    PHASE_UP_TAG = 'phase_risk_on'
    PHASE_DOWN_TAG = 'phase_risk_reduce'

    def populate_entry_trend(self, dataframe, metadata):
        dataframe = super().populate_entry_trend(dataframe, metadata)
        entries = dataframe.enter_long == 1
        dataframe.loc[entries & dataframe.cooldown_btc_strict.fillna(False), 'enter_tag'] = 'phase_full_entry'
        dataframe.loc[entries & ~dataframe.cooldown_btc_strict.fillna(False), 'enter_tag'] = 'phase_reduced_entry'
        return dataframe

    def _pair_budget(self, pair):
        # Freeze principal; open partial profits must not inflate it.
        if not hasattr(self, '_phase_initial_capital'):
            capital = float(self.wallets.get_starting_balance())
            if 'available_capital' not in self.config:
                capital -= sum((float(t.realized_profit or 0.0) for t in Trade.get_trades_proxy(is_open=True))) * float(self.config.get('tradable_balance_ratio', 1.0))
            self._phase_initial_capital = max(0.0, capital)
        profits = sum((float(t.close_profit_abs or 0.0) for t in Trade.get_trades_proxy(pair=pair, is_open=False)))
        return max(0.0, self._phase_initial_capital / self._slots() + profits)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake, min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fraction = 1.0 if entry_tag == 'phase_full_entry' else self.EARLY_EXPOSURE
        fee = 0.001 if self.config.get('fee') is None else float(self.config['fee'])
        stake = min(fraction * self._pair_budget(pair) / (1 + fee), max_stake)
        return stake if stake >= (min_stake or 0.0) else 0.0

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit, min_stake, max_stake, current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        row = self._last_closed_row(trade.pair, current_time)
        if row is None or pd.isna(row.get('cooldown_btc_strict')) or bool(row['exposure_exit']):
            return None
        desired = 1.0 if bool(row['cooldown_btc_strict']) else self.EARLY_EXPOSURE
        previous = trade.get_custom_data(self.PHASE_KEY)
        if previous is None:
            previous = 1.0 if trade.enter_tag == 'phase_full_entry' else self.EARLY_EXPOSURE
        if previous == desired:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        # Reserved cash includes partial-sale profit once, minus remaining cost and fees.
        cash = max(0.0, self._pair_budget(trade.pair) + float(trade.realized_profit or 0.0) - float(trade.stake_amount) * (1 + fee))
        equity = cash + value
        delta = desired * equity - value
        minimum = max(1.0, min_stake or 0.0)
        if delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, self.PHASE_UP_TAG) if amount >= minimum else None
        sold = -delta
        if sold < minimum or value - sold < minimum or value <= 0:
            return None
        return (-float(trade.stake_amount) * sold / value, self.PHASE_DOWN_TAG)

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        tag = order.ft_order_tag
        if order.ft_order_side == trade.entry_side:
            if tag == self.PHASE_UP_TAG:
                row = self._last_closed_row(pair, current_time)
                value = float(trade.amount) * float(row['close']) if row is not None else 0.0
                cash = max(0.0, self._pair_budget(pair) + float(trade.realized_profit or 0.0) - float(trade.stake_amount) * (1 + float(trade.fee_open)))
                if cash < max(1.0, value * 0.005):
                    trade.set_custom_data(self.PHASE_KEY, 1.0)
            elif trade.get_custom_data(self.PHASE_KEY) is None:
                trade.set_custom_data(self.PHASE_KEY, 1.0 if trade.enter_tag == 'phase_full_entry' else self.EARLY_EXPOSURE)
        elif order.ft_order_side == trade.exit_side and tag == self.PHASE_DOWN_TAG:
            trade.set_custom_data(self.PHASE_KEY, self.EARLY_EXPOSURE)


class BtcTrendFastExitStrategy(BtcTrendPhasedStrategy):
    """Return-preserving drawdown revision of the official phased baseline.

    Full early exposure and exit after one completed weak BTC day. The 14-day
    cooldown and per-coin cash accounting are inherited without modification.
    This full-exposure profile does not trim from 100% to 75% at MA150 changes.
    Comparison: validation/core_hold/drawdown_revision/REPORT.md.
    """

    EARLY_EXPOSURE = 1.0
    TREND_EXIT_DAYS = 1
