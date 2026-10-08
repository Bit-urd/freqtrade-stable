import csv,gzip,json,runpy
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p).set_index('date') for p in (root.parent/'independent_trend_optimization_20261008/data').glob('*-1d.feather')}
risk={}
for pair,h in history.items():
 ma=h.close.rolling(150).mean();ema=h.close.ewm(span=10,adjust=False).mean()
 risk[pair]=ma.notna() & ((h.close>ma)|((h.close>ema)&(ema>ema.shift(1))))
btc=history['BTC/USDT'];strict=btc.close>btc.close.rolling(150).mean()
strict.to_frame('btc_strict').to_csv(root/'btc_strict.csv')
rows=[];events=[]
for w in json.loads((root/'windows.json').read_text()):
 payload=json.load(gzip.open(root/'results'/w['label']/'BtcCoinGuardCycleRiskStrategy.json.gz','rt'))
 trades=payload['trades'];count=0
 for pair in w['pairs']:
  own=[t for t in trades if t['pair']==pair]
  for day in pd.date_range(w['start'],w['end'],tz='UTC'):
   signal=day-pd.Timedelta(days=1)
   if bool(strict.get(signal,False)) or not bool(risk['BTC/USDT'].get(signal,False)) or not bool(risk[pair].get(signal,False)):continue
   if any(pd.Timestamp(t['open_date'])<=day<=pd.Timestamp(t['close_date']) for t in own):continue
   closed=[pd.Timestamp(t['close_date']) for t in own if t['exit_reason']!='force_exit' and pd.Timestamp(t['close_date'])<day]
   if not closed:continue
   age=(day-max(closed)).total_seconds()/86400
   if 7<=age<14:
    count+=1;events.append(dict(window=w['label'],pair=pair,execution_day=day.isoformat(),days_after_close=age))
 rows.append(dict(window=w['label'],blocked_entry_days_between_7_and_14=count))
for name,data in [('cooldown_diagnosis.csv',rows),('cooldown_opportunities.csv',events)]:
 with (root/name).open('w') as f:
  keys=list(data[0]) if data else ['window','pair','execution_day','days_after_close'];out=csv.DictWriter(f,fieldnames=keys);out.writeheader();out.writerows(data)
print('Cooldown diagnosis',json.dumps(rows),flush=True)
assert len(events)>0,'No 7-day cooldown opportunity on original path'
plan=json.loads((root/'plan.json').read_text());plan['status']='running';plan['diagnosis']='Flat-pair original-path entry-permitted days 7 <= time since last close < 14; exclude same-day open/close ambiguity.';(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
runpy.run_path(str(root/'run.py'),run_name='__main__')
