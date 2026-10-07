"""Three-pair growth profiles for the configurable CoreHold strategy.

Growth tops up the bear-to-bull handover and disables weekly half-slot sizing.
Recovery additionally restores trimmed exposure after coin trend recovery and
uses the same core rules for handed-over positions. BTC bear exits remain active.
See validation/core_hold/improve_btc_sol_eth/REPORT.md for measured tradeoffs.
"""
from ma200_btc_regime_full_cycle_core_hold_strategy import (
    Ma200BtcRegimeFullCycleCoreHoldStrategy,
)


class Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy(Ma200BtcRegimeFullCycleCoreHoldStrategy):
    HANDOVER_TOP_UP = True
    BULL_WEEKLY_SIZING = False


class Ma200BtcRegimeFullCycleCoreHoldRecoveryStrategy(
    Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy,
):
    CORE_RESTORE_ON_RECOVERY = True
    HANDOVER_CORE_HOLD = True
