import csv,gzip,json,runpy
from datetime import datetime
from pathlib import Path
root=Path(__file__).resolve().parent
rows=[]
for w in json.loads((root/'windows.json').read_text()):
 label=w['label'];folder=root/'results'/label
 equity={datetime.fromisoformat(x['']).date():float(x['cash']) for x in csv.DictReader((folder/'equity_BtcCoinGuardCycleRiskStrategy.csv').open())}
 trades=json.load(gzip.open(folder/'BtcCoinGuardCycleRiskStrategy.json.gz','rt'))['trades'];count=0
 for t in trades:
  order=next(o for o in t['orders'] if o['ft_is_entry'] and o['order_filled_timestamp'] is not None)
  day=datetime.fromisoformat(t['open_date']).date()
  initial=float(order['amount'])*float(order['safe_price'])
  if equity.get(day,0)>=.5*initial:count+=1
 rows.append(dict(window=label,positions=len(trades),entry_days_with_close_cash_at_least_half_initial_stake=count))
with (root/'idle_cash_diagnosis.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print('Idle cash diagnosis',json.dumps(rows),flush=True)
assert sum(x['entry_days_with_close_cash_at_least_half_initial_stake'] for x in rows)>0
plan=json.loads((root/'plan.json').read_text());plan['status']='running';plan['diagnosis']='Original-path entry days retaining cash at daily close; descriptive, not callback available cash or proof that reserving other budgets is unnecessary.';(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
runpy.run_path(str(root/'run.py'),run_name='__main__')
