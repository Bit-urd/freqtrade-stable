"""固定防守试验：仅在亏损退出且 BTC 未确认时加强已有冷却。"""
from freqtrade.persistence import Trade
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardLossCooldownStrategy(BtcCoinGuardCycleRiskStrategy):
    """保留首次参与；亏损后的弱 BTC 再入场等待原有 14 天冷却。"""
    def confirm_trade_entry(self, pair, current_time, **kwargs):
        if not super().confirm_trade_entry(pair=pair,current_time=current_time,**kwargs):
            return False
        if self._btc_bull_confirmed(current_time):
            return True
        closed = [t for t in Trade.get_trades_proxy(pair=pair,is_open=False)
                  if t.close_date_utc is not None and t.close_date_utc <= current_time]
        if not closed:
            return True
        last = max(closed,key=lambda t:t.close_date_utc)
        if float(last.close_profit_abs or 0.0) >= 0:
            return True
        return (current_time-last.close_date_utc).total_seconds() >= self.RECOVERY_COOLDOWN_DAYS*86400
