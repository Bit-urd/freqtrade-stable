import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'strategies'))
from recovery_speed_strategy import FasterRecoveryCycleRiskStrategy as Candidate
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Original
checks=[]
for previous,dd,want in [(1,.249,1),(1,.25,.75),(1,.35,.5),(.75,.225,1),(.75,.22501,.75),(.75,.35,.5),(.5,.325,.75),(.5,.32501,.5),(.5,.225,1),(.5,.35,.5),(.75,.20,1),(.5,.30,.75)]:
 assert Candidate.next_fraction(previous,dd)==want;(checks.append(f'fraction:{previous}:{dd}:{want}'))
for previous in [1,.75,.5]:
 for dd in [.35,.40,.80]:
  assert Candidate.next_fraction(previous,dd)==Original.next_fraction(previous,dd)==.5
  checks.append(f'preserved_reduction:{previous}:{dd}')
for method in ['populate_indicators','custom_exit','confirm_trade_entry','custom_stake_amount','adjust_trade_position','order_filled','bot_loop_start','_pair_budget']:
 assert getattr(Candidate,method) is getattr(Original,method);checks.append('inherited:'+method)
(root/'verification.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks),indent=2)+'\n');print('Passed',len(checks),'checks')
