from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcTwoDayExitCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    """Only change: two completed weak BTC candles before exiting."""
    TREND_EXIT_DAYS = 2
