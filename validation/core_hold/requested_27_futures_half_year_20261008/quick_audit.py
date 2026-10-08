"""Standard-library independent first-stage check, including settlement-time position quantities."""
import bisect,csv,datetime,gzip,json,math
from pathlib import Path
root=Path(__file__).resolve().parent;windows=json.loads((root/'windows.json').read_text());maximum=0.;checks=0
for window in windows:
 folder=root/'results'/window['label']
 if not (folder/'completed.json').exists():continue
 dates=[window['start']];day=datetime.date.fromisoformat(dates[0]);last=datetime.date.fromisoformat(window['end'])
 dates=[]
 while day<=last:dates.append(str(day));day+=datetime.timedelta(days=1)
 raw={p:json.loads((root/'raw'/(p.split('/')[0]+'.json')).read_text()) for p in window['pairs']};prices={p:{datetime.datetime.fromtimestamp(r[0]/1000,datetime.timezone.utc).date().isoformat():float(r[4]) for r in d['daily']['rows']} for p,d in raw.items()}
 for name in ['BtcCoinGuardCycleRiskStrategy','BtcTwoDayExitCycleRiskStrategy','BuyAndHold']:
  curve=list(csv.DictReader((folder/('equity_'+name+'.csv')).open()));flow={d:0. for d in dates};events={p:[] for p in raw};terminal=10000.
  if name!='BuyAndHold':
   payload=json.load(gzip.open(folder/(name+'.json.gz'),'rt'))
   for trade in payload['trades']:
    assert trade['leverage']==1 and not trade['is_short'];orders=[o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
    terminal+=float(trade.get('funding_fees') or 0)
    for i,order in enumerate(orders):
     when=order['order_filled_timestamp'];qty=float(order['amount']);entry=order['ft_is_entry'];delta=qty if entry else -qty;cost=qty*float(order['safe_price']);cash=-cost*(1+trade['fee_open']) if entry else cost*(1-trade['fee_close']);terminal+=cash
     if trade['exit_reason']=='force_exit' and i==len(orders)-1:continue
     date=datetime.datetime.fromtimestamp(when/1000,datetime.timezone.utc).date().isoformat();flow[date]+=cash;events[trade['pair']].append((when,delta))
   assert abs(terminal-payload['final_balance'])<.05
  else:
   for pair,d in raw.items():
    eligible=[r for r in d['daily']['rows'][61:] if window['start']<=datetime.datetime.fromtimestamp(r[0]/1000,datetime.timezone.utc).date().isoformat()<=window['end']]
    if eligible:
     first=eligible[0];budget=10000/len(raw);date=datetime.datetime.fromtimestamp(first[0]/1000,datetime.timezone.utc).date().isoformat();flow[date]-=budget;events[pair].append((first[0],budget/1.0005/float(first[1])))
  for pair,d in raw.items():
   ev=sorted(events[pair]);times=[x[0] for x in ev];prefix=[0.]
   for _,delta in ev:prefix.append(prefix[-1]+delta)
   for fund in d['funding']['rows']:
    when=int(fund['fundingTime']);date=datetime.datetime.fromtimestamp(when/1000,datetime.timezone.utc).date().isoformat()
    if date in flow:flow[date]-=prefix[bisect.bisect_left(times,when)]*float(fund['fundingRate'])*float(fund['markPrice'])
  cash=10000.;quantities={p:0. for p in raw};dayevents={d:[] for d in dates}
  for pair,ev in events.items():
   for when,delta in ev:dayevents[datetime.datetime.fromtimestamp(when/1000,datetime.timezone.utc).date().isoformat()].append((pair,delta))
  reconstructed={}
  for date,record in zip(dates,curve):
   cash+=flow[date]
   for pair,delta in dayevents[date]:quantities[pair]+=delta
   equity=cash+sum(qty*prices[pair].get(date,0) for pair,qty in quantities.items());error=abs(equity-float(record['equity']));assert error<.05,(window['label'],name,date,equity,record['equity']);maximum=max(maximum,error);reconstructed[date]=equity
  if name!='BuyAndHold':
   trace=json.loads((folder/('risk_trace_'+name+'.json')).read_text());assert len(trace)>=len(dates)-2
   for row in trace:
    date=(datetime.date.fromisoformat(row['execution_date'][:10])-datetime.timedelta(days=1)).isoformat()
    if date in reconstructed:assert abs(reconstructed[date]-row['prior_closed_equity'])<.05
  checks+=1
print('Independent stdlib audit passed',checks,'curves; max error',maximum)
(root/'quick_audit_verification.json').write_text(json.dumps(dict(passed=True,curve_checks=checks,max_equity_error=maximum),indent=2)+'\n')
