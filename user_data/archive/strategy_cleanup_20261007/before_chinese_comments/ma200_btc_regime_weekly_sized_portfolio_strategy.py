"""BTC 定牛熊 + 各币自己的 EMA/周线的多币组合策略（候选策略，2026-09-23 加入）。

思路：牛熊只看 BTC 日线 MA200，EMA20/50 排列和周线仓位用每个币自己的数据。
- 新币不用等攒够 200 根日线：自己有 60 根日线（startup_candle_count）就能交易，
  上线约 2 个月。这个门槛在进场条件里显式检查，实盘和回测一致。
- BTC 代表币圈整体的资金环境：BTC 不在牛市时，小币自己走出来的多头排列也不做，
  用来过滤小币的错误信号。

规则（跟组合版正式策略相比，只换了 MA200 的来源）：
- 进场：BTC 日线收盘 > BTC MA200，且该币 收盘 > EMA20 > EMA50、两条 EMA 都在上升。
- 退出：BTC 收盘 < BTC MA200，或该币 EMA20 < EMA50，连续 2 根完整日线成立。
  BTC 当天数据缺失时既不算牛也不算熊：不进场，也不因为 BTC 触发退出。
- 仓位：该币自己的周线 EMA20 > EMA50 时满槽位，否则半槽位；槽位 = 账户市值 /
  max_open_trades；只在周线目标翻转时调仓（跟组合版一样）。

指标数据：startup_candle_count 只有 60，Freqtrade 回测只会在区间前多加载 60 根，不够算
BTC 的 MA200，EMA 的起算点也会随回测区间变化（跟实盘不一致）。所以回测和画图模式下，
BTC 日线、各币日线和周线都从数据目录读完整历史算指标，再按日期合并（只用到当根及之前的
收盘价，没有未来数据）。dry-run 和实盘时用正常的 DataProvider：币安首次下载 1000 根，
日线 EMA50 已收敛，周线基本是全部历史。数据目录里必须有 BTC/USDT 的日线数据，即使
BTC 不在交易币池里。

止损：-99%（等于不设），风控靠上面的退出规则。固定比例、按趋势分档、盘中、插针小止损
+ADX、市场广度减仓都测过，全部不如"直接少投资金"（REVIEW_20260923.md 第七节、
extra_checks/stoploss*/、extra_checks/breadth/）。

使用场景：
- 多币共用一个账户，币池是币安成交额靠前的主流币（大约前 10～20 名），比如
  BTC ETH BNB SOL PEPE XRP ADA SUI。成交额靠后的小币没有测过，不要用。
- 想让币池跟着 BTC 大环境走，熊市尽量完全空仓（BTC 在 MA200 下方时一笔都不开）。
- 不适合想吃"小币独立行情"的场景：BTC 走弱时，小币的独立上涨也会被一起放弃。
- 资金按最大回撤 -60% 准备（时点币池的结果）；觉得太大就只投入一部分资金。

验证结论（../validation/ma200_btc_regime_20260923/REPORT.md 和 REVIEW_20260923.md，
跟组合版正式策略同币池、同日期对比，10 币 / BTC+ETH+BNB+XRP / BTC+ETH+SOL 三个组合
x 五个区间）：
- 15 组里收益更好 11 组，打平 1 组，更差 3 组；回撤 9 组更小、1 组持平、5 组更深；
  手续费提到 0.3%（模拟滑点）后仍是 11 组更好。
- 优势主要来自新币提前进场，不是 BTC 过滤本身：把新币门槛改成 210 根（跟组合版一样）
  后，10 币全周期 +8218%，低于组合版的 +9532%；牛市区间 3 个组合全部跑输组合版。
  BTC 过滤本身的价值集中在熊市和 2024 年至今。
- 熊市（2022 年）三个组合都是 0 笔交易、0% 亏损（原组合版 -7%～-10%）。
- 新币提前约 2～5 个月参与：UNI 首笔交易 2020-11（原来 2021-04），SOL 2021-01（原来
  2021-03），ARB 2023-07（原来 2023-12）。
- 小组合受益最大：BTC+ETH+SOL 全周期 +4417%（原组合版 +2024%）。
- 时点币池（每年 1 月 1 日按成交额取前 10，含后来归零的 LUNA、EOS 等，逐年复利，
  2019-01 -> 2026-09）：+771%，等权持有 +904%；最大回撤 -59.6%，持有 -85.3%。
  手挑币池会把收益放大 15～30 倍，但"回撤远小于持有"的结论成立。
- 81 个月度滚动起点：回撤全部小于持有；但 2023 年以后起步的收益全部跑输等权持有
  （持有的收益几乎全来自 ZEC），去掉 ZEC 后 32/33 个起点跑赢、0 个亏钱。
- BTC ETH BNB SOL PEPE 五币：2023-07 到 2025-07 的 5 个起点收益都不低于持有，
  回撤 -18%～-50%（持有 -62%～-78%）。
- 崩盘：LUNA（2022-05）和 OM（2025-04-13 一根 4h 跌 94%）崩盘时 BTC 已在 MA200 下方，
  本策略已空仓。

已知局限：
- BTC 跌破 MA200 时会清掉所有小币。2025-10-17 BTC 跌破 MA200，ZEC 那一笔在 +421% 时
  就平掉了，原组合版一直持有到 +1105%。所以 10 币组合的牛熊交替区间变差（+91% 对 +137%）。
- 2021 年年中 BTC 有 98 天在 MA200 下方，所有币一起清仓再一起重新进场，10 币组合在
  牛市区间收益变差（+1809% 对 +2439%），但回撤更小（-23.9% 对 -32.4%）。
- 新币的周线 EMA20/50 从上线价格开始算，上线第一年的周线仓位信号比较粗糙。
- 新币提前进场只在 SOL、UNI、ARB 这几个事后挑出来的币上验证过，没有测过上线后一路
  下跌的新币。
- 如果某个币在 BTC 牛市里突然归零（跑路、被盗），要等 EMA 死叉再连续 2 天确认才退出，
  这个仓位基本亏光；账户损失 = 它当时的占比。赢家不减仓，单币最高占过 37%（时点币池）、
  57%（手挑 10 币）。单币仓位上限还没有实现。
- 快速暴跌挡不住：时点币池 2021 年的回撤是 -52%。
- 时点币池的候选池（33 个币）仍是人选的；全部是样本内结果，还没有 dry-run。
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


class Ma200BtcRegimeWeeklySizedPortfolioStrategy(IStrategy):
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
    TARGET_KEY = "weekly_target"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self._history_cache: dict[tuple[str, str], DataFrame] = {}

    def informative_pairs(self):
        pairs = [(pair, "1w") for pair in self.dp.current_whitelist()]
        return pairs + [(self.BTC_PAIR, self.timeframe)]

    def _history(self, pair: str, timeframe: str) -> DataFrame:
        """指标用的完整历史。回测只会在区间前多加载 startup_candle_count 根，EMA 的起算点会随
        回测区间变化，所以回测和画图时从数据目录读完整历史；实盘用 DataProvider（币安首次
        下载 1000 根，日线 EMA50 已经收敛，周线基本就是全部历史）。指标只用到当根及之前的
        收盘价，再按日期合并，没有未来数据。"""
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
        # 牛市和熊市都要 BTC 数据明确给出：BTC 当天的 K 线缺失（实盘里晚到）或 MA200 还没算出来时，
        # 两者都是 False，既不进场也不因为"BTC 转熊"触发退出。
        btc["btc_bull"] = btc["close"] > btc["btc_ma200"]
        btc["btc_bear"] = btc["close"] < btc["btc_ma200"]
        dataframe = dataframe.merge(
            btc[["date", "btc_ma200", "btc_bull", "btc_bear"]], on="date", how="left"
        )
        if pd.isna(dataframe["btc_ma200"].iloc[-1]):
            logger.warning("%s: BTC 日线缺少 %s 的数据，本根 K 线不进场也不按 BTC 退出",
                           metadata["pair"], dataframe["date"].iloc[-1])
        dataframe["btc_bull"] = dataframe["btc_bull"].astype("boolean").fillna(False).astype(bool)
        dataframe["btc_bear"] = dataframe["btc_bear"].astype("boolean").fillna(False).astype(bool)

        weekly = self._history(metadata["pair"], "1w")
        weekly["ema20_w"] = weekly["close"].ewm(span=20, adjust=False).mean()
        weekly["ema50_w"] = weekly["close"].ewm(span=50, adjust=False).mean()
        weekly["weekly_bull"] = weekly["ema20_w"] > weekly["ema50_w"]
        dataframe = merge_informative_pair(dataframe, weekly, self.timeframe, "1w", ffill=True)
        dataframe["weekly_bull"] = dataframe["weekly_bull_1w"].fillna(False)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 回测会切掉每个币最前面 startup_candle_count 根 K 线，实盘不会。新币在实盘里上线第二天
        # EMA 就能满足排列，所以这里显式要求至少有这么多根自己的日线，实盘和回测才一致。
        warmed_up = dataframe["own_candles"] > self.startup_candle_count
        aligned = (
            warmed_up
            & dataframe["btc_bull"]
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["ema20"] > dataframe["ema20"].shift(1))
            & (dataframe["ema50"] > dataframe["ema50"].shift(1))
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[aligned, ["enter_long", "enter_tag"]] = [1, "btc_regime_ema_alignment"]
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        invalid = dataframe["btc_bear"] | (dataframe["ema20"] < dataframe["ema50"])
        confirmed = invalid & invalid.shift(1).fillna(False)
        dataframe.loc[confirmed, ["exit_long", "exit_tag"]] = [1, "btc_regime_or_alignment_lost"]
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
