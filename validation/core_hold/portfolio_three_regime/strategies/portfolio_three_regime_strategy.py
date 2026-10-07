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
