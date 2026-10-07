"""趋势恢复版的两项固定结构试验，不修改 BTC 退出和入场规则。"""
import pandas as pd
from trend_aware_risk_strategy import BtcCoinGuardTrendRecoveryRiskStrategy

class BtcCoinGuardPendingRecoveryStrategy(BtcCoinGuardTrendRecoveryRiskStrategy):
    """冷却期内的恢复事件保留至冷却结束；趋势失效即取消。"""
    def __init__(self, config):
        super().__init__(config)
        self._pending_long_rearm = False

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        previous_support = self._previous_long_support
        super().bot_loop_start(current_time, **kwargs)
        if self._risk_candle != candle:
            return
        if not self._long_trend_supported:
            self._pending_long_rearm = False
        elif not previous_support and self._risk_fraction < 1.0:
            self._pending_long_rearm = True
        allowed = self._last_rearm_candle is None or (candle-self._last_rearm_candle).days >= self.REARM_COOLDOWN_DAYS
        reset = self._pending_long_rearm and self._long_trend_supported and allowed and self._risk_fraction < 1.0
        if reset:
            self._risk_peak = self.risk_trace[-1]['prior_closed_equity']
            self._risk_fraction = 1.0
            self._last_rearm_candle = candle
            self.risk_trace[-1].update(peak=self._risk_peak,drawdown=0.0,risk_fraction=1.0,risk_epoch_reset=True)
        if self._risk_fraction >= 1.0:
            self._pending_long_rearm = False
        self.risk_trace[-1]['pending_long_rearm'] = self._pending_long_rearm
        self.risk_trace[-1]['pending_rearm_executed'] = bool(reset)

class BtcCoinGuardConfirmedCoinExitStrategy(BtcCoinGuardTrendRecoveryRiskStrategy):
    """个币弱势退出同时要求 EMA20 不高于 EMA50，BTC 退出不延迟。"""
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        history = self._history(metadata['pair'], self.timeframe)[['date','close']].copy()
        history['coin_medium_weak'] = history.close.ewm(span=20,adjust=False).mean() <= history.close.ewm(span=50,adjust=False).mean()
        return frame.merge(history[['date','coin_medium_weak']],on='date',how='left')

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = super().custom_exit(pair,trade,current_time,current_rate,current_profit,**kwargs)
        if original != 'coin_trend_to_cash':
            return original
        row = self._last_closed_row(pair,current_time)
        weak = row.get('coin_medium_weak',True) if row is not None else True
        return original if pd.isna(weak) or bool(weak) else None
