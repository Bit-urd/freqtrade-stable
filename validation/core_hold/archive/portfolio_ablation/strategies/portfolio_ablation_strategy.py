"""Two frozen mechanism experiments; original Portfolio remains official."""
from ma200_btc_regime_full_cycle_portfolio_strategy import (
    Ma200BtcRegimeFullCyclePortfolioStrategy, BEAR_TAG,
)


class BtcPortfolioRecoveryTopUpStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    """Only add a conditional bear-to-bull top-up; preserve all baseline exits."""
    RESTORE_TAG = 'confirmed_handover_restore'
    RESTORE_KEY = 'confirmed_handover_filled'

    def _strong(self, pair, current_time):
        row = self._last_closed_row(pair, current_time)
        if row is None or not bool(row['btc_bull_2d']) or not bool(row['weekly_bull']):
            return False
        frame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        closed = frame.loc[frame.date < self._executing_candle_start(current_time)]
        if len(closed) < 2:
            return False
        previous = closed.iloc[-2]
        return (row['close'] > row['ema20'] > row['ema50']
                and row['ema20'] > previous['ema20']
                and row['ema50'] > previous['ema50'])

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if (trade.enter_tag == BEAR_TAG
                and not trade.get_custom_data(self.RESTORE_KEY)
                and self._strong(trade.pair, current_time)
                and not self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit)):
            slot = self._equity(current_time, trade.pair, current_rate) / self._slots()
            delta = max(0.0, slot - float(trade.amount) * current_rate)
            amount = min(delta / (1 + float(trade.fee_open)), max_stake)
            if amount >= max(1.0, min_stake or 0.0):
                return (amount, self.RESTORE_TAG)
            # Remain retryable if cash/exchange minimum prevented a top-up.
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit,
            current_exit_profit, **kwargs)

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        if order.ft_order_tag == self.RESTORE_TAG and order.ft_order_side == trade.entry_side:
            trade.set_custom_data(self.RESTORE_KEY, True)


class BtcPortfolioPullbackTrimStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    """Only replace ordinary full exits with a half-position and recovery.

    No bear-handover top-up. Weekly adjustments otherwise follow the baseline.
    """
    TRIM_KEY = 'pullback_trim_filled'
    TRIM_TAG = 'pullback_half'
    RESTORE_TAG = 'pullback_restore'

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)
        row = self._last_closed_row(pair, current_time)
        if original and row is not None and bool(row['weekly_bull']) and not bool(row['btc_exit']):
            return None
        return original

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        row = self._last_closed_row(trade.pair, current_time)
        original_exit = super().custom_exit(trade.pair, trade, current_time, current_rate, current_profit)
        trimmed = bool(trade.get_custom_data(self.TRIM_KEY))
        if row is not None and original_exit and bool(row['weekly_bull']) and not bool(row['btc_exit']):
            if not trimmed:
                value = float(trade.amount) * current_rate
                minimum = max(1.0, min_stake or 0.0)
                if value / 2 >= minimum:
                    return (-float(trade.stake_amount) / 2, self.TRIM_TAG)
            return None
        if trimmed:
            if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
                return None
            # Restore only the exposure reduced by this experiment.
            strong = BtcPortfolioRecoveryTopUpStrategy._strong(self, trade.pair, current_time)
            if strong:
                slot = self._equity(current_time, trade.pair, current_rate) / self._slots()
                amount = min(max(0.0, slot - float(trade.amount) * current_rate)
                             / (1 + float(trade.fee_open)), max_stake)
                if amount >= max(1.0, min_stake or 0.0):
                    return (amount, self.RESTORE_TAG)
            return None
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit,
            current_exit_profit, **kwargs)

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        if order.ft_order_tag == self.TRIM_TAG and order.ft_order_side == trade.exit_side:
            trade.set_custom_data(self.TRIM_KEY, True)
        elif order.ft_order_tag == self.RESTORE_TAG and order.ft_order_side == trade.entry_side:
            trade.set_custom_data(self.TRIM_KEY, False)
