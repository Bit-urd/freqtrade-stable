import csv,gzip,json
from datetime import datetime
from pathlib import Path
root=Path(__file__).resolve().parent;summary=[];total=0
for w in json.loads((root/'windows.json').read_text()):
 folder=root/'results'/w['label'];name='LimitedSharedCashCycleRiskStrategy'
 requests=json.loads((folder/('budget_requests_'+name+'.json')).read_text())
 bykey={}
 for r in requests:
  assert 0<=r['extra']<=r['base']*.5+1e-7
  assert r['amount']<=r['max_stake']+1e-7 and r['amount']<=r['base']*1.5+1e-7
  assert r['extra']<=max(0,r['max_stake']-r['reserved']-r['base']*1.001)*.5/1.001+1e-7
  bykey.setdefault((r['pair'],datetime.fromisoformat(r['execution_date'])),[]).append(r)
 trades=json.load(gzip.open(folder/(name+'.json.gz'),'rt'))['trades'];boosted=0
 for t in trades:
  matches=bykey.get((t['pair'],datetime.fromisoformat(t['open_date'])),[]);assert matches,(w['label'],t['pair'],t['open_date'])
  order=next(o for o in t['orders'] if o['ft_is_entry'] and o['order_filled_timestamp'] is not None)
  quote=float(order['amount'])*float(order['safe_price']);valid=[r for r in matches if quote<=r['amount']+.01];assert valid,(w['label'],quote,matches)
  boosted+=any(r['extra']>.01 and quote>r['base']+.01 for r in valid);total+=1
 summary.append(dict(window=w['label'],stake_requests=len(requests),filled_initial_entries=len(trades),filled_entries_with_extra_cash=boosted))
with (root/'budget_request_audit.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
(root/'actual_budget_verification.json').write_text(json.dumps(dict(passed=True,filled_entry_checks=total,extra_cap=.5,max_stake_and_peer_reservation_checks=True),indent=2)+'\n')
print('Verified',total,'actual initial fills')
