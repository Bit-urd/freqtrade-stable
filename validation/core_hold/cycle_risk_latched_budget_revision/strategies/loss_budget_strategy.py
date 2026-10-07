"""亏损序列约束个币风险预算；原账户恢复不能绕过个币约束。"""
import pandas as pd
from freqtrade.persistence import Trade
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardLossBudgetStrategy(BtcCoinGuardCycleRiskStrategy):
    """一笔亏损后目标75%，连续两笔或更多亏损后50%；盈利平仓后解除。"""
    def _loss_streak(self, pair, current_time):
        closed = [t for t in Trade.get_trades_proxy(pair=pair,is_open=False)
                  if t.close_date_utc is not None and t.close_date_utc <= current_time]
        closed.sort(key=lambda t:t.close_date_utc,reverse=True)
        count = 0
        for trade in closed:
            if trade.close_profit_abs is None or float(trade.close_profit_abs) >= 0:
                break
            count += 1
            if count >= 2:
                break
        return count

    def _coin_risk_fraction(self, pair, current_time):
        streak = self._loss_streak(pair,current_time)
        return min(self._risk_fraction, .5 if streak >= 2 else .75 if streak else 1.)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fraction = self._coin_risk_fraction(pair,current_time)
        fee = .001 if self.config.get('fee') is None else float(self.config['fee'])
        amount = min(fraction*self._pair_budget(pair)/(1+fee),max_stake)
        if amount < (min_stake or 0.):
            return 0.
        self._pending_initial_fraction[pair] = fraction
        return amount

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._coin_risk_fraction(trade.pair, current_time)
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


class BtcCoinGuardTrendRestoreBudgetStrategy(BtcCoinGuardLossBudgetStrategy):
    """个币EMA20>EMA50且EMA50上升的趋势确认允许解除亏损预算限制。"""
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe,metadata)
        frame['coin_budget_recovered'] = ((frame.close>frame.ema20) &
            (frame.ema20>frame.ema50) & (frame.ema50>frame.ema50.shift(1)))
        return frame

    def _coin_risk_fraction(self, pair, current_time):
        row = self._last_closed_row(pair,current_time)
        signal = row.get('coin_budget_recovered',False) if row is not None else False
        if pd.notna(signal) and bool(signal):
            return self._risk_fraction
        return super()._coin_risk_fraction(pair,current_time)
