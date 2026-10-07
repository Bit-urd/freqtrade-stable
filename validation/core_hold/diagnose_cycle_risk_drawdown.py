"""从成交逐币重建权益，解释最大回撤的阶段、标的和持仓回吐。"""
from pathlib import Path
import json,gzip,os,sys,datetime,argparse
import pandas as pd
parser=argparse.ArgumentParser();parser.add_argument('--results-folder',default='production_comparison_2023_latest');parser.add_argument('--output-folder',default='cycle_risk_drawdown_diagnosis');parser.add_argument('--strategy',default='BtcCoinGuardCycleRiskStrategy');args=parser.parse_args()
R=Path('/research');D=R/args.output_folder;D.mkdir(parents=True,exist_ok=True)
SRC=R/'production_comparison_2023_latest';F=R/args.results_folder/'results/continuous_2023_latest';NAME=args.strategy;PAIRS=['BTC/USDT','SOL/USDT','ETH/USDT']
curve=pd.read_csv(F/('equity_'+NAME+'.csv'),index_col=0,parse_dates=True);curve.index=pd.to_datetime(curve.index,utc=True);dates=curve.index
hist={p:pd.read_feather(SRC/'data'/(p.replace('/','_')+'-1d.feather')).set_index('date') for p in PAIRS}
prices=pd.DataFrame({p:h.close.reindex(dates) for p,h in hist.items()});assert prices.notna().all().all()
payload=json.load(gzip.open(F/(NAME+'.json.gz'),'rt'));trades=payload['trades']
flows=pd.DataFrame(0.,index=dates,columns=PAIRS);dq=flows.copy();fees=flows.copy();execution=flows.copy();orders=[];trade_legs=[]
for i,t in enumerate(trades):
 p=t['pair'];tf=pd.Series(0.,index=dates);tq=tf.copy();tfees=tf.copy();filled=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
 for j,o in enumerate(filled):
  if t['exit_reason']=='force_exit' and j==len(filled)-1:continue
  day=pd.to_datetime(o['order_filled_timestamp'],unit='ms',utc=True).floor('D');amount=float(o['amount']);rate=float(o['safe_price']);entry=bool(o['ft_is_entry']);signed=amount if entry else -amount
  fee=amount*rate*float(t['fee_open'] if entry else t['fee_close']);cash=-signed*rate-fee
  flows.loc[day,p]+=cash;dq.loc[day,p]+=signed;fees.loc[day,p]+=fee
  execution.loc[day,p]+=signed*(prices.loc[day,p]-rate)
  tf.loc[day]+=cash;tq.loc[day]+=signed;tfees.loc[day]+=fee
  orders.append({'trade_id':i,'pair':p,'day':str(day.date()),'kind':('open' if j==0 else 'add') if entry else ('close' if j==len(filled)-1 else 'reduce'),'notional':amount*rate,'fee':fee})
 q=tq.cumsum();leg=tf.cumsum()+q*prices[p]
 trade_legs.append({'trade_id':i,'trade':t,'equity_delta':leg,'qty':q,'fees':tfees})
qty=dq.cumsum();sleeves=1000/3+flows.cumsum()+qty*prices;total=sleeves.sum(axis=1)
assert (total-curve.equity).abs().max()<1e-6
carry=qty.shift(1,fill_value=0)*prices.diff().fillna(0);daypnl=carry+execution-fees
assert (daypnl.sum(axis=1)-(curve.equity.diff().fillna(curve.equity.iloc[0]-1000))).abs().max()<1e-6
peak=curve.equity.cummax().clip(lower=1000);drawdown=1-curve.equity/peak;valley=drawdown.idxmax();top=curve.loc[:valley,'equity'].idxmax();peakvalue=float(curve.loc[top,'equity']);valleyvalue=float(curve.loc[valley,'equity']);loss=peakvalue-valleyvalue
sleeves.to_csv(D/'coin_daily_equity.csv');(qty*prices).to_csv(D/'coin_daily_positions.csv');daypnl.to_csv(D/'coin_daily_pnl.csv');fees.to_csv(D/'coin_daily_fees.csv');pd.DataFrame(orders).to_csv(D/'filled_order_events.csv',index=False)
traces=json.loads((F/('risk_trace_'+NAME+'.json')).read_text());trace=pd.DataFrame(traces);trace.index=pd.to_datetime(trace.execution_date,utc=True)
# 全历史峰值和回撤来自真实权益，完全独立于内部风控峰值。
coin_rows=[];clipped=[]
for p in PAIRS:
 delta=float(sleeves.loc[valley,p]-sleeves.loc[top,p]);segment=(dates>top)&(dates<=valley)
 attributed={'pair':p,'peak_sleeve_equity':float(sleeves.loc[top,p]),'valley_sleeve_equity':float(sleeves.loc[valley,p]),'pnl':delta,'share_of_total_loss_pct':-delta/loss*100,'contribution_to_global_drawdown_pp':-delta/peakvalue*100,'peak_position_value':float((qty*prices).loc[top,p]),'peak_position_weight_pct':float((qty*prices).loc[top,p]/peakvalue*100),'carry_pnl':float(carry.loc[segment,p].sum()),'execution_pnl':float(execution.loc[segment,p].sum()),'fees':float(fees.loc[segment,p].sum())}
 oldpnl=newpnl=0.;newlosers=newwins=0
 for leg in trade_legs:
  t=leg['trade']
  if t['pair']!=p:continue
  net=float(leg['equity_delta'].loc[valley]-leg['equity_delta'].loc[top])
  if abs(net)<1e-8:continue
  old=abs(float(leg['qty'].loc[top]))>1e-8
  oldpnl+=net if old else 0;newpnl+=net if not old else 0
  if not old:newlosers+=int(net<0);newwins+=int(net>0)
  clipped.append({'pair':p,'trade_id':leg['trade_id'],'open':t['open_date'][:10],'close':t['close_date'][:10],'exit_reason':t['exit_reason'],'category':'峰值时已有持仓' if old else '峰值后新入场','clipped_pnl':net,'whole_trade_profit':t['profit_abs'],'fees_in_interval':float(leg['fees'].loc[segment].sum())})
 assert abs(oldpnl+newpnl-delta)<1e-6
 attributed.update(existing_holdings_pnl=oldpnl,new_entries_pnl=newpnl,new_entries_losing_count=newlosers,new_entries_winning_count=newwins)
 coin_rows.append(attributed)
pd.DataFrame(coin_rows).to_csv(D/'worst_drawdown_coin_attribution.csv',index=False);pd.DataFrame(clipped).sort_values('clipped_pnl').to_csv(D/'clipped_trade_attribution.csv',index=False)
# 用日历季度分段，避免手工挑选好看的局部走势。相邻区间首尾连接。
boundaries=[top]+[d for d in dates if top<d<valley and d.is_quarter_end]+[valley];stages=[]
for a,b in zip(boundaries,boundaries[1:]):
 row={'start':str(a.date()),'end':str(b.date()),'start_equity':float(curve.loc[a,'equity']),'end_equity':float(curve.loc[b,'equity']),'pnl':float(curve.loc[b,'equity']-curve.loc[a,'equity']),'return_pct':(curve.loc[b,'equity']/curve.loc[a,'equity']-1)*100,'global_drawdown_at_end_pct':float(drawdown.loc[b]*100)}
 for p in PAIRS:row[p.split('/')[0]+'_pnl']=float(sleeves.loc[b,p]-sleeves.loc[a,p])
 ev=[e for e in orders if str(a.date())<e['day']<=str(b.date())];row.update(new_entries=sum(e['kind']=='open' for e in ev),closes=sum(e['kind']=='close' for e in ev),fees=sum(e['fee'] for e in ev))
 stages.append(row)
pd.DataFrame(stages).to_csv(D/'worst_drawdown_quarter_stages.csv',index=False)
# 日损失、仓位集中与风险恢复事件。
worst_days=[]
for day in daypnl.sum(axis=1).nsmallest(12).index:
 prev=day-pd.Timedelta(days=1);row={'date':str(day.date()),'account_pnl':float(daypnl.loc[day].sum()),'daily_return_pct':float(daypnl.loc[day].sum()/curve.loc[prev,'equity']*100) if prev in dates else None}
 for p in PAIRS:row[p.split('/')[0]+'_pnl']=float(daypnl.loc[day,p]);row[p.split('/')[0]+'_prior_weight_pct']=float((qty*prices).loc[prev,p]/curve.loc[prev,'equity']*100) if prev in dates else 0
 worst_days.append(row)
pd.DataFrame(worst_days).to_csv(D/'worst_daily_losses.csv',index=False)
rearms=[]
for t in traces:
 if t.get('risk_epoch_reset'):
  day=pd.Timestamp(t['execution_date']);prev=day-pd.Timedelta(days=1)
  rearms.append({'date':str(day.date()),'global_drawdown_pct':float(drawdown.loc[prev]*100) if prev in dates else 0,'internal_drawdown_pct':t['drawdown']*100,'risk_fraction':t['risk_fraction']})
pd.DataFrame(rearms).to_csv(D/'risk_rearm_events.csv',index=False)
# 独立的新高到恢复区间，不把同一大回撤的局部谷底当独立事件。
episodes=[];active=None;running=1000.;running_day=dates[0]
for day,equity in curve.equity.items():
 if equity>=running:
  if active:active['recovery']=str(day.date());episodes.append(active);active=None
  running=float(equity);running_day=day
 else:
  if active is None:active={'peak':str(running_day.date()),'valley':str(day.date()),'peak_equity':running,'valley_equity':float(equity),'drawdown_pct':(1-equity/running)*100,'recovery':None}
  if equity<active['valley_equity']:active.update(valley=str(day.date()),valley_equity=float(equity),drawdown_pct=(1-equity/running)*100)
if active:episodes.append(active)
pd.DataFrame(sorted(episodes,key=lambda x:x['drawdown_pct'],reverse=True)[:10]).to_csv(D/'largest_drawdown_episodes.csv',index=False)
# 初始等权的持有会随行情改变权重；风控阶段不是实际市场敞口。
mask=(trace.index>top)&(trace.index<=valley);fractions=trace.loc[mask,'risk_fraction'].value_counts().to_dict()
summary={'strategy':NAME,'start':str(dates[0].date()),'end':str(dates[-1].date()),'worst_peak':str(top.date()),'worst_valley':str(valley.date()),'peak_equity':peakvalue,'valley_equity':valleyvalue,'loss_usdt':loss,'drawdown_pct':float(drawdown.loc[valley]*100),'coins':coin_rows,'stages':stages,'risk_stage_days_in_peak_valley':{str(k):int(v) for k,v in fractions.items()},'fees_during_drawdown':float(fees.loc[(dates>top)&(dates<=valley)].sum().sum()),'worst_days':worst_days,'risk_rearms':rearms,'max_total_equity_reconciliation_error':float((total-curve.equity).abs().max()),'max_daily_pnl_reconciliation_error':float((daypnl.sum(axis=1)-curve.equity.diff().fillna(curve.equity.iloc[0]-1000)).abs().max()),'not_causal_independent_effects':'持仓、重新入场及手续费是同一账本分解，不将整笔交易盈利误当峰值后盈利；不把回撤阶段的事后边界用于交易规则。'}
(D/'diagnosis.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:summary[k] for k in ['worst_peak','worst_valley','drawdown_pct','coins','stages','risk_stage_days_in_peak_valley','fees_during_drawdown']},ensure_ascii=False,indent=2),flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
