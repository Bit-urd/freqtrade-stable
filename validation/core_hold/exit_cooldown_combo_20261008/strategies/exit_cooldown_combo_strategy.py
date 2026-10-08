from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class TwoDayExitSevenDayCooldownCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    """Combine only BTC 2-day exit and weak-BTC 7-day same-pair cooldown."""
    TREND_EXIT_DAYS = 2
    RECOVERY_COOLDOWN_DAYS = 7
