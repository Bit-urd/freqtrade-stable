"""固定结构试验：长期趋势有效时，不因账户普通回调追加减仓。"""
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardTrendAwareRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    def __init__(self, config):
        super().__init__(config)
        self._long_trend_supported = False
        self._support_days = 0

    def _closed_long_trend_supported(self, current_time):
        # 账户规则对所有币一致，不针对 SOL 另设参数。
        if not self._btc_bull_confirmed(current_time):
            return False
        pairs = self.dp.current_whitelist()
        if not pairs:
            return False
        good = 0
        for pair in pairs:
            history = self._history(pair, self.timeframe)
            close = history.loc[history['date'] < self._executing_candle_start(current_time), 'close']
            if len(close) < 150:
                return False
            ma = close.rolling(150).mean().iloc[-1]
            ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
            ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
            good += int(close.iloc[-1] > ma and ema20 > ema50)
        # 多币组合要求至少三分之二的币长期趋势仍有效，单币要求该币有效。
        return good * 3 >= len(pairs) * 2

    def next_fraction(self, previous, drawdown):
        desired = super().next_fraction(previous, drawdown)
        if self._long_trend_supported and desired < previous:
            return previous
        return desired

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        supported = self._closed_long_trend_supported(current_time)
        self._support_days = self._support_days + 1 if supported else 0
        self._long_trend_supported = self._support_days >= 2
        super().bot_loop_start(current_time, **kwargs)
        if self._risk_candle == candle:
            self.risk_trace[-1]['long_trend_supported'] = self._long_trend_supported


class BtcCoinGuardTrendRecoveryRiskStrategy(BtcCoinGuardTrendAwareRiskStrategy):
    """仅追加长期趋势重新确认后恢复风险，保留 14 天重置间隔。"""
    def __init__(self, config):
        super().__init__(config)
        self._previous_long_support = False

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        super().bot_loop_start(current_time, **kwargs)
        if self._risk_candle != candle:
            return
        allowed = self._last_rearm_candle is None or (candle-self._last_rearm_candle).days >= self.REARM_COOLDOWN_DAYS
        reset = self._long_trend_supported and not self._previous_long_support and allowed and self._risk_fraction < 1.0
        if reset:
            self._risk_peak = self.risk_trace[-1]['prior_closed_equity']
            self._risk_fraction = 1.0
            self._last_rearm_candle = candle
            self.risk_trace[-1].update(peak=self._risk_peak,drawdown=0.0,risk_fraction=1.0,risk_epoch_reset=True)
        self.risk_trace[-1]['long_trend_rearm'] = bool(reset)
        self._previous_long_support = self._long_trend_supported
