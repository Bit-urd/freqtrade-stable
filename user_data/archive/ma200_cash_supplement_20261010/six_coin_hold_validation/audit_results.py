import csv,gzip,json,hashlib
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
D=Path(__file__).resolve().parent
raw=D.parent/'requested_27_half_year_20261008/raw/spot';prices={};checks=[];contributions=[]
for path in sorted(D.rglob('*_trades.json.gz')):
 if 'invalid_cursor_run' in path.parts:continue
 strategy=path.name.removesuffix('_trades.json.gz')
 trades=json.load(gzip.open(path,'rt'));pairs={t['pair'] for t in trades};daily=defaultdict(list)
 for pair in pairs:
  if pair not in prices:
   data=json.loads((raw/(pair.split('/')[0]+'.json')).read_text())
   prices[pair]={datetime.fromtimestamp(float(r[0])/1000,timezone.utc).strftime('%Y-%m-%d'):float(r[4]) for r in data}
 for t in trades:
  orders=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
  for i,o in enumerate(orders):
   if t['exit_reason']=='force_exit' and i==len(orders)-1:continue
   day=datetime.fromtimestamp(o['order_filled_timestamp']/1000,timezone.utc).strftime('%Y-%m-%d');q=float(o['amount']);v=q*float(o['safe_price']);buy=o['ft_is_entry'];change=-v*(1+float(t['fee_open'])) if buy else v*(1-float(t['fee_close']))
   daily[day].append((t['pair'],q if buy else -q,change))
 curve=list(csv.DictReader((path.parent/(strategy+'_equity.csv')).open()))
 cash=1000.;qty=defaultdict(float);flows=defaultdict(float);err=0.
 for r in curve:
  day=r[''][:10]
  for pair,q,change in daily[day]:cash+=change;qty[pair]+=q;flows[pair]+=change
  nav=cash+sum(q*prices[pair][day] for pair,q in qty.items() if abs(q)>1e-9)
  err=max(err,abs(nav-float(r['equity'])),abs(cash-float(r['cash'])))
 assert err<.05,(path,err)
 checks.append({'file':str(path.relative_to(D)),'max_daily_error':err,'end_equity':nav,'trades':len(trades),'mean_exposure_pct':sum((1-float(r['cash'])/float(r['equity']))*100 for r in curve)/len(curve)})
 for pair in sorted(pairs):contributions.append({'file':str(path.relative_to(D)),'pair':pair,'profit_usdt':flows[pair]+qty[pair]*prices[pair][day]})
 assert abs(sum(x['profit_usdt'] for x in contributions if x['file']==str(path.relative_to(D)))-(nav-1000))<.05
assert checks
for stage in [D,D/'ten',D/'single_assets']:
 for log in stage.glob('run.log'):
  assert ' - ERROR - ' not in log.read_text() and 'Traceback' not in log.read_text(),log
expected={'ma200_btc_regime_full_cycle_portfolio_strategy.py':'b08519edb1883e469a59514e7c4d2e68c26203be31f044fcfd77c0057fced9fc','cycle_risk_strategy.py':'471bb44d6617be4a5efb7862ef44dbc2f1be499e757f72666ee821893b416228'}
assert all(hashlib.sha256((D.parents[2]/'user_data/strategies'/n).read_bytes()).hexdigest()==h for n,h in expected.items())
(D/'all_stages_audit.json').write_text(json.dumps({'all_passed':True,'native_runs_audited':len(checks),'official_sources_unchanged':True,'max_error':max(x['max_daily_error'] for x in checks),'checks':checks},indent=2)+'\n')
with (D/'all_stages_contributions.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(contributions[0]));w.writeheader();w.writerows(contributions)
print('ALL STAGES AUDIT PASSED',len(checks),max(x['max_daily_error'] for x in checks))
