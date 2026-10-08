"""Causal indicator and callback checks using actual strategy classes."""
import json
import sys
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'strategies'))
from independent_atr_trailing_strategy import IndependentAtr3CycleRiskStrategy

config = json.loads((root / 'config.json').read_text())
data = root.parent / 'independent_trend_optimization_20261008/data'
history = {p.stem.split('-')[0].replace('_', '/'): pd.read_feather(p)
           for p in data.glob('*-1d.feather')}
checks = []
for pair, end in [('SUI/USDT', '2024-06-15'), ('ZEC/USDT', '2025-11-30'),
                  ('DOGE/USDT', '2022-11-08'), ('ADA/USDT', '2026-09-01')]:
    s = IndependentAtr3CycleRiskStrategy(config)
    s._history = lambda p, tf: history[p].copy()
    full = s.populate_indicators(history[pair].copy(), {'pair': pair})
    cutoff = pd.Timestamp(end, tz='UTC')
    s._history = lambda p, tf: history[p].loc[history[p].date <= cutoff].copy()
    prefix = s.populate_indicators(history[pair].loc[history[pair].date <= cutoff].copy(), {'pair': pair})
    pd.testing.assert_frame_equal(prefix.reset_index(drop=True), full.loc[full.date <= cutoff].reset_index(drop=True))
    checks.append('prefix_invariance:' + pair)


class DummyTrade:
    open_date_utc = pd.Timestamp('2025-01-01', tz='UTC')

    def __init__(self):
        self.custom = {}

    def get_custom_data(self, key):
        return self.custom.get(key)

    def set_custom_data(self, key, value):
        # Trade custom data must survive a JSON persistence round trip.
        self.custom[key] = json.loads(json.dumps(value, allow_nan=False))


s = IndependentAtr3CycleRiskStrategy(config)
t = DummyTrade()
row = pd.Series(dict(date=pd.Timestamp('2025-01-02', tz='UTC'), close=100.,
                     independent_atr14=5., exposure_exit=False,
                     independent_strong=True, coin_risk_off=False))
s._last_closed_row = lambda p, now: row
def exit(pair='ZEC/USDT'):
    return s.custom_exit(pair, t, row['date'] + pd.Timedelta(days=1), 100., 0.)

assert exit() is None and not t.custom[s.ATR_STATE_KEY]['active']
checks.append('strong_alone_does_not_activate')
row['date'] += pd.Timedelta(days=1)
row['exposure_exit'] = True
assert exit() is None and t.custom[s.ATR_STATE_KEY]['active']
checks.append('actually_allowed_exception_activates')
row['date'] += pd.Timedelta(days=1)
row['exposure_exit'] = False
row['independent_strong'] = False
row['close'] = 84.
assert exit() == 'independent_atr_close'
assert exit() == 'independent_atr_close'
checks.append('btc_recovery_and_duplicate_callback_preserve_stop_exit')
row['coin_risk_off'] = True
assert exit() == 'coin_trend_to_cash'
checks.append('original_exit_keeps_precedence')
before = dict(t.custom)
row['coin_risk_off'] = False
assert exit('BTC/USDT') is None and t.custom == before
checks.append('btc_unchanged')
row['exposure_exit'] = True
row['independent_strong'] = False
assert exit() == 'trend_to_cash'
checks.append('btc_filter_still_exits_without_independent_exception')
(root / 'integration_verification.json').write_text(json.dumps({'passed': True, 'checks': checks}, indent=2) + '\n')
print('Passed', len(checks), 'integration and causality checks', flush=True)
