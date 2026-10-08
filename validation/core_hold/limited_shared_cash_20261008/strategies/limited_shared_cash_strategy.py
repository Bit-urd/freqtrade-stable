import pandas as pd
from freqtrade.persistence import Trade
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class LimitedSharedCashCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    """Entry-only cash sharing; keep original exits, budget accounting and adjustments."""
    def __init__(self, config):
        super().__init__(config)
        self.budget_requests = []

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                           min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        base = super().custom_stake_amount(pair, current_time, current_rate, proposed_stake,
                                         min_stake, max_stake, leverage, entry_tag, side, **kwargs)
        if base <= 0:
            return 0.0
        fee = .001 if self.config.get('fee') is None else float(self.config['fee'])
        held = {trade.pair for trade in Trade.get_trades_proxy(is_open=True)}
        reserved = 0.0
        for peer in self.dp.current_whitelist():
            if peer == pair or peer in held:
                continue
            row = self._last_closed_row(peer, current_time)
            signals = [] if row is None else [row.get('coin_risk_on', False), row.get('exposure_entry', False)]
            eligible = (len(signals) == 2 and all(pd.notna(v) and bool(v) for v in signals)
                        and row.get('volume', 0) > 0
                        and self.confirm_trade_entry(peer, current_time))
            weight = 1.0 if eligible else .5
            reserved += weight * self._risk_fraction * self._pair_budget(peer)
        extra = min(base * .5, max(0.0, max_stake - reserved - base * (1 + fee)) * .5 / (1 + fee))
        amount = min(max_stake, base + extra)
        self.budget_requests.append(dict(execution_date=current_time, pair=pair, base=base,
                                        max_stake=max_stake, reserved=reserved, extra=extra, amount=amount))
        return amount
