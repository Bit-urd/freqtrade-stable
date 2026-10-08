import sys,json
from pathlib import Path
import pandas as pd
root=Path(__file__).parent
sys.path.insert(0,str(root/'strategies'))
from independent_fast_guard_strategy import IndependentFastGuardCycleRiskStrategy
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p) for p in (root/'data').glob('*-1d.feather')}
config=json.loads((root/'config.json').read_text());checks=[]
for pair,end in [('SUI/USDT','2024-06-15'),('ZEC/USDT','2025-11-30'),('DOGE/USDT','2022-11-08'),('ADA/USDT','2026-09-01')]:
 s=IndependentFastGuardCycleRiskStrategy(config);s._history=lambda p,tf:history[p].copy()
 full=s.populate_indicators(history[pair].copy(),{'pair':pair})
 cutoff=pd.Timestamp(end,tz='UTC');s._history=lambda p,tf:history[p].loc[history[p].date<=cutoff].copy()
 prefix=s.populate_indicators(history[pair].loc[history[pair].date<=cutoff].copy(),{'pair':pair})
 pd.testing.assert_frame_equal(prefix.reset_index(drop=True),full.loc[full.date<=cutoff].reset_index(drop=True))
 checks.append('fast_guard_prefix_invariance:'+pair+':'+end)
s=IndependentFastGuardCycleRiskStrategy(config);s._history=lambda p,tf:history[p].copy()
btc=s.populate_indicators(history['BTC/USDT'].copy(),{'pair':'BTC/USDT'})
assert not btc.independent_strong.any()
checks.append('btc_has_no_fast_guard_exception')
(root/'fast_verification.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2));print('Passed',len(checks),'fast-guard checks',flush=True)
