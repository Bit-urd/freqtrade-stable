"""Research variants: BTC exposure caps plus confirmed absolute/relative strength.

All indicators use completed daily candles; breakout levels exclude today's high.
Variants share parameters across coins. Production strategies remain untouched.
"""
import pandas as pd
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy


class IndependentHoldCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    ALLOW_INDEPENDENT_ENTRY = False
    ALLOW_PROBE_PROMOTION = False
    WEAK_HOLD_CAP = 0.5
    PROBE_CAP = 0.25
    PROBE_TAG = "independent_probe"

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        coin = self._history(metadata["pair"], self.timeframe).copy()
        btc = self._history(self.BTC_PAIR, self.timeframe)[["date", "close"]]
        coin = coin.merge(btc.rename(columns={"close": "btc_close"}), on="date", how="left")
        ema20 = coin.close.ewm(span=20, adjust=False).mean()
        ema50 = coin.close.ewm(span=50, adjust=False).mean()
        relative = coin.close / coin.btc_close
        rs20 = relative.ewm(span=20, adjust=False).mean()
        rs50 = relative.ewm(span=50, adjust=False).mean()
        strong = ((coin.close > ema20) & (ema20 > ema50)
                  & (ema20 > ema20.shift(1)) & (ema50 > ema50.shift(1))
                  & (relative > rs20) & (rs20 > rs50)
                  & (rs20 > rs20.shift(1)) & (rs50 > rs50.shift(1)))
        level = coin.high.shift(1).rolling(20).max()
        confirmed = ((coin.close.shift(1) > level.shift(1))
                     & (coin.close > level.shift(1)))
        # A confirmed breakout remains valid while both trends remain strong.
        # Requiring a fresh breakout every day would prematurely revoke the exception.
        active = False
        flags = []
        for alive, trigger in zip(strong.fillna(False), confirmed.fillna(False)):
            active = bool(alive) and (active or bool(trigger))
            flags.append(active)
        coin["independent_strong"] = flags
        if metadata["pair"] == self.BTC_PAIR:
            coin["independent_strong"] = False
        return frame.merge(coin[["date", "independent_strong"]], on="date", how="left")

    @staticmethod
    def _flag(row, key):
        value = row.get(key, False)
        return pd.notna(value) and bool(value)

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        if self.ALLOW_INDEPENDENT_ENTRY and metadata["pair"] != self.BTC_PAIR:
            probe = ((frame.own_candles > self.startup_candle_count)
                     & (frame.volume > 0) & frame.independent_strong.fillna(False)
                     & frame.coin_risk_on.fillna(False)
                     & ~frame.exposure_entry.fillna(False))
            frame.loc[probe, ["enter_long", "enter_tag"]] = [1, self.PROBE_TAG]
        return frame

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return None
        if self._flag(row, "exposure_exit"):
            if pair != self.BTC_PAIR and self._flag(row, "independent_strong"):
                return "coin_trend_to_cash" if self._flag(row, "coin_risk_off") else None
            return "trend_to_cash"
        return "coin_trend_to_cash" if self._flag(row, "coin_risk_off") else None

    def _probe_confirmed(self, trade, current_time):
        if not self.ALLOW_PROBE_PROMOTION:
            return False
        frame, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        held = frame.loc[(frame.date >= trade.open_date_utc)
                         & (frame.date < self._executing_candle_start(current_time))]
        return len(held) >= 3 and bool(held.independent_strong.iloc[-3:].all())

    def _desired_fraction(self, pair, current_time, trade=None, entry_tag=None):
        row = self._last_closed_row(pair, current_time)
        if pair == self.BTC_PAIR or row is None or not self._flag(row, "exposure_exit"):
            return self._risk_fraction
        cap = self.WEAK_HOLD_CAP
        tag = trade.enter_tag if trade is not None else entry_tag
        if tag == self.PROBE_TAG:
            cap = self.PROBE_CAP
            if trade is not None and self._probe_confirmed(trade, current_time):
                cap = self.WEAK_HOLD_CAP
        # The independent exception cannot exceed the account's risk cap.
        return min(self._risk_fraction, cap)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fraction = self._desired_fraction(pair, current_time, entry_tag=entry_tag)
        fee = .001 if self.config.get("fee") is None else float(self.config["fee"])
        amount = min(fraction * self._pair_budget(pair) / (1 + fee), max_stake)
        if amount < (min_stake or 0):
            return 0.0
        self._pending_initial_fraction[pair] = fraction
        return amount

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._desired_fraction(trade.pair, current_time, trade=trade)
        previous = trade.get_custom_data(self.STAGE_KEY)
        previous = 1.0 if previous is None else previous
        if desired == previous:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        cash = max(0.0, self._pair_budget(trade.pair) + float(trade.realized_profit or 0)
                   - float(trade.stake_amount) * (1 + fee))
        delta = desired * (cash + value) - value
        minimum = max(1.0, min_stake or 0)
        tag = self.ORDER_PREFIX + str(desired)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, tag) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, tag)
        return None


class IndependentProbeCycleRiskStrategy(IndependentHoldCycleRiskStrategy):
    ALLOW_INDEPENDENT_ENTRY = True


class IndependentPromoteCycleRiskStrategy(IndependentProbeCycleRiskStrategy):
    ALLOW_PROBE_PROMOTION = True
