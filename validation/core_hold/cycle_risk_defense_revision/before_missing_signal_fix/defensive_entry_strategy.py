"""CycleRisk 防守试验：仅过滤新开仓，不增加账户状态或延迟退出。"""
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardConfirmedBtcEntryStrategy(BtcCoinGuardCycleRiskStrategy):
    """新开仓要求 BTC 连续两根完整日线站上 MA200。"""
    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        btc = self._history(self.BTC_PAIR, self.timeframe)[['date','close']].copy()
        above = btc.close > btc.close.rolling(200).mean()
        btc['defense_btc_confirmed'] = above & above.shift(1,fill_value=False)
        return frame.merge(btc[['date','defense_btc_confirmed']],on='date',how='left')

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        frame.loc[~frame.defense_btc_confirmed.fillna(False),'enter_long'] = 0
        return frame

class BtcCoinGuardSelectiveRecoveryEntryStrategy(BtcCoinGuardConfirmedBtcEntryStrategy):
    """BTC 未确认时，只允许个币中期多头且 EMA50 上升的修复入场。"""
    def populate_entry_trend(self, dataframe, metadata):
        # 从正式版取得候选入场，保留 BTC 弱势下个币自身中期强势的例外。
        frame = BtcCoinGuardCycleRiskStrategy.populate_entry_trend(self,dataframe,metadata)
        medium = (frame.ema20 > frame.ema50) & (frame.ema50 > frame.ema50.shift(1))
        allowed = frame.defense_btc_confirmed.fillna(False) | medium.fillna(False)
        frame.loc[~allowed,'enter_long'] = 0
        return frame
