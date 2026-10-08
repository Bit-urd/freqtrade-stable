import csv,json,runpy
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
btc=pd.read_feather(root.parent/'independent_trend_optimization_20261008/data/BTC_USDT-1d.feather').set_index('date').close
ma=btc.rolling(150).mean();ema=btc.ewm(span=10,adjust=False).mean()
allowed=ma.notna() & ((btc>ma) | ((btc>ema)&(ema>ema.shift(1))))
rows=[]
for w in json.loads((root/'windows.json').read_text()):
 traces=json.loads((root/'results'/w['label']/'risk_trace_BtcCoinGuardCycleRiskStrategy.json').read_text())
 reduced=eligible=earlier=0
 for t in traces:
  day=pd.Timestamp(t['execution_date'])-pd.Timedelta(days=1)
  frac=t['risk_fraction'];dd=t['drawdown'];btc_on=bool(allowed.get(day,False))
  reduced+=frac<1
  eligible+=(frac<1 and btc_on)
  earlier+=(btc_on and ((frac==.75 and .20<dd<=.225) or (frac==.5 and .30<dd<=.325)))
 rows.append(dict(window=w['label'],days=len(traces),reduced_risk_days=reduced,btc_eligible_reduced_days=eligible,earlier_recovery_candidate_days=earlier))
with (root/'recovery_diagnosis.csv').open('w') as f:
 out=csv.DictWriter(f,fieldnames=list(rows[0]));out.writeheader();out.writerows(rows)
print('Recovery diagnosis',json.dumps(rows),flush=True)
assert sum(r['earlier_recovery_candidate_days'] for r in rows)>0,'No earlier recovery opportunity: do not run candidate blindly'
plan=json.loads((root/'plan.json').read_text());plan['status']='running';plan['diagnosis']='Original-path reduced-risk days overlap BTC entry permission and fixed earlier recovery thresholds; descriptive, not causal.';(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
runpy.run_path(str(root/'run.py'),run_name='__main__')
