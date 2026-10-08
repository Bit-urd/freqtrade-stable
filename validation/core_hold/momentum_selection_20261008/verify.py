"""Verify prefix invariance, calendar mapping, rank limits and inherited rules."""
import copy
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'strategies'))
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy
from momentum_selection_strategy import TrendOnlyCycleRiskStrategy, WeeklyTop2CycleRiskStrategy, WeeklyTop2TrendOnlyCycleRiskStrategy

config = json.loads((root / 'config.json').read_text())
history = {p.stem.split('-')[0].replace('_', '/'): pd.read_feather(p)
           for p in (root.parent / 'independent_trend_optimization_20261008/data').glob('*-1d.feather')}
checks = []
classes = [TrendOnlyCycleRiskStrategy, WeeklyTop2CycleRiskStrategy, WeeklyTop2TrendOnlyCycleRiskStrategy]
for cls in classes:
    for pair, end in [('SOL/USDT', '2022-08-17'), ('ETH/USDT', '2024-09-15')]:
        full_strategy = cls(copy.deepcopy(config)); full_strategy._history = lambda p, tf: history[p].copy()
        full = full_strategy.populate_entry_trend(full_strategy.populate_indicators(history[pair].copy(), {'pair': pair}), {'pair': pair})
        cutoff = pd.Timestamp(end, tz='UTC')
        prefix_strategy = cls(copy.deepcopy(config)); prefix_strategy._history = lambda p, tf: history[p].loc[history[p].date <= cutoff].copy()
        prefix = prefix_strategy.populate_entry_trend(prefix_strategy.populate_indicators(history[pair].loc[history[pair].date <= cutoff].copy(), {'pair': pair}), {'pair': pair})
        pd.testing.assert_frame_equal(prefix.reset_index(drop=True), full.loc[full.date <= cutoff].reset_index(drop=True))
        checks.append(cls.__name__ + ':prefix:' + pair)
    for method in ['custom_exit', 'custom_stake_amount', 'adjust_trade_position', 'confirm_trade_entry', 'order_filled', 'bot_loop_start', '_pair_budget']:
        assert getattr(cls, method) is getattr(BtcCoinGuardCycleRiskStrategy, method)
    checks.append(cls.__name__ + ':original_exit_sizing_risk_cooldown_inherited')
    assert full_strategy._slots() == 3
    checks.append(cls.__name__ + ':no_capital_redistribution')

dates = pd.date_range('2020-01-01', periods=240, tz='UTC')
def candles(rate):
    close = 100 * np.exp(rate * np.arange(len(dates)))
    return pd.DataFrame(dict(date=dates, open=close, high=close * 1.01, low=close * .99, close=close, volume=100.))
synthetic = {'BTC/USDT': candles(.002), 'ETH/USDT': candles(.004), 'SOL/USDT': candles(.006)}
s = WeeklyTop2CycleRiskStrategy(copy.deepcopy(config)); s._history = lambda p, tf: synthetic[p].copy()
ranks = s._weekly_ranks()
assert (ranks.sum(axis=1) <= 2).all()
assert ranks.iloc[-1]['ETH/USDT'] and ranks.iloc[-1]['SOL/USDT'] and not ranks.iloc[-1]['BTC/USDT']
checks.append('top2_of_eligible_universe')
frame = s.populate_indicators(synthetic['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
execution = frame.date + pd.Timedelta(days=1)
assert (frame.ranking_signal_date < execution).all()
assert (frame.ranking_signal_date.dt.dayofweek == 6).all()
assert (frame.ranking_signal_date <= frame.date).all()
assert frame.loc[execution.dt.dayofweek == 0, 'ranking_signal_date'].equals(frame.loc[execution.dt.dayofweek == 0, 'date'])
checks.append('sunday_signal_applies_at_monday_open')
assert (frame.loc[execution.dt.dayofweek == 6, 'ranking_signal_date'] == frame.loc[execution.dt.dayofweek == 6, 'date'] - pd.Timedelta(days=6)).all()
checks.append('sunday_execution_keeps_previous_week_snapshot')
entry = s.populate_entry_trend(frame.copy(), {'pair': 'SOL/USDT'})
assert entry.enter_long.iloc[-1] == 1
frame.loc[frame.index[-1], 'exposure_entry'] = False
entry = s.populate_entry_trend(frame.copy(), {'pair': 'SOL/USDT'})
assert entry.enter_long.iloc[-1] != 1
checks.append('momentum_never_bypasses_btc_gate')
frame.loc[frame.index[-1], 'exposure_entry'] = True
frame.loc[frame.index[-1], 'coin_risk_on'] = False
assert s.populate_entry_trend(frame, {'pair': 'SOL/USDT'}).enter_long.iloc[-1] == 0
checks.append('momentum_never_bypasses_own_coin_gate')
tied = {p: candles(.004) for p in config['exchange']['pair_whitelist']}
s = WeeklyTop2CycleRiskStrategy(copy.deepcopy(config)); s._history = lambda p, tf: tied[p].copy()
last = s._weekly_ranks().iloc[-1]
assert last['BTC/USDT'] and last['ETH/USDT'] and not last['SOL/USDT']
checks.append('deterministic_alphabetical_tie_break')
source = {p: h.copy() for p, h in synthetic.items()}; source['SOL/USDT'] = source['SOL/USDT'].iloc[-40:]
s = WeeklyTop2CycleRiskStrategy(copy.deepcopy(config)); s._history = lambda p, tf: source[p].copy()
assert not s._weekly_ranks()['SOL/USDT'].any()
checks.append('immature_asset_excluded')
s = TrendOnlyCycleRiskStrategy(copy.deepcopy(config)); s._history = lambda p, tf: synthetic[p].copy()
frame = s.populate_indicators(synthetic['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
frame.loc[frame.index[-1], 'own_above_ma150'] = False
assert s.populate_entry_trend(frame, {'pair': 'SOL/USDT'}).enter_long.iloc[-1] == 0
checks.append('trend_only_rejects_recovery_entries')
for cls in [WeeklyTop2CycleRiskStrategy, WeeklyTop2TrendOnlyCycleRiskStrategy]:
    c = copy.deepcopy(config); c['exchange']['pair_whitelist'] = list(history); c['max_open_trades'] = len(history)
    s = cls(c); s._history = lambda p, tf: history[p].copy()
    ranks = s._weekly_ranks()
    assert (ranks.sum(axis=1) <= 2).all()
    assert not ranks.loc[ranks.index < pd.Timestamp('2023-05-03', tz='UTC'), 'SUI/USDT'].any()
    checks.append(cls.__name__ + ':broad_universe_causal_top2')
(root / 'indicator_verification.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks), indent=2) + '\n')
print('Passed', len(checks), 'momentum checks', flush=True)
