"""Frozen research: separate confirmed bull, recovery/range and cash defense.

No bear accumulation, leverage or calendar regime labels. Use existing BTC
MA200 two-day confirmation and existing MA150/EMA10 support. Range entries
require the coin's original EMA20/50 alignment; full bull uses coin guard.
"""
from portfolio_regime_switch_strategy import BtcPortfolioRegimeSwitchStrategy
from ma200_btc_regime_full_cycle_portfolio_strategy import Ma200BtcRegimeFullCyclePortfolioStrategy

class BtcPortfolioNoBearSwitchStrategy(BtcPortfolioRegimeSwitchStrategy):
    """One-change control: previous two-mode switch without bear accumulation."""
    BEAR_ENABLED = False

class BtcPortfolioThreeRegimeStrategy(BtcPortfolioRegimeSwitchStrategy):
    BEAR_ENABLED = False
    RANGE_TAG = 'hybrid_range_alignment'

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        frame['mode_down'] = frame.guard_btc_off.fillna(False)
        frame['mode_bull'] = frame.hybrid_bull.fillna(False) & frame.guard_btc_on.fillna(False)
        frame['mode_range'] = (frame.guard_btc_on.fillna(False) & ~frame.mode_bull & ~frame.mode_down)
        frame['range_alignment'] = ((frame.close > frame.ema20) & (frame.ema20 > frame.ema50)
            & (frame.ema20 > frame.ema20.shift(1)) & (frame.ema50 > frame.ema50.shift(1)))
        weak = frame.ema20 < frame.ema50
        frame['own_weak_2d'] = weak & weak.shift(1, fill_value=False)
        return frame

    def populate_entry_trend(self, dataframe, metadata):
        frame = dataframe
        frame['enter_long'] = 0
        frame['enter_tag'] = None
        warm = (frame.own_candles > self.startup_candle_count) & (frame.volume > 0)
        bull = warm & frame.mode_bull & frame.guard_coin_on.fillna(False)
        recovery = warm & frame.mode_range & frame.range_alignment.fillna(False)
        frame.loc[bull, ['enter_long', 'enter_tag']] = [1, self.GUARD_TAG]
        frame.loc[recovery, ['enter_long', 'enter_tag']] = [1, self.RANGE_TAG]
        return frame

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return None
        if self._flag(row, 'mode_down'):
            return 'hybrid_downtrend_cash'
        if self._flag(row, 'mode_bull'):
            return 'hybrid_bull_coin_weak' if self._flag(row, 'guard_coin_off') else None
        if self._flag(row, 'mode_range') and (
                self._flag(row, 'own_weak_2d') or self._flag(row, 'guard_coin_off')):
            return 'hybrid_range_alignment_lost'
        return None

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        row = self._last_closed_row(trade.pair, current_time)
        if row is None or self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        if self._flag(row, 'mode_bull'):
            return super().adjust_trade_position(
                trade, current_time, current_rate, current_profit, min_stake, max_stake,
                current_entry_rate, current_exit_rate, current_entry_profit,
                current_exit_profit, **kwargs)
        if self._flag(row, 'mode_range'):
            trade.set_custom_data(self.GUARD_FILLED_KEY, False)
            return Ma200BtcRegimeFullCyclePortfolioStrategy.adjust_trade_position(
                self, trade, current_time, current_rate, current_profit, min_stake,
                max_stake, current_entry_rate, current_exit_rate,
                current_entry_profit, current_exit_profit, **kwargs)
        return None

class BtcPortfolioHalfRecoveryStrategy(BtcPortfolioRegimeSwitchStrategy):
    """Fixed compromise: half exposure on recovery, full in confirmed bull.

    Preserve cash exits and prohibit bear accumulation. Only existing BTC/coin
    MA150/EMA10 support permits risk; BTC MA200 two-day confirmation sets size.
    """
    BEAR_ENABLED = False
    EARLY_TAG = 'half_recovery_entry'
    UP_TAG = 'half_recovery_full'
    DOWN_TAG = 'half_recovery_reduce'
    STAGE_KEY = 'half_recovery_filled_stage'

    def populate_entry_trend(self, dataframe, metadata):
        frame = dataframe
        frame['enter_long'] = 0
        frame['enter_tag'] = None
        allowed = (frame.guard_btc_on.fillna(False) & frame.guard_coin_on.fillna(False)
                   & (frame.own_candles > self.startup_candle_count) & (frame.volume > 0))
        frame.loc[allowed & frame.hybrid_bull.fillna(False), ['enter_long', 'enter_tag']] = [1, self.GUARD_TAG]
        frame.loc[allowed & ~frame.hybrid_bull.fillna(False), ['enter_long', 'enter_tag']] = [1, self.EARLY_TAG]
        return frame

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fraction = 0.5 if entry_tag == self.EARLY_TAG else 1.0
        fee = 0.001 if self.config.get('fee') is None else float(self.config['fee'])
        amount = min(fraction * self._equity(current_time, pair, current_rate)
                     / self._slots() / (1 + fee), max_stake)
        return amount if amount >= (min_stake or 0.0) else 0.0

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        return 'half_recovery_to_cash' if self._flag(row, 'guard_btc_off') or self._flag(row, 'guard_coin_off') else None

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        row = self._last_closed_row(trade.pair, current_time)
        if row is None or self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = 1.0 if self._flag(row, 'hybrid_bull') else 0.5
        previous = trade.get_custom_data(self.STAGE_KEY)
        if previous is None:
            previous = 0.5 if trade.enter_tag == self.EARLY_TAG else 1.0
        if previous == desired:
            return None
        value = float(trade.amount) * current_rate
        slot = self._equity(current_time, trade.pair, current_rate) / self._slots()
        delta = desired * slot - value
        minimum = max(1.0, min_stake or 0.0)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + float(trade.fee_open)), max_stake)
            return (amount, self.UP_TAG) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, self.DOWN_TAG)
        return None

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        if order.ft_order_side == trade.entry_side:
            fraction = 0.5 if order.ft_order_tag == self.EARLY_TAG else 1.0
            trade.set_custom_data(self.STAGE_KEY, fraction)
        elif order.ft_order_tag == self.DOWN_TAG and order.ft_order_side == trade.exit_side:
            trade.set_custom_data(self.STAGE_KEY, 0.5)
