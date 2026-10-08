"""Research only: unchanged IndependentHold entries/sizing plus close-based ATR exit."""
import pandas as pd
from independent_cycle_risk_strategy import IndependentHoldCycleRiskStrategy
from atr_trailing_core import advance


class IndependentAtr3CycleRiskStrategy(IndependentHoldCycleRiskStrategy):
    ATR_MULTIPLE = 3.0
    ATR_STATE_KEY = 'independent_atr_close_v1'

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        coin = self._history(metadata['pair'], self.timeframe).copy()
        previous = coin.close.shift(1)
        ranges = pd.concat([
            coin.high - coin.low,
            (coin.high - previous).abs(),
            (coin.low - previous).abs(),
        ], axis=1).max(axis=1)
        # Wilder smoothing, initialized by the first 14 true ranges' mean.
        values, seed, value = [], [], None
        for tr in ranges:
            if value is None:
                seed.append(float(tr))
                if len(seed) == 14:
                    value = sum(seed) / 14
            else:
                value = (value * 13 + float(tr)) / 14
            values.append(float('nan') if value is None else value)
        coin['independent_atr14'] = values
        return frame.merge(coin[['date', 'independent_atr14']], on='date', how='left')

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        parent_exit = super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)
        if pair == self.BTC_PAIR:
            return parent_exit
        row = self._last_closed_row(pair, current_time)
        if row is None or row['date'] < trade.open_date_utc:
            return parent_exit
        activate = (parent_exit is None and self._flag(row, 'exposure_exit')
                    and self._flag(row, 'independent_strong'))
        state, hit = advance(
            trade.get_custom_data(self.ATR_STATE_KEY), row['date'].isoformat(),
            float(row['close']), float(row.get('independent_atr14', float('nan'))),
            self.ATR_MULTIPLE, activate,
        )
        trade.set_custom_data(self.ATR_STATE_KEY, state)
        # Original trend exits keep their precedence and attribution.
        return parent_exit or ('independent_atr_close' if hit else None)


class IndependentAtr2CycleRiskStrategy(IndependentAtr3CycleRiskStrategy):
    ATR_MULTIPLE = 2.0


class IndependentAtr4CycleRiskStrategy(IndependentAtr3CycleRiskStrategy):
    ATR_MULTIPLE = 4.0
