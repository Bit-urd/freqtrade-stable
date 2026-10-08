"""Reconstruct actual daily coin weights from all fills; do not rerun strategies."""
import csv,gzip,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
root=Path(__file__).resolve().parent
folders=['btc_exit_confirmation_20261008','recovery_speed_20261008','short_cooldown_20261008','limited_shared_cash_20261008']
prices={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p).set_index('date') for p in (root/'independent_trend_optimization_20261008/data').glob('*-1d.feather')}
cache={};allrows=[];maxerror=0
for folder in folders:
 r=root/folder;rows=[]
 for w in json.loads((r/'windows.json').read_text()):
  summary=[x for x in csv.DictReader((r/'summary.csv').open()) if x['window']==w['label']]
  pairs=w['pairs'];dates=pd.date_range(w['start'],w['end'],tz='UTC');days=len(dates);matrix=np.column_stack([prices[p].close.reindex(dates).to_numpy() for p in pairs])
  pairindex={p:i for i,p in enumerate(pairs)}
  for record in summary:
   name=record['strategy'];key=(w['label'],name)
   if key in cache:metrics=cache[key]
   else:
    curve=pd.read_csv(r/'results'/w['label']/('equity_'+name+'.csv'),index_col=0)
    if name=='BuyAndHold':
     quantities=np.array([1000/len(pairs)/1.001/float(prices[p].loc[dates[0],'open']) for p in pairs]);values=matrix*quantities
    else:
     quantities=np.zeros((days,len(pairs)))
     trades=json.load(gzip.open(r/'results'/w['label']/(name+'.json.gz'),'rt'))['trades']
     for t in trades:
      orders=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
      if t['exit_reason']=='force_exit':orders=orders[:-1]
      for o in orders:
       day=int((o['order_filled_timestamp']/1000-dates[0].timestamp())//86400);assert 0<=day<days
       quantities[day,pairindex[t['pair']]]+=float(o['amount'])*(1 if o['ft_is_entry'] else -1)
     quantities=np.cumsum(quantities,axis=0);assert quantities.min()>-1e-5
     values=quantities*matrix
    values=np.nan_to_num(values);equity=curve.equity.to_numpy();error=float(np.max(np.abs(curve.cash.to_numpy()+values.sum(axis=1)-equity)));assert error<.05,(folder,w['label'],name,error);maxerror=max(maxerror,error)
    weights=values/equity[:,None];counts=(values>1.).sum(axis=1)
    metrics=dict(max_single_coin_weight_pct=float(weights.max()*100),mean_largest_coin_weight_pct=float(weights.max(axis=1).mean()*100),max_concurrent_coins=int(counts.max()),mean_concurrent_coins=float(counts.mean()),max_equity_reconstruction_error=error)
    cache[key]=metrics
   row=dict(window=w['label'],strategy=name,**metrics);rows.append(row);allrows.append(dict(experiment=folder,**row))
 with (r/'position_audit.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(root/'optimization_position_verification.json').write_text(json.dumps(dict(passed=True,unique_curves=len(cache),comparison_rows=len(allrows),max_equity_error=maxerror),indent=2)+'\n')
print('Audited',len(cache),'unique curves; max error',maxerror,flush=True)
sys.stdout.flush();sys.stderr.flush()
import os;os._exit(0)
