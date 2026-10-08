from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class FasterRecoveryCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    """Retain reductions at 25/35%; recover at 22.5/32.5%, not 20/30%."""
    @staticmethod
    def next_fraction(previous, drawdown):
        if drawdown >= .35:
            return .5
        if previous == 1.0:
            return .75 if drawdown >= .25 else 1.0
        if drawdown <= .225:
            return 1.0
        if previous == .5:
            return .75 if drawdown <= .325 else .5
        return .75
