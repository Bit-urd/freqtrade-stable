"""One-change research trial: activate original immediate handover top-up.

Unlike archived weekly-confirmed top-up, use the original BTC two-day MA200
handover without an additional weekly entry gate. All baseline exits remain.
Not an official strategy; original Portfolio is unchanged.
"""
from ma200_btc_regime_full_cycle_portfolio_strategy import Ma200BtcRegimeFullCyclePortfolioStrategy

class BtcPortfolioBullHandoverStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    HANDOVER_TOP_UP = True
