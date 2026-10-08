from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class ShortCooldownCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    """Only change: weak-BTC same-pair cooldown 14 -> 7 days."""
    RECOVERY_COOLDOWN_DAYS = 7
