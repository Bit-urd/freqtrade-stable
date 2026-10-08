"""Follow-up: top2 entries, two actual slots, shared realized-capital budget.

Original BTC/coin exits and account risk fractions remain unchanged. Unrealized
profits are not treated as spendable capital. Wallet max_stake is a hard limit.
"""
from freqtrade.persistence import Trade
from momentum_selection_strategy import WeeklyTop2CycleRiskStrategy


class WeeklyTop2ConcentratedCycleRiskStrategy(WeeklyTop2CycleRiskStrategy):
    def _pair_budget(self, pair):
        capital = float(self.wallets.get_starting_balance())
        capital += sum(float(t.close_profit_abs or 0) for t in Trade.get_trades_proxy(is_open=False))
        capital += sum(float(t.realized_profit or 0) for t in Trade.get_trades_proxy(is_open=True))
        return max(0., capital) / self._slots()

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._risk_fraction
        previous = trade.get_custom_data(self.STAGE_KEY)
        previous = 1.0 if previous is None else previous
        if desired == previous:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        # Shared budget already includes this trade's realized partial profits.
        cash = max(0., self._pair_budget(trade.pair) - float(trade.stake_amount) * (1 + fee))
        delta = desired * (cash + value) - value
        minimum = max(1., min_stake or 0.)
        tag = self.ORDER_PREFIX + str(desired)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, tag) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, tag)
        return None
