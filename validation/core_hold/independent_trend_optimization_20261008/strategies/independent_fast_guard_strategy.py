"""Second-stage ablation: retain only exceptions with intact short coin momentum.

Added after observing the medium-trend exception's false-break losses. Parameters
are shared across all assets; this is retrospective validation, not a holdout.
"""
from independent_cycle_risk_strategy import IndependentHoldCycleRiskStrategy


class IndependentFastGuardCycleRiskStrategy(IndependentHoldCycleRiskStrategy):
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        history = self._history(metadata["pair"], self.timeframe)
        ema10 = history.close.ewm(span=10, adjust=False).mean()
        valid = (history.close > ema10) & (ema10 > ema10.shift(1))
        short_guard = dict(zip(history.date, valid))
        frame["independent_strong"] &= frame.date.map(short_guard).fillna(False)
        return frame
