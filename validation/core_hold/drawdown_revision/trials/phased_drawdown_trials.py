"""Focused drawdown revisions; official v1 remains unchanged during comparison."""
import pandas as pd
from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendPhasedStrategy

class PhasedCoinGuardBase(BtcTrendPhasedStrategy):
    GUARD_MODE = "alignment"
    GUARD_DAYS = 2

    def populate_indicators(self, dataframe, metadata):
        df = super().populate_indicators(dataframe, metadata)
        if df.empty:
            return df
        weak = (df.close < df.ema50)
        if self.GUARD_MODE == "alignment":
            weak &= df.ema20 < df.ema50
        df["coin_guard_exit"] = weak.rolling(self.GUARD_DAYS).sum() == self.GUARD_DAYS
        return df

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)
        if original:
            return original
        row = self._last_closed_row(pair, current_time)
        if row is not None and pd.notna(row.get("coin_guard_exit")) and bool(row["coin_guard_exit"]):
            return "coin_trend_guard"
        return None

class PhasedGuard75(PhasedCoinGuardBase):
    EARLY_EXPOSURE = 0.75

class PhasedGuard100(PhasedCoinGuardBase):
    EARLY_EXPOSURE = 1.0

class PhasedCloseGuard100(PhasedCoinGuardBase):
    EARLY_EXPOSURE = 1.0
    GUARD_MODE = 'close'

class PhasedFastExit100(BtcTrendPhasedStrategy):
    EARLY_EXPOSURE = 1.0
    TREND_EXIT_DAYS = 1

class PhasedSlowRecovery100(BtcTrendPhasedStrategy):
    EARLY_EXPOSURE = 1.0
    RECOVERY_EMA_DAYS = 20

class PhasedSlowRecovery85(BtcTrendPhasedStrategy):
    EARLY_EXPOSURE = 0.85
    RECOVERY_EMA_DAYS = 20

class PhasedGuardSlow100(PhasedCoinGuardBase):
    EARLY_EXPOSURE = 1.0
    RECOVERY_EMA_DAYS = 20

class PhasedRecoveryConfirm100(BtcTrendPhasedStrategy):
    EARLY_EXPOSURE = 1.0
    def populate_indicators(self, dataframe, metadata):
        df = super().populate_indicators(dataframe, metadata)
        if df.empty:
            return df
        # Require two completed days of recovery below the long average.
        early = df.exposure_entry.fillna(False)
        df["exposure_entry"] = df.cooldown_btc_strict.fillna(False) | (early & early.shift(1, fill_value=False))
        return df


class PhasedFastExit75(BtcTrendPhasedStrategy):
    TREND_EXIT_DAYS = 1

class PhasedFastExit85(BtcTrendPhasedStrategy):
    EARLY_EXPOSURE = 0.85
    TREND_EXIT_DAYS = 1

class PhasedAlignedGuard100(PhasedCoinGuardBase):
    EARLY_EXPOSURE = 1.0

    def populate_entry_trend(self, dataframe, metadata):
        df = super().populate_entry_trend(dataframe, metadata)
        # Weak coin protection only during BTC's early recovery phase.
        blocked = ~df.cooldown_btc_strict.fillna(False) & df.coin_guard_exit.fillna(False)
        df.loc[blocked, "enter_long"] = 0
        return df

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        if row is not None and bool(row.get("cooldown_btc_strict", False)):
            return BtcTrendPhasedStrategy.custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs)
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

class PhasedAlignedGuard75(PhasedAlignedGuard100):
    EARLY_EXPOSURE = 0.75
