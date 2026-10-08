"""Exact daily per-coin P&L gaps; descriptive signal-state attribution, no retuning."""
import collections,csv,datetime,gzip,json,math
from pathlib import Path
root=Path(__file__).resolve().parent;study=root.parent;UTC=datetime.timezone.utc
labels=['Main10_full_cycle','Main10_mature11_control','Mature11_full_cycle','Requested12_mature11_cash'];old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';names=[old,new]
windows={w['label']:w for w in json.loads((study/'windows.json').read_text())};assets=json.loads((study/'plan.json').read_text())['assets'];history={};states={}
for a in assets:
 rows=json.loads((study/'raw/spot'/(a+'.json')).read_text());h={datetime.datetime.fromtimestamp(r[0]/1000,UTC).date():dict(open=float(r[1]),close=float(r[4])) for r in rows};history[a]=h;queue=collections.deque();total=0;ema=None;st={}
 for day,r in h.items():
  c=r['close'];previous_ema=ema;ema=c if ema is None else 2/11*c+9/11*ema;queue.append(c);total+=c
  if len(queue)>150:total-=queue.popleft()
  ma=total/150 if len(queue)==150 else None;recovery=previous_ema is not None and c>ema and ema>previous_ema
  st[day]=dict(entry=ma is not None and (c>ma or recovery),strict=ma is not None and c>ma,weak=ma is not None and c<ma and not recovery)
 states[a]=st
summary=list(csv.DictReader((study/'summary.csv').open()));si={(r['window'],r['strategy']):r for r in summary};attr=list(csv.DictReader((study/'profit_attribution.csv').open()));ai={(r['window'],r['strategy'],r['pair']):float(r['profit_abs']) for r in attr}
coinrows=[];state_rows=[];monthly=[];daily=[];riskrows=[];entries=[];maxerror=0.
for label in labels:
 w=windows[label];start=datetime.date.fromisoformat(w['start']);end=datetime.date.fromisoformat(w['end']);dates=[start+datetime.timedelta(days=i) for i in range((end-start).days+1)];coins=[p.split('/')[0] for p in w['pairs']];budget=1000/w['slots']
 for name in names:
  payload=json.load(gzip.open(study/'results'/label/(name+'.json.gz'),'rt'));trades=payload['trades'];orders=collections.defaultdict(list);closed={a:[] for a in coins};entryevents=[]
  for t in trades:
   a=t['pair'].split('/')[0];filled=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
   if t['exit_reason']!='force_exit':closed[a].append(datetime.datetime.fromisoformat(t['close_date']))
   for k,o in enumerate(filled):
    if t['exit_reason']=='force_exit' and k==len(filled)-1:continue
    d=datetime.datetime.fromtimestamp(o['order_filled_timestamp']/1000,UTC).date();isentry=o['ft_is_entry'];amount=float(o['amount']);price=float(o['safe_price']);fee=float(t['fee_open'] if isentry else t['fee_close']);orders[d,a].append((amount if isentry else -amount,price,amount*price*fee));
   if a in ['ZEC','PUMP']:
    entries.append(dict(window=label,strategy=name,asset=a,entry=t['open_date'][:10],exit=t['close_date'][:10],exit_reason=t['exit_reason'],net_profit=float(t['profit_abs']),reported_stake=float(t['stake_amount'])))
  traces=json.loads((study/'results'/label/('risk_trace_'+name+'.json')).read_text());counter=collections.Counter(str(t['risk_fraction']) for t in traces)
  riskrows.append(dict(window=label,strategy=name,observed_risk_days=len(traces),days_at_100=counter['1.0'],days_at_75=counter['0.75'],days_at_50=counter['0.5']))
  for a in coins:
   h=history[a];qb=budget/1.001/h[start]['open'];qt=0.;prevsv=0.;prevbv=0.;cumstrategy=cumhold=totalfees=0.;stats=collections.defaultdict(lambda:dict(days=0,strategy_pnl=0.,hold_pnl=0.,gap=0.));months=collections.defaultdict(lambda:dict(strategy_pnl=0.,hold_pnl=0.,gap=0.));held=0;meanq=0.;q_held=0.;trade_days=0
   for day in dates:
    flows=0.;events=orders[day,a];dayfee=0.
    for delta,price,fee in events:qt+=delta;flows-=delta*price+fee;dayfee+=fee
    sv=qt*h[day]['close'];bv=qb*h[day]['close'];sp=sv-prevsv+flows;bp=bv-prevbv-(budget if day==start else 0.);gap=bp-sp;cumstrategy+=sp;cumhold+=bp;totalfees+=dayfee;prevsv=sv;prevbv=bv
    prior=day-datetime.timedelta(days=1);b=states['BTC'][prior];own=states[a][prior]
    last_closed=max((d for d in closed[a] if d.date()<day),default=None);cold=last_closed is not None and (datetime.datetime.combine(day,datetime.time(),UTC)-last_closed).total_seconds()<14*86400 and not b['strict']
    if events:state='交易日';trade_days+=1
    elif qt>1e-8:state='持仓日，仓位数量与持有不同'
    elif not b['entry']:state='空仓且BTC禁止入场'
    elif not own['entry']:state='空仓且个币禁止入场'
    elif cold:state='空仓且弱BTC冷却未满14天'
    else:state='空仓，其他执行条件'
    s=stats[state];s['days']+=1;s['strategy_pnl']+=sp;s['hold_pnl']+=bp;s['gap']+=gap;m=months[str(day)[:7]];m['strategy_pnl']+=sp;m['hold_pnl']+=bp;m['gap']+=gap
    held+=qt>1e-8;meanq+=qt/qb
    if qt>1e-8:q_held+=qt/qb
    if a in ['ZEC','PUMP']:daily.append(dict(window=label,strategy=name,asset=a,date=str(day),state=state,strategy_qty=qt,hold_qty=qb,strategy_daily_pnl=sp,hold_daily_pnl=bp,gap=gap,btc_entry_allowed=b['entry'],own_entry_allowed=own['entry'],btc_strict=b['strict'],cooldown=cold))
   err=max(abs(cumstrategy-ai[label,name,a+'/USDT']),abs(cumhold-ai[label,'BuyAndHold',a+'/USDT']));assert err<1e-6,(label,name,a,err);maxerror=max(maxerror,err)
   assert abs(sum(s['gap'] for s in stats.values())-(cumhold-cumstrategy))<1e-6
   coinrows.append(dict(window=label,strategy=name,asset=a,strategy_profit=cumstrategy,hold_profit=cumhold,gap=cumhold-cumstrategy,days=len(dates),held_days=held,held_day_pct=held/len(dates)*100,mean_qty_vs_hold_pct=meanq/len(dates)*100,mean_qty_while_held_vs_hold_pct=q_held/held*100 if held else 0,end_qty_vs_hold_pct=qt/qb*100,fees=totalfees,trade_days=trade_days))
   for state,s in stats.items():state_rows.append(dict(window=label,strategy=name,asset=a,state=state,**s))
   for month,m in months.items():monthly.append(dict(window=label,strategy=name,asset=a,month=month,**m))
for file,rows in [('coin_gap.csv',coinrows),('signal_state_gap.csv',state_rows),('monthly_gap.csv',monthly),('zec_pump_daily.csv',daily),('risk_stage_days.csv',riskrows),('zec_pump_trades.csv',entries)]:
 with (root/file).open('w') as f:writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(root/'verification.json').write_text(json.dumps(dict(passed=True,coin_pnl_reconstructions=len(coinrows),maximum_pnl_error=maxerror,state_gap_sums_verified=True,signal_classification='Completed prior-day indicators; trading days separate. Descriptive attribution, not rule-removal counterfactual.'),indent=2)+'\n')
print('Reconciled',len(coinrows),'coin P&L paths; maximum error',maxerror)
for label in labels:
 cs=[r for r in coinrows if r['window']==label and r['strategy']==new];gap=sum(r['gap'] for r in cs);print('\n',label,'totalgap',round(gap,2))
 for r in sorted(cs,key=lambda r:r['gap'],reverse=True)[:4]:print(r['asset'],'gap',round(r['gap'],2),'daysheld',round(r['held_day_pct'],1),'qtymean',round(r['mean_qty_vs_hold_pct'],1),'endqty',round(r['end_qty_vs_hold_pct'],1),'fees',round(r['fees'],2))
 if label==labels[0]:
  for s in state_rows:
   if s['window']==label and s['strategy']==new and s['asset']=='ZEC':print('ZECstate',s['state'],s['days'],round(s['gap'],2))
  for m in sorted((m for m in monthly if m['window']==label and m['strategy']==new and m['asset']=='ZEC'),key=lambda m:m['gap'],reverse=True)[:5]:print('ZECmonth',m['month'],round(m['gap'],2),round(m['hold_pnl'],2),round(m['strategy_pnl'],2))
