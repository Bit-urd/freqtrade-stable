"""趋势恢复确认对同一笔交易保持有效，避免中期信号反复调仓。"""
import pandas as pd
from loss_budget_strategy import BtcCoinGuardTrendRestoreBudgetStrategy

class BtcCoinGuardLatchedBudgetStrategy(BtcCoinGuardTrendRestoreBudgetStrategy):
    RELEASE_KEY = 'coin_loss_budget_released'

    def _recovered(self, pair, current_time):
        row = self._last_closed_row(pair,current_time)
        signal = row.get('coin_budget_recovered',False) if row is not None else False
        return pd.notna(signal) and bool(signal)

    def _trade_risk_fraction(self, trade, current_time):
        if trade.get_custom_data(self.RELEASE_KEY) is True:
            return self._risk_fraction
        if self._recovered(trade.pair,current_time):
            # 此字段记录已经观察到的收盘趋势确认，不代表订单已成交。
            # 真正成交的风险档位仍由父类order_filled单独记录。
            trade.set_custom_data(self.RELEASE_KEY,True)
            return self._risk_fraction
        return super()._coin_risk_fraction(trade.pair,current_time)

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        super().order_filled(pair,trade,order,current_time,**kwargs)
        if order.ft_order_side == trade.entry_side and self._recovered(pair,current_time):
            trade.set_custom_data(self.RELEASE_KEY,True)

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._trade_risk_fraction(trade, current_time)
        previous = trade.get_custom_data(self.STAGE_KEY)
        if previous is None:
            previous = 1.0
        if desired == previous:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        cash = max(0.0, self._pair_budget(trade.pair) + float(trade.realized_profit or 0.0)
                   - float(trade.stake_amount) * (1 + fee))
        delta = desired * (cash + value) - value
        minimum = max(1.0, min_stake or 0.0)
        tag = self.ORDER_PREFIX + str(desired)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, tag) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, tag)
        return None

