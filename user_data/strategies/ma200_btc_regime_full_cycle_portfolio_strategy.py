"""BTC 定牛熊的全周期多币组合策略：牛市趋势做多 + 熊市分档囤币（2026-09-24 加入，2026-09-25 提升为正式策略）。

把两个策略放进同一个账户、同一笔钱：
- BTC 在 MA200 上方（牛市）：Ma200BtcRegimeWeeklySizedPortfolioStrategy 的规则，加改动 3。
- BTC 在 MA200 下方（熊市）：Ma200BtcBearAccumulationStrategy（已归档到 archive/strategies/）的规则，加改动 1。
把 HANDOVER_TO_BULL、BULL_ENTRY_FULL 都设成 False 并关掉任意一边（BULL_ENABLED / BEAR_ENABLED），
结果跟原策略完全一样（已验证）。

牛市部分（开仓标签 bull_*）：
- 进场：BTC 收盘 > BTC MA200，且该币 收盘 > EMA20 > EMA50、两条 EMA 都在上升；
  该币至少有 startup_candle_count 根自己的日线。
- 仓位：槽位 = 账户市值 / max_open_trades。开仓直接满槽位（改动 3，BULL_ENTRY_FULL）；
  持仓期间周线 EMA20 > EMA50 出现过一次之后，周线转空减到半槽位、再转多补回满槽位。
  原策略开仓时周线还没转多就只买半槽位，牛市刚开始时仓位不够。
- 退出：BTC 收盘 < BTC MA200，或该币 EMA20 < EMA50，连续 2 根完整日线成立。

熊市部分（开仓标签 bear_accumulate）：
- 买入：BTC 收盘 < MA200 连续 2 天后，按 BTC 相对 MA200 的偏离率分档，累计投入资金：
  -10% → 20%，-20% → 40%，-30% → 60%，-40% → 80%，-50% → 100%（BEAR_TIERS）。
  只加不减，按成本算（资金 = 现金 + 持仓成本）。每个币等权：1 / max_open_trades。
- 卖出（改动 1，HANDOVER_TO_BULL）：BTC 站回 MA200 时不卖，交给牛市部分，按牛市的退出规则卖
  （BTC 转熊或该币死叉）。原策略站回 MA200 就全部卖出，2023-01 把 2022 年熊市囤的 BTC 卖在
  20953，第二天牛市部分又重新买。交接过去的仓位保持原来大小，不补到满槽位。
- 同一轮熊市里某个币被止损过（归零、崩盘），就不再买它，直到 BTC 站回 MA200
  （confirm_trade_entry）。2022-05 LUNA 被止损后原规则会接着买。
- 新币要有 60 根自己的日线才参与（原熊市囤币策略 30 根），跟牛市部分统一，回测和实盘一致。
- 可选：BEAR_PAIRS 限制熊市只囤哪些币；BEAR_TIER_BASIS = "ath" 改成按 BTC 距历史最高价的
  跌幅分档（改动 2，没有采用，见验证报告）。

同一个币同一时间只能有一笔持仓，所以用开仓标签区分，退出和加仓在 custom_exit 和
adjust_trade_position 里按标签分开处理。

指标数据：回测和画图时 BTC 日线、各币日线和周线都从数据目录读完整历史（同两个原策略），
dry-run 和实盘用 DataProvider。数据目录里必须有 BTC/USDT 日线数据。

验证结论（../validation/ma200_btc_regime_full_cycle_fixes_20260924/REPORT.md、ROLL2Y_ALL.md；
现货，1000 USDT，手续费 0.1%，逐日盯市，6 个币池，全部样本内）：
- 2018 年以来等长两年窗口（每季度一个起点，156 个窗口）：收益中位数 +156%，最差 -45%，
  亏钱窗口 8%，回撤中位数 -36%，最差回撤 -71%。79% 的窗口比改动前收益高（净值倍数中位数
  1.11），回撤不变；71% 的窗口收益高于持有 BTC，75% 回撤更浅。
- 2023～2024 年起点（42 个窗口）：+126% / -33%，最差 0%，最差回撤 -39%；但持有 BTC 是
  +190% / -28%，只有 43% 的窗口跑赢持有 BTC。
- 弱点：两年里碰上 2022 年那种深熊（2021～2022 起点）时，最差 -45%、回撤 -71%；
  改动 2（按距历史最高价跌幅分档）在这种情况下好很多（最差 -24%），但 2023 年以后更差。
- 固定 11 币（BTC ETH BNB SOL PEPE AAVE PUMP UNI ADA XRP SUI）2023-01 → 2026-09：
  +345% / -39%（改动前 +156% / -39%，持有 BTC +388% / -53%），11 个币全部比改动前更赚钱。
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
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair, timeframe_to_prev_date
from pandas import DataFrame


logger = logging.getLogger(__name__)

BULL_TAG = "bull_btc_regime_ema_alignment"
BEAR_TAG = "bear_accumulate"


class Ma200BtcRegimeFullCyclePortfolioStrategy(IStrategy):
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
        dataframe["btc_exit"] = dataframe["btc_below"] & dataframe["btc_below"].shift(1, fill_value=False)

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
                & (dataframe["ema20"] > dataframe["ema50"])
                & (dataframe["ema20"] > dataframe["ema20"].shift(1))
                & (dataframe["ema50"] > dataframe["ema50"].shift(1))
                & has_volume
            )
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
        return "bull_btc_regime_or_alignment_lost" if bool(row["bull_exit"]) else None

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
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None
        rows = dataframe.loc[dataframe["date"] <= current_time]
        if rows.empty:
            return None
        return 1.0 if bool(rows.iloc[-1]["weekly_bull"]) else 0.5

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
    ) -> float | None:
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if trade.enter_tag == BEAR_TAG:
            handed_over = (self.HANDOVER_TO_BULL and self.HANDOVER_TOP_UP
                           and self._bull_seen_since_open(trade.pair, trade, current_time))
            if not handed_over:
                top_up = self._bear_target_cost(trade.pair, current_time) - float(trade.stake_amount)
                # 差额很小（手续费、精度误差）时不补
                if top_up < max(1.0, min_stake or 0):
                    return None
                return min(top_up, max_stake)
            if not trade.get_custom_data(self.HANDOVER_KEY):
                # 交接第一天补到满槽位，之后跟牛市仓位一样按周线调仓
                trade.set_custom_data(self.HANDOVER_KEY, True)
                trade.set_custom_data(self.TARGET_KEY, 1.0)
                top_up = (
                    self._equity(current_time, trade.pair, current_rate) / self._slots()
                    - float(trade.amount) * current_rate
                )
                if top_up < 1.0:
                    return None
                return min(top_up, max_stake)

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
