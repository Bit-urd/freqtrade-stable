import csv,gzip,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
root=Path(__file__).resolve().parent;parent=root.parent
old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';hold='BuyAndHold'
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p).set_index('date') for p in (root/'data').glob('*-1d.feather')}
btc=history['BTC/USDT'].close;ma=btc.rolling(150).mean();ema=btc.ewm(span=10,adjust=False).mean()
weak=ma.notna() & (btc<ma) & ~((btc>ema)&(ema>ema.shift(1)))
manifest=json.loads((root/'data_audit.json').read_text())
for item in manifest:assert hashlib.sha256((root/'data'/item['file']).read_bytes()).hexdigest()==item['sha256']
for file,digest in json.loads((root/'source_manifest.json').read_text()).items():assert hashlib.sha256((root/file).read_bytes()).hexdigest()==digest
assert hashlib.sha256(Path('/freqtrade/user_data/strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==json.loads((root/'plan.json').read_text())['production_sha256']
positions=[];attribution=[];annual=[];exits=[];replay_matches=exit_checks=risk_checks=stats_checks=0;maxequity=maxcash=0.;cooldown_checks=0
for folder,scope in [(root,'single')]:
 windows=json.loads((folder/'windows.json').read_text());summary=list(csv.DictReader((folder/'summary.csv').open()));idx={(r['window'],r['strategy']):r for r in summary}
 assert len(summary)==len(windows)*3
 for w in windows:
  scope=w['scope'];label=w['label'];pairs=w['valuation_pairs'];dates=pd.date_range(w['start'],w['end'],tz='UTC');n=len(dates);price=np.column_stack([history[p].close.reindex(dates).to_numpy() for p in pairs]);pairidx={p:i for i,p in enumerate(pairs)}
  for name in [old,new,hold]:
   q=np.zeros((n,len(pairs)));flows=np.zeros_like(q);fullcash=1000.
   curve=pd.read_csv(folder/'results'/label/('equity_'+name+'.csv'),index_col=0);equity=curve.equity.to_numpy()
   if name==hold:
    for p,j in pairidx.items():
     available=history[p].iloc[61:];available=available.loc[(available.index>=dates[0])&(available.index<=dates[-1])]
     if len(available):
      day=available.index[0];i=int((day-dates[0]).days);budget=1000/len(pairs);q[i,j]=budget/1.001/float(history[p].loc[day,'open']);flows[i,j]=-budget
   else:
    payload=json.load(gzip.open(folder/'results'/label/(name+'.json.gz'),'rt'));trades=payload['trades']
    assert all(t['pair'] in w['pairs'] for t in trades)
    for t in trades:
     entry_day=pd.Timestamp(t['open_date']);prior_signal=entry_day-pd.Timedelta(days=1)
     if not bool(btc.loc[prior_signal]>ma.loc[prior_signal]):
      prior_closed=[pd.Timestamp(pt['close_date']) for pt in trades if pt is not t and pt['pair']==t['pair'] and pd.Timestamp(pt['close_date'])<=entry_day]
      if prior_closed:assert (entry_day-max(prior_closed)).total_seconds()>=14*86400
      cooldown_checks+=1
     orders=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
     for k,o in enumerate(orders):
      entry=o['ft_is_entry'];amount=float(o['amount']);rate=float(o['safe_price']);fee=float(t['fee_open'] if entry else t['fee_close']);flow=-amount*rate*(1+fee) if entry else amount*rate*(1-fee);fullcash+=flow
      if t['exit_reason']=='force_exit' and k==len(orders)-1:continue
      day=pd.to_datetime(o['order_filled_timestamp'],unit='ms',utc=True).floor('D');i=int((day-dates[0]).days);assert 0<=i<n
      j=pairidx[t['pair']];q[i,j]+=amount if entry else -amount;flows[i,j]+=flow
     if t['exit_reason']=='trend_to_cash':
      day=pd.Timestamp(t['close_date']);signal=day-pd.Timedelta(days=1);required=1 if name==old else 2
      assert all(bool(weak.loc[signal-pd.Timedelta(days=k)]) for k in range(required));exit_checks+=1
      h=history[t['pair']].close;record=dict(scope=scope,window=label,strategy=name,pair=t['pair'],exit_date=day.isoformat(),profit_abs=t['profit_abs'])
      for step in [5,10]:
       target=day+pd.Timedelta(days=step);record[f'price_return_{step}d_pct']=(float(h.loc[target])/float(t['close_rate'])-1)*100 if target in h.index and target<=dates[-1] else None
      exits.append(record)
    error=abs(fullcash-float(payload['final_balance']));assert error<.05;maxcash=max(maxcash,error)
    trace=json.loads((folder/'results'/label/('risk_trace_'+name+'.json')).read_text())
    for t in trace:
     day=pd.Timestamp(t['execution_date'])-pd.Timedelta(days=1)
     if day in dates:
      assert abs(float(t['prior_closed_equity'])-equity[int((day-dates[0]).days)])<.05;risk_checks+=1
   q=np.cumsum(q,axis=0);assert q.min()>-1e-5;assert not ((abs(q)>1e-8)&np.isnan(price)).any();values=np.nan_to_num(q*price);cash=1000+flows.sum(axis=1).cumsum()
   error=float(np.max(np.abs(cash+values.sum(axis=1)-equity)));assert error<.05;maxequity=max(maxequity,error)
   assert np.max(np.abs(cash-curve.cash.to_numpy()))<.05
   if name==hold:assert abs((1000-cash[-1])*.001/1.001-float(idx[label,name]['normal_fees']))<1e-6
   computed=dict(return_pct=(equity[-1]/1000-1)*100,wallet_drawdown_pct=float(np.max(1-equity/np.maximum(1000,np.maximum.accumulate(equity)))*100),mean_idle_cash_pct=float((cash/equity).mean()*100))
   for key,value in computed.items():assert abs(value-float(idx[label,name][key]))<1e-6;stats_checks+=1
   weights=values/equity[:,None];positions.append(dict(scope=scope,window=label,strategy=name,max_single_coin_weight_pct=float(weights.max()*100),mean_cash_pct=float((cash/equity).mean()*100)))
   daily_pnl=np.diff(values,axis=0,prepend=np.zeros((1,len(pairs))))+flows
   assert abs(daily_pnl.sum()-(equity[-1]-1000))<.05
   for p,j in pairidx.items():attribution.append(dict(scope=scope,window=label,strategy=name,pair=p,profit_abs=float(daily_pnl[:,j].sum())))
   previous=1000.
   for year in dict.fromkeys(dates.year):
    mask=dates.year==year;yearvalues=equity[mask];v=np.concatenate(([previous],yearvalues));dd=float(np.max(1-v/np.maximum.accumulate(v))*100)
    annual.append(dict(scope=scope,window=label,year=year,strategy=name,return_pct=(yearvalues[-1]/previous-1)*100,drawdown_pct=dd));previous=yearvalues[-1]
   replay_matches+=1
for file,data in [('position_audit.csv',positions),('profit_attribution.csv',attribution),('continuous_annual.csv',annual),('btc_exit_events.csv',exits)]:
 with (root/file).open('w') as f:writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)

(root/'audit_verification.json').write_text(json.dumps(dict(passed=True,curve_checks=replay_matches,summary_metric_checks=stats_checks,actual_btc_exit_checks=exit_checks,actual_weak_btc_entry_cooldown_checks=cooldown_checks,daily_risk_equity_checks=risk_checks,max_equity_error=maxequity,max_cash_error=maxcash,source_and_data_hashes_unchanged=True),indent=2)+'\n')
h=history['HYPE/USDT'];dates=h.index;qty=1000/1.001/float(h.iloc[0]['open']);equity=qty*h.close;peak=equity.cummax().clip(lower=1000);hcurve=pd.DataFrame({'cash':0.,'equity':equity});hcurve.to_csv(root/'hype_listing_hold_only.csv')
(root/'hype_listing_hold_only.json').write_text(json.dumps(dict(start=str(dates[0].date()),end=str(dates[-1].date()),days=len(h),return_pct=(float(equity.iloc[-1])/1000-1)*100,wallet_drawdown_pct=float((1-equity/peak).max()*100),strategy_status='Unavailable: only13 own completed candles, no60-day warmup orMA150; hold result is descriptive only'),indent=2)+'\n')
print('Audit passed',replay_matches,'curves; cash error',maxcash,flush=True)
sys.stdout.flush();sys.stderr.flush()
import os;os._exit(0)
