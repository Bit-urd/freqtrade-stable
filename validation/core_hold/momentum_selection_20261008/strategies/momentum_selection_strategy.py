"""Entry-only ablations; preserve original exits, cooldowns and pair budgets."""
import pandas as pd
from freqtrade.enums import RunMode
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy


class TrendOnlyCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        history = self._history(metadata['pair'], self.timeframe)[['date', 'close']].copy()
        history['own_ma150'] = history.close.rolling(self.TREND_MA_DAYS).mean()
        history['own_above_ma150'] = history.close > history.own_ma150
        return frame.merge(history[['date', 'own_ma150', 'own_above_ma150']], on='date', how='left')

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        frame.loc[~frame.own_above_ma150.fillna(False), 'enter_long'] = 0
        return frame


class WeeklyTop2CycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    MOMENTUM_DAYS = 60
    TOP_N = 2
    RANK_REQUIRE_TREND = False

    def __init__(self, config):
        super().__init__(config)
        self._ranking_cache = None
        self._ranking_universe = None

    def informative_pairs(self):
        pairs = dict.fromkeys([self.BTC_PAIR, *self.config['exchange']['pair_whitelist']])
        return [(pair, self.timeframe) for pair in pairs]

    def _weekly_ranks(self):
        pairs = tuple(sorted(self.config['exchange']['pair_whitelist']))
        cacheable = self.config.get('runmode') not in (RunMode.LIVE, RunMode.DRY_RUN)
        if cacheable and self._ranking_cache is not None and self._ranking_universe == pairs:
            return self._ranking_cache
        histories = {}
        for pair in pairs:
            frame = self._history(pair, self.timeframe).copy().set_index('date')
            close = frame.close
            ma = close.rolling(self.TREND_MA_DAYS).mean()
            ema = close.ewm(span=self.RECOVERY_EMA_DAYS, adjust=False).mean()
            risk_on = ma.notna() & ((close > ma) | ((close > ema) & (ema > ema.shift(1))))
            score = close.pct_change(self.MOMENTUM_DAYS, fill_method=None)
            valid = risk_on & (frame.volume > 0) & score.notna()
            if self.RANK_REQUIRE_TREND:
                valid &= close > ma
            histories[pair] = score.where(valid)
        scores = pd.DataFrame(histories).sort_index()
        snapshots = scores.loc[scores.index.dayofweek == 6]
        # rank(method='first') uses the deterministic alphabetical column order.
        ranks = snapshots.rank(axis=1, ascending=False, method='first')
        selected = ranks.le(self.TOP_N) & ranks.notna()
        self._ranking_cache = selected
        self._ranking_universe = pairs
        return selected

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        snapshots = self._weekly_ranks()
        # Signal on Sunday executes Monday. Other daily signals refer back to the
        # latest Sunday, so future snapshots cannot alter past selection.
        execution = frame.date + pd.Timedelta(days=1)
        monday = execution.dt.normalize() - pd.to_timedelta(execution.dt.dayofweek, unit='D')
        reference = monday - pd.Timedelta(days=1)
        selected = snapshots[metadata['pair']].reindex(pd.DatetimeIndex(reference))
        frame['weekly_rank_selected'] = selected.fillna(False).to_numpy(dtype=bool)
        frame['ranking_signal_date'] = reference
        return frame

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        frame.loc[~frame.weekly_rank_selected.fillna(False), 'enter_long'] = 0
        return frame


class WeeklyTop2TrendOnlyCycleRiskStrategy(WeeklyTop2CycleRiskStrategy):
    RANK_REQUIRE_TREND = True

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        history = self._history(metadata['pair'], self.timeframe)[['date', 'close']].copy()
        history['own_above_ma150'] = history.close > history.close.rolling(self.TREND_MA_DAYS).mean()
        return frame.merge(history[['date', 'own_above_ma150']], on='date', how='left')

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        frame.loc[~frame.own_above_ma150.fillna(False), 'enter_long'] = 0
        return frame
