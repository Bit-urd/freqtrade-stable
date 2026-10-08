import ast,copy,json,sys,hashlib
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'strategies'))
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Original
from exit_cooldown_combo_strategy import TwoDayExitSevenDayCooldownCycleRiskStrategy as Candidate
config=json.loads((root/'config.json').read_text())
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p) for p in (root.parent/'independent_trend_optimization_20261008/data').glob('*-1d.feather')}
checks=[]
body=ast.parse((root/'strategies/exit_cooldown_combo_strategy.py').read_text()).body[1].body
assert len(body)==3 and isinstance(body[0],ast.Expr)
assert {node.targets[0].id:node.value.value for node in body[1:]}=={'TREND_EXIT_DAYS':2,'RECOVERY_COOLDOWN_DAYS':7}
assert Candidate.TREND_EXIT_DAYS==2 and Candidate.RECOVERY_COOLDOWN_DAYS==7 and Candidate.REARM_COOLDOWN_DAYS==14
checks.append('only_two_constant_overrides')
for pair in history:
 s=Candidate(copy.deepcopy(config));s._history=lambda p,tf:history[p].copy()
 o=Original(copy.deepcopy(config));o._history=s._history
 frame=s.populate_indicators(history[pair].copy(),{'pair':pair})
 baseline=o.populate_indicators(history[pair].copy(),{'pair':pair})
 pd.testing.assert_frame_equal(frame.drop(columns='exposure_exit'),baseline.drop(columns='exposure_exit'))
 expected=baseline.set_index('date').exposure_exit.rolling(2).sum().eq(2)
 pd.testing.assert_series_equal(frame.set_index('date').exposure_exit,expected,check_names=False)
 checks.append(pair+':two_consecutive_original_weak_signals_only')
 for end in ['2022-08-17','2024-09-15']:
  cutoff=pd.Timestamp(end,tz='UTC')
  if not (history[pair].date<=cutoff).any():continue
  s=Candidate(copy.deepcopy(config));s._history=lambda p,tf:history[p].loc[history[p].date<=cutoff].copy()
  prefix=s.populate_indicators(history[pair].loc[history[pair].date<=cutoff].copy(),{'pair':pair})
  pd.testing.assert_frame_equal(prefix.reset_index(drop=True),frame.loc[frame.date<=cutoff].reset_index(drop=True))
  checks.append(pair+':prefix:'+end)
assert hashlib.sha256((root/'strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==hashlib.sha256((root.parent/'short_cooldown_20261008/strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()
checks.append('baseline_hash_unchanged')
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch
now=datetime(2025,6,1,tzinfo=timezone.utc)
s=Candidate(copy.deepcopy(config));s._last_closed_row=lambda *args:pd.Series({'cooldown_btc_strict':False})
for elapsed,want in [(7*86400-1,False),(7*86400,True),(7*86400+1,True)]:
 with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[SimpleNamespace(close_date_utc=now-timedelta(seconds=elapsed))]):assert s.confirm_trade_entry('SOL/USDT',now)==want
 checks.append('cooldown_boundary:'+str(elapsed))
for method in ['custom_exit','custom_stake_amount','adjust_trade_position','confirm_trade_entry','order_filled','bot_loop_start','_pair_budget','next_fraction']:
 assert getattr(Candidate,method) is getattr(Original,method);checks.append('inherited:'+method)
(root/'verification.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks),indent=2)+'\n')
print('Passed',len(checks),'checks')
