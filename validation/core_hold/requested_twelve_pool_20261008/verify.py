import ast,copy,json,sys,hashlib
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'strategies'))
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Original
from btc_exit_confirmation_strategy import BtcTwoDayExitCycleRiskStrategy as Candidate
config=json.loads((root/'config.json').read_text())
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p) for p in (root/'data').glob('*-1d.feather')}
checks=[]
body=ast.parse((root/'strategies/btc_exit_confirmation_strategy.py').read_text()).body[1].body
assert len(body)==2 and isinstance(body[0],ast.Expr) and isinstance(body[1],ast.Assign)
assert body[1].targets[0].id=='TREND_EXIT_DAYS' and body[1].value.value==2
assert Candidate.TREND_EXIT_DAYS==2 and Original.TREND_EXIT_DAYS==1
checks.append('only_override_two_day_btc_exit')
for pair in history:
 s=Candidate(copy.deepcopy(config));s._history=lambda p,tf:history[p].copy()
 o=Original(copy.deepcopy(config));o._history=s._history
 frame=s.populate_indicators(history[pair].copy(),{'pair':pair})
 baseline=o.populate_indicators(history[pair].copy(),{'pair':pair})
 pd.testing.assert_frame_equal(frame.drop(columns='exposure_exit'),baseline.drop(columns='exposure_exit'))
 btcframe=o.populate_indicators(history['BTC/USDT'].copy(),{'pair':'BTC/USDT'})
 expected=btcframe.set_index('date').exposure_exit.rolling(2).sum().eq(2).reindex(frame.date)
 pd.testing.assert_series_equal(frame.set_index('date').exposure_exit,expected,check_names=False)
 checks.append(pair+':two_consecutive_original_weak_signals_only')
 for end in ['2022-08-17','2024-09-15','2026-09-30']:
  cutoff=pd.Timestamp(end,tz='UTC')
  if not (history[pair].date<=cutoff).any():continue
  s=Candidate(copy.deepcopy(config));s._history=lambda p,tf:history[p].loc[history[p].date<=cutoff].copy()
  prefix=s.populate_indicators(history[pair].loc[history[pair].date<=cutoff].copy(),{'pair':pair})
  pd.testing.assert_frame_equal(prefix.reset_index(drop=True),frame.loc[frame.date<=cutoff].reset_index(drop=True))
  checks.append(pair+':prefix:'+end)
assert hashlib.sha256((root/'strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==json.loads((root/'plan.json').read_text())['production_sha256']
checks.append('baseline_hash_unchanged')
(root/'verification.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks),indent=2)+'\n')
print('Passed',len(checks),'checks')

import os
sys.stdout.flush(); sys.stderr.flush(); os._exit(0)
