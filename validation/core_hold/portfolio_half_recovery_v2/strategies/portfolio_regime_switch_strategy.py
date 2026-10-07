"""Research: guarded trend in confirmed BTC bull regime, Portfolio otherwise.

BTC bull regime = two completed daily closes above its MA200. No calendar
labels or future regime information. One wallet, same Portfolio slot sizing.
Positions migrate in place: confirmed bull may fill a reserved small slot;
non-bull uses original Portfolio exits, weekly sizing and bear accumulation.
"""
import pandas as pd
from ma200_btc_regime_full_cycle_portfolio_strategy import Ma200BtcRegimeFullCyclePortfolioStrategy

class BtcPortfolioRegimeSwitchStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    GUARD_TAG = 'hybrid_guard_entry'
    TOP_UP_TAG = 'hybrid_bull_restore'
    GUARD_FILLED_KEY = 'hybrid_guard_slot_filled'

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        for pair, prefix, days in [(self.BTC_PAIR, 'guard_btc', 1), (metadata['pair'], 'guard_coin', 2)]:
            prices = self._history(pair, self.timeframe)[['date', 'close']].copy()
            ma = prices.close.rolling(150).mean()
            ema = prices.close.ewm(span=10, adjust=False).mean()
            recovery = (prices.close > ema) & (ema > ema.shift(1))
            valid = ma.notna()
            prices[prefix+'_on'] = valid & ((prices.close > ma) | recovery)
            weak = valid & (prices.close < ma) & ~recovery
            prices[prefix+'_off'] = weak.rolling(days).sum() == days
            frame = frame.merge(prices[['date', prefix+'_on', prefix+'_off']], on='date', how='left')
        frame['hybrid_bull'] = frame.btc_bull_2d.fillna(False)
        return frame

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        bull = frame.hybrid_bull.fillna(False)
        frame.loc[bull, 'enter_long'] = 0
        allowed = (bull & frame.guard_btc_on.fillna(False)
                   & frame.guard_coin_on.fillna(False)
                   & (frame.own_candles > self.startup_candle_count)
                   & (frame.volume > 0))
        frame.loc[allowed, ['enter_long', 'enter_tag']] = [1, self.GUARD_TAG]
        return frame

    @staticmethod
    def _flag(row, key):
        return row is not None and pd.notna(row.get(key)) and bool(row[key])

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        if self._flag(row, 'hybrid_bull'):
            return 'hybrid_coin_to_cash' if self._flag(row, 'guard_coin_off') or self._flag(row, 'guard_btc_off') else None
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        row = self._last_closed_row(trade.pair, current_time)
        if self._flag(row, 'hybrid_bull'):
            if (self._flag(row, 'guard_coin_off') or self._flag(row, 'guard_btc_off')
                    or not self._flag(row, 'guard_coin_on')
                    or trade.get_custom_data(self.GUARD_FILLED_KEY)):
                return None
            slot = self._equity(current_time, trade.pair, current_rate) / self._slots()
            amount = min(max(0.0, slot - float(trade.amount) * current_rate)
                         / (1 + float(trade.fee_open)), max_stake)
            if amount >= max(1.0, min_stake or 0.0):
                return (amount, self.TOP_UP_TAG)
            return None
        # Signal-mode reset is distinct from the exposure recorded on fills.
        trade.set_custom_data(self.GUARD_FILLED_KEY, False)
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit,
            current_exit_profit, **kwargs)

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        if order.ft_order_side != trade.entry_side:
            return
        if order.ft_order_tag in (self.GUARD_TAG, self.TOP_UP_TAG):
            trade.set_custom_data(self.GUARD_FILLED_KEY, True)
            trade.set_custom_data(self.TARGET_KEY, 1.0)
