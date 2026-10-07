"""固定退出结构试验：仅在有趋势支持时延迟个币退出。"""
import pandas as pd
from trend_aware_risk_strategy import BtcCoinGuardTrendRecoveryRiskStrategy
from recovery_refinement_strategy import BtcCoinGuardConfirmedCoinExitStrategy

class BtcCoinGuardRisingMediumExitStrategy(BtcCoinGuardConfirmedCoinExitStrategy):
    """EMA20 高于 EMA50 且 EMA50 仍上升才延迟个币退出。"""
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        h = self._history(metadata['pair'], self.timeframe)[['date','close']].copy()
        ema50 = h.close.ewm(span=50,adjust=False).mean()
        h['coin_medium_rising'] = ema50 > ema50.shift(1)
        return frame.merge(h[['date','coin_medium_rising']],on='date',how='left')

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = BtcCoinGuardTrendRecoveryRiskStrategy.custom_exit(self,pair,trade,current_time,current_rate,current_profit,**kwargs)
        if original != 'coin_trend_to_cash':
            return original
        row = self._last_closed_row(pair,current_time)
        if row is None:
            return original
        weak = row.get('coin_medium_weak',True)
        rising = row.get('coin_medium_rising',False)
        supported = pd.notna(weak) and not bool(weak) and pd.notna(rising) and bool(rising)
        return None if supported else original

class BtcCoinGuardBtcConfirmedExitStrategy(BtcCoinGuardConfirmedCoinExitStrategy):
    """个币中期多头且 BTC 连续两天站上 MA200 才延迟个币退出。"""
    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = BtcCoinGuardTrendRecoveryRiskStrategy.custom_exit(self,pair,trade,current_time,current_rate,current_profit,**kwargs)
        if original != 'coin_trend_to_cash':
            return original
        row = self._last_closed_row(pair,current_time)
        weak = row.get('coin_medium_weak',True) if row is not None else True
        supported = pd.notna(weak) and not bool(weak) and self._btc_bull_confirmed(current_time)
        return None if supported else original
