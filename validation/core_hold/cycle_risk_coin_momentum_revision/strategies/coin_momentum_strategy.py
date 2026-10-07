"""回撤归因后的固定试验：用个币既有 EMA20 过滤单日反弹。"""
import pandas as pd
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardCoinMomentumEntryStrategy(BtcCoinGuardCycleRiskStrategy):
    """个币连续两天站上 EMA20 才允许原入场，不改变原退出。"""
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe,metadata)
        good = frame.close > frame.ema20
        frame['coin_medium_entry'] = good.rolling(self.COIN_EXIT_DAYS).sum() == self.COIN_EXIT_DAYS
        return frame

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe,metadata)
        frame.loc[~frame.coin_medium_entry.fillna(False).astype(bool),'enter_long'] = 0
        return frame

class BtcCoinGuardCoinMomentumExitStrategy(BtcCoinGuardCoinMomentumEntryStrategy):
    """在对称入场过滤基础上，个币连续两天跌破 EMA20 时退出。"""
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe,metadata)
        weak = frame.close < frame.ema20
        frame['coin_medium_exit'] = weak.rolling(self.COIN_EXIT_DAYS).sum() == self.COIN_EXIT_DAYS
        return frame

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        original = super().custom_exit(pair,trade,current_time,current_rate,current_profit,**kwargs)
        if original:
            return original
        row = self._last_closed_row(pair,current_time)
        signal = row.get('coin_medium_exit',False) if row is not None else False
        return 'coin_medium_to_cash' if pd.notna(signal) and bool(signal) else None
