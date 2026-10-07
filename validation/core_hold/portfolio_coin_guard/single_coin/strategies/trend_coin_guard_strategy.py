"""Fixed dual-trend trial: preserve fast BTC exposure and add individual defense.

Reuse BTC MA150 / EMA10 trend logic and apply the same rule to each traded
coin. Entries require both BTC and the coin to permit risk. Exit on either
BTC weakness (one day) or coin weakness (two completed days). No new tuning.
Original Portfolio remains the official strategy.
"""
from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendFastExitStrategy

class BtcTrendCoinGuardStrategy(BtcTrendFastExitStrategy):
    COIN_EXIT_DAYS = 2

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        coin = self._history(metadata['pair'], self.timeframe)[['date', 'close']].copy()
        ma = coin.close.rolling(self.TREND_MA_DAYS).mean()
        ema = coin.close.ewm(span=self.RECOVERY_EMA_DAYS, adjust=False).mean()
        recovery = (coin.close > ema) & (ema > ema.shift(1))
        valid = ma.notna()
        coin['coin_risk_on'] = valid & ((coin.close > ma) | recovery)
        weak = valid & (coin.close < ma) & ~recovery
        coin['coin_risk_off'] = weak.rolling(self.COIN_EXIT_DAYS).sum() == self.COIN_EXIT_DAYS
        return frame.merge(coin[['date', 'coin_risk_on', 'coin_risk_off']], on='date', how='left')

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        frame.loc[~frame.coin_risk_on.fillna(False), 'enter_long'] = 0
        return frame

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)
        if original:
            return original
        row = self._last_closed_row(pair, current_time)
        return 'coin_trend_to_cash' if row is not None and bool(row['coin_risk_off']) else None
