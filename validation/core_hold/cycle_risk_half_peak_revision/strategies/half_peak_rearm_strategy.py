"""固定防守试验：风险恢复时只下调一半权益峰值，保留部分回撤记忆。"""
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardHalfPeakRearmStrategy(BtcCoinGuardCycleRiskStrategy):
    """入场退出及恢复事件不变，恢复后的内部峰值取旧峰值与当前权益中点。"""
    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        previous_peak = self._risk_peak
        super().bot_loop_start(current_time,**kwargs)
        if self._risk_candle != candle or previous_peak is None:
            return
        trace = self.risk_trace[-1]
        if trace.get('risk_epoch_reset'):
            equity = trace['prior_closed_equity']
            self._risk_peak = max(equity,(previous_peak+equity)/2)
            trace.update(peak=self._risk_peak,drawdown=max(0.0,1-equity/self._risk_peak),half_peak_rearm=True)
