"""Fixed delta: rearm risk after a new BTC MA200 two-day bull confirmation.

All-time drawdown control can lock reduced exposure through recovery. A new
bull transition permits a fresh risk epoch; resets are at least 14 days apart.
The reset uses only prior completed candles. Reported maximum drawdown always
uses the original account high-water mark, never the reset internal risk peak.
Research only: live restart persistence is not implemented.
"""
import pandas as pd
from equity_risk_strategy import BtcCoinGuardEquityRiskStrategy

class BtcCoinGuardCycleRiskStrategy(BtcCoinGuardEquityRiskStrategy):
    REARM_COOLDOWN_DAYS = 14

    def __init__(self, config):
        super().__init__(config)
        self._previous_bull = False
        self._last_rearm_candle = None

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        super().bot_loop_start(current_time, **kwargs)
        if self._risk_candle != candle:
            return
        row = self._last_closed_row(self.BTC_PAIR, current_time)
        signal = row.get('btc_bull_2d', False) if row is not None else False
        bull = pd.notna(signal) and bool(signal)
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
