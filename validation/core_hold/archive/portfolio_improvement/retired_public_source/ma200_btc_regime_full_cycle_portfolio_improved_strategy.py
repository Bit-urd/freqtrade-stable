"""Research candidate. Original Portfolio remains the official baseline.

Keep MA200, individual EMA alignment and weekly defense. In a strong weekly
trend, reduce a daily alignment failure to half exposure instead of exiting.
Restore only when BTC and the coin confirm strength. Bear tiers are unchanged.
"""
from ma200_btc_regime_full_cycle_portfolio_strategy import (
    Ma200BtcRegimeFullCyclePortfolioStrategy, BEAR_TAG,
)


class BtcPortfolioImprovedStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    RESEARCH_ONLY = True
    EXPOSURE_KEY = 'improved_filled_exposure'
    UP_TAG = 'improved_restore'
    DOWN_TAG = 'improved_reduce'

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        weak = frame.ema20 < frame.ema50
        frame['own_weak_2d'] = weak & weak.shift(1, fill_value=False)
        frame['own_strong'] = ((frame.close > frame.ema20)
                               & (frame.ema20 > frame.ema50)
                               & (frame.ema20 > frame.ema20.shift(1))
                               & (frame.ema50 > frame.ema50.shift(1)))
        return frame

    def _handed_over(self, trade, current_time):
        return trade.enter_tag != BEAR_TAG or self._bull_seen_since_open(
            trade.pair, trade, current_time)

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        if row is None or not self._handed_over(trade, current_time):
            return None
        if bool(row['btc_exit']):
            return 'improved_btc_trend_lost'
        if bool(row['own_weak_2d']) and not bool(row['weekly_bull']):
            return 'improved_coin_daily_weekly_weak'
        return None

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        row = self._last_closed_row(trade.pair, current_time)
        if row is None:
            return None
        if not self._handed_over(trade, current_time):
            return super().adjust_trade_position(
                trade, current_time, current_rate, current_profit, min_stake,
                max_stake, current_entry_rate, current_exit_rate,
                current_entry_profit, current_exit_profit, **kwargs)
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        weekly = bool(row['weekly_bull'])
        # Indicator history is restricted to completed candles; seeing strength
        # is a signal state, while exposure changes are recorded only on fills.
        if weekly:
            trade.set_custom_data(self.WEEKLY_SEEN_KEY, True)
        reduced = bool(row['own_weak_2d']) or (
            not weekly and bool(trade.get_custom_data(self.WEEKLY_SEEN_KEY)))
        strong = bool(row['btc_bull_2d']) and bool(row['own_strong']) and weekly
        previous = trade.get_custom_data(self.EXPOSURE_KEY)
        if previous is None:
            previous = 0.0 if trade.enter_tag == BEAR_TAG else 1.0
        desired = 0.5 if reduced else (1.0 if strong else previous)
        value = float(trade.amount) * current_rate
        slot = self._equity(current_time, trade.pair, current_rate) / self._slots()
        minimum = max(1.0, min_stake or 0.0)
        if desired == 0.5 and previous != 0.5:
            sold = max(0.0, value - 0.5 * slot)
            if sold >= minimum and value - sold >= minimum and value > 0:
                return (-float(trade.stake_amount) * sold / value, self.DOWN_TAG)
        if desired == 1.0 and previous != 1.0:
            fee = float(trade.fee_open)
            top_up = min(max(0.0, slot - value) / (1 + fee), max_stake)
            if top_up >= minimum:
                return (top_up, self.UP_TAG)
        return None

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        if order.ft_order_tag == self.DOWN_TAG and order.ft_order_side == trade.exit_side:
            trade.set_custom_data(self.EXPOSURE_KEY, 0.5)
        elif order.ft_order_tag == self.UP_TAG and order.ft_order_side == trade.entry_side:
            trade.set_custom_data(self.EXPOSURE_KEY, 1.0)
        elif order.ft_order_side == trade.entry_side and trade.enter_tag != BEAR_TAG:
            trade.set_custom_data(self.EXPOSURE_KEY, 1.0)
