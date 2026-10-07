"""新正式版：BTC 新一轮连续两天站上 MA200 时恢复风险仓位。

全历史峰值回撤控制可能使策略在恢复行情中长期维持低仓位。
新的多头确认事件允许开启新一轮风险控制，两次重置至少相隔 14 天。
确认和重置只使用已经收盘的日线。报告最大回撤始终以原账户历史
最高权益计算，不使用重置后的内部风控峰值美化结果。
已正式选定用于 BTC/SOL/ETH；实盘重启状态持久化尚未实现。
"""
import pandas as pd
from equity_risk_strategy import BtcCoinGuardEquityRiskStrategy

class BtcCoinGuardCycleRiskStrategy(BtcCoinGuardEquityRiskStrategy):
    REARM_COOLDOWN_DAYS = 14

    def __init__(self, config):
        super().__init__(config)
        self._previous_bull = False
        self._last_rearm_candle = None

    def _btc_bull_confirmed(self, current_time):
        history = self._history(self.BTC_PAIR, self.timeframe)
        close = history.loc[history['date'] < self._executing_candle_start(current_time), 'close']
        if len(close) < 201:
            return False
        return bool((close.iloc[-2:] > close.rolling(200).mean().iloc[-2:]).all())

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        super().bot_loop_start(current_time, **kwargs)
        if self._risk_candle != candle:
            return
        bull = self._btc_bull_confirmed(current_time)
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
