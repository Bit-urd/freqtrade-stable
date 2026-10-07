"""BTC 与个币双趋势保护：保留快速参与 BTC 行情的能力，增加个币退出保护。

沿用 BTC 的 MA150 / EMA10 趋势规则，并对每个交易币应用相同规则。
只有 BTC 与该币均允许风险敞口时才进场；BTC 弱势一根完整日线，
或个币弱势连续两根完整日线时退出。本轮不调整参数。
这是新正式版的信号父类，同时保留为风控消融对照。
"""
import pandas as pd
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
        signal = row.get('coin_risk_off', False) if row is not None else False
        return 'coin_trend_to_cash' if pd.notna(signal) and bool(signal) else None
