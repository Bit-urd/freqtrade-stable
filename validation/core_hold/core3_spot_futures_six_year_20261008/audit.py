import bisect,csv,datetime,gzip,hashlib,json,math
from pathlib import Path
root=Path(__file__).resolve().parent;cases=json.loads((root/'cases.json').read_text());raw_cache={(mode,a):json.loads((root/'raw'/mode/(a+'.json')).read_text()) for mode in ['spot','futures'] for a in ['BTC','ETH','SOL']};checks=0;maximum=0.;cashmax=0.;risk_checks=0;fund_checks=0;annual=[];attribution=[];summary=list(csv.DictReader((root/'summary.csv').open()));lookup={(r['case'],r['strategy']):r for r in summary}
def date(ms):return datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).date().isoformat()
for case in cases:
 folder=root/'results'/case['label'];assert (folder/'completed.json').exists();day=datetime.date.fromisoformat(case['start']);last=datetime.date.fromisoformat(case['end']);dates=[]
 while day<=last:dates.append(str(day));day+=datetime.timedelta(days=1)
 raw={a:raw_cache[case['mode'],a] for a in ['BTC','ETH','SOL']};prices={a:{date(r[0]):float(r[4]) for r in d['daily']['rows']} for a,d in raw.items()}
 for kind in ['strategy','hold_theoretical']:
  curve=list(csv.DictReader((folder/('equity_'+kind+'.csv')).open()));assert len(curve)==len(dates);flow={d:0. for d in dates};events={a:[] for a in raw};terminal=10000.;fees=0.;asset_flow={a:{d:0. for d in dates} for a in raw}
  if kind=='strategy':
   payload=json.load(gzip.open(folder/'trades.json.gz','rt'));name=payload['strategy']
   for trade in payload['trades']:
    if case['mode']=='futures':assert trade['leverage']==1 and not trade['is_short']
    a=trade['pair'].split('/')[0];orders=[o for o in trade['orders'] if o['order_filled_timestamp'] is not None];expected_fund=0.
    if case['mode']=='futures' and not case['zero_funding']:
     times=[int(f['fundingTime']) for f in raw[a]['funding']['rows']];prefix=[0.]
     for f in raw[a]['funding']['rows']:prefix.append(prefix[-1]+float(f['fundingRate'])*float(f['markPrice']))
     for o in orders:
      delta=float(o['amount'])*(1 if o['ft_is_entry'] else -1);expected_fund-=delta*(prefix[bisect.bisect_right(times,trade['close_timestamp'])]-prefix[bisect.bisect_right(times,o['order_filled_timestamp'])])
    assert abs(expected_fund-float(trade.get('funding_fees') or 0))<1e-5,(case['label'],a,'funding mismatch');fund_checks+=1;terminal+=float(trade.get('funding_fees') or 0)
    for i,o in enumerate(orders):
     when=o['order_filled_timestamp'];qty=float(o['amount']);entry=o['ft_is_entry'];delta=qty if entry else -qty;notional=qty*float(o['safe_price']);fee=trade['fee_open'] if entry else trade['fee_close'];cash=-notional*(1+fee) if entry else notional*(1-fee);terminal+=cash
     if trade['exit_reason']=='force_exit' and i==len(orders)-1:continue
     d=date(when);flow[d]+=cash;asset_flow[a][d]+=cash;events[a].append((when,delta));fees+=notional*fee
   error=abs(terminal-payload['final_balance']);assert error<.05;cashmax=max(cashmax,error)
  else:
   name='BuyAndHoldTheoretical'
   for a,d in raw.items():
    eligible=[r for r in d['daily']['rows'][61:] if case['start']<=date(r[0])<=case['end']]
    if eligible:first=eligible[0];budget=10000/3;flow[date(first[0])]-=budget;asset_flow[a][date(first[0])]-=budget;events[a].append((first[0],budget/(1+case['fee'])/float(first[1])));fees+=budget*case['fee']/(1+case['fee'])
  if case['mode']=='futures' and not case['zero_funding']:
   for a,d in raw.items():
    ev=sorted(events[a]);times=[e[0] for e in ev];prefix=[0.]
    for _,delta in ev:prefix.append(prefix[-1]+delta)
    for f in d['funding']['rows']:
     when=int(f['fundingTime']);dt=date(when)
     if dt in flow:cash=-prefix[bisect.bisect_left(times,when)]*float(f['fundingRate'])*float(f['markPrice']);flow[dt]+=cash;asset_flow[a][dt]+=cash
  cash=10000.;q={a:0. for a in raw};dayevents={d:[] for d in dates};rebuilt={};values={a:0. for a in raw};pnl={a:0. for a in raw}
  for a,ev in events.items():
   for when,delta in ev:dayevents[date(when)].append((a,delta))
  for d,r in zip(dates,curve):
   cash+=flow[d]
   for a,delta in dayevents[d]:q[a]+=delta
   assert min(q.values())>-1e-5
   for a in raw:
    value=q[a]*prices[a].get(d,0);pnl[a]+=value-values[a]+asset_flow[a][d];values[a]=value
   equity=cash+sum(values.values());error=abs(equity-float(r['equity']));assert error<.05,(case['label'],kind,d,error);assert abs(cash-float(r['cash']))<.05;maximum=max(maximum,error);rebuilt[d]=equity
  if kind=='strategy':
   trace=json.loads((folder/'risk_trace.json').read_text());assert len(trace)>=len(dates)-2
   for row in trace:
    d=(datetime.date.fromisoformat(row['execution_date'][:10])-datetime.timedelta(days=1)).isoformat()
    if d in rebuilt:assert abs(rebuilt[d]-row['prior_closed_equity'])<.05;risk_checks+=1
  peak=10000.;dd=0.
  for v in rebuilt.values():peak=max(peak,v);dd=max(dd,1-v/peak)
  metric=lookup[case['label'],name];assert abs((list(rebuilt.values())[-1]/10000-1)*100-float(metric['return_pct']))<1e-5;assert abs(dd*100-float(metric['wallet_drawdown_pct']))<1e-5;assert abs(fees-float(metric['normal_fees']))<1e-5
  assert abs(sum(pnl.values())-(list(rebuilt.values())[-1]-10000))<.05
  for a,value in pnl.items():attribution.append(dict(case=case['label'],strategy=name,asset=a,profit_abs=value))
  prior=10000.
  for year in sorted(set(d[:4] for d in dates)):
   vals=[v for d,v in rebuilt.items() if d.startswith(year)];peak=prior;dd=0.
   for v in vals:peak=max(peak,v);dd=max(dd,1-v/peak)
   annual.append(dict(case=case['label'],strategy=name,year=year,return_pct=(vals[-1]/prior-1)*100,drawdown_pct=dd*100));prior=vals[-1]
  checks+=1
for filename,records in [('annual.csv',annual),('profit_attribution.csv',attribution)]:
 with (root/filename).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator='\n');w.writeheader();w.writerows(records)
for r in json.loads((root/'data_audit.json').read_text()):assert hashlib.sha256((root/r['file']).read_bytes()).hexdigest()==r['sha256']
result=dict(passed=True,curve_checks=checks,funding_trade_checks=fund_checks,daily_risk_equity_checks=risk_checks,max_equity_error=maximum,max_cash_error=cashmax);(root/'audit_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
