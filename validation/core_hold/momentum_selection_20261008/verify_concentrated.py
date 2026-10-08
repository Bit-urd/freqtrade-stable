"""Shared budget, fee, wallet and realized-profit accounting checks."""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'strategies'))
from concentrated_selection_strategy import WeeklyTop2ConcentratedCycleRiskStrategy
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy
from freqtrade.persistence import Trade

config = json.loads((root / 'config.json').read_text()); config['max_open_trades'] = 2
s = WeeklyTop2ConcentratedCycleRiskStrategy(config)
s.wallets = SimpleNamespace(get_starting_balance=lambda: 1000.)
closed = [SimpleNamespace(close_profit_abs=100.), SimpleNamespace(close_profit_abs=-20.)]
opened = [SimpleNamespace(realized_profit=20.)]
checks = []
with patch.object(Trade, 'get_trades_proxy', side_effect=lambda **kw: opened if kw['is_open'] else closed):
    assert s._pair_budget('BTC/USDT') == s._pair_budget('SOL/USDT') == 550.
    checks.append('shared_realized_capital_divided_by_two_slots')
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    s._risk_fraction = .75
    stake = s.custom_stake_amount('BTC/USDT', now, 100, 1000, 1, 1000, 1, 'phase_full_entry', 'long')
    assert abs(stake - .75 * 550 / 1.001) < 1e-8
    checks.append('original_account_fraction_and_fee_adjustment')
    assert s.custom_stake_amount('BTC/USDT', now, 100, 1000, 1, 100, 1, 'phase_full_entry', 'long') == 100.
    checks.append('wallet_max_stake_limits_new_entries')
    s._risk_fraction = 1.
    s._last_closed_row = lambda p, t: pd.Series(dict(exposure_exit=False, coin_risk_off=False))
    trade = SimpleNamespace(pair='BTC/USDT', has_open_orders=False,
        open_date_utc=now - timedelta(days=1), amount=1., fee_open=.001,
        stake_amount=100., realized_profit=20., get_custom_data=lambda key: .5)
    adjustment = s.adjust_trade_position(trade, now, 100., 0., 1., 1000., 100., 100., 0., 0.)
    assert abs(adjustment[0] - (550 - 100 * 1.001) / 1.001) < 1e-8
    checks.append('partial_realized_profit_not_double_counted')
    adjustment = s.adjust_trade_position(trade, now, 100., 0., 1., 100., 100., 100., 0., 0.)
    assert adjustment[0] == 100.
    checks.append('wallet_max_stake_limits_position_increases')
for method in ['custom_exit', 'confirm_trade_entry', 'order_filled', 'bot_loop_start', 'next_fraction']:
    assert getattr(WeeklyTop2ConcentratedCycleRiskStrategy, method) is getattr(BtcCoinGuardCycleRiskStrategy, method)
checks.append('original_exit_cooldown_and_account_risk_retained')
(root / 'concentrated_verification.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks), indent=2) + '\n')
print('Passed', len(checks), 'concentrated budget checks', flush=True)
