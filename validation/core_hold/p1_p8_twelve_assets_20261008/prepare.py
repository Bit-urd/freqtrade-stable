import csv,hashlib,json
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent;plan=json.loads((root/'plan.json').read_text());history={};audit=[]
for coin in plan['assets']:
 raw=root/('raw_'+coin+'.json')
 if raw.exists():
  rows=json.loads(raw.read_text());frame=pd.DataFrame(rows)
  frame=frame.rename(columns={0:'date',1:'open',2:'high',3:'low',4:'close',5:'volume'})[['date','open','high','low','close','volume']]
  frame['date']=pd.to_datetime(frame.date.astype('int64'),unit='ms',utc=True)
  for col in ['open','high','low','close','volume']:frame[col]=frame[col].astype(float)
  source='Binance public spot /api/v3/klines; download_sources.json'
 else:
  path=Path('/freqtrade/user_data/data/binance')/(coin+'_USDT-1d.feather');frame=pd.read_feather(path);source=str(path)
 frame=frame.sort_values('date').drop_duplicates('date').reset_index(drop=True)
 frame=frame.loc[frame.date<=pd.Timestamp('2025-02-28',tz='UTC')].reset_index(drop=True)
 assert not frame.empty and frame.date.is_unique
 assert (frame.close>0).all() and (frame.volume>=0).all()
 assert (frame.high>=frame[['open','close','low']].max(axis=1)).all() and (frame.low<=frame[['open','close','high']].min(axis=1)).all()
 file=root/'data'/(coin+'_USDT-1d.feather');frame.to_feather(file);history[coin]=frame
 audit.append(dict(asset=coin,source=source,file=file.name,rows=len(frame),first=str(frame.date.iloc[0]),last=str(frame.date.iloc[-1]),sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
coverage=[];windows=[]
for phase in json.loads((root/'periods.json').read_text()):
 for coin in plan['assets']:
  df=history[coin];start=pd.Timestamp(phase['start'],tz='UTC');end=pd.Timestamp(phase['end'],tz='UTC')
  row=dict(phase=phase['id'],asset=coin,requested_start=phase['start'],requested_end=phase['end'],data_first=str(df.date.iloc[0].date()),status='unavailable',reason='',effective_start='',effective_end='',prior_candles=0,ma150_ready_at_start=False)
  if df.date.iloc[0]>end:row['reason']='本交易所尚无该标的历史'
  elif len(df)<=61 or df.date.iloc[61]>end:row['reason']='本阶段内不足60根完成日线，无法完成策略暖机'
  else:
   effective=max(start,df.date.iloc[61]);available=pd.date_range(effective,end,freq='D',tz='UTC');missing=available.difference(pd.DatetimeIndex(df.date))
   if len(missing):raise AssertionError((coin,phase['id'],'missing requested candles',list(missing)))
   row.update(status='full' if effective==start else 'partial',effective_start=str(effective.date()),effective_end=str(end.date()),prior_candles=int((df.date<effective).sum()),ma150_ready_at_start=bool((df.date<effective).sum()>=150))
   if effective!=start:row['reason']='上市/60日暖机不足；三组统一从有效起点开户'
   else:row['reason']='覆盖完整阶段'
   if not row['ma150_ready_at_start']:row['reason']+='；MA150尚未形成，策略按原规则等待'
   label=coin+'_'+phase['id'];windows.append(dict(label=label,universe=coin,pairs=[coin+'/USDT'],phase=phase['id'],start=row['effective_start'],end=row['effective_end'],timerange=row['effective_start'].replace('-','')+'-'+row['effective_end'].replace('-',''),reference_window=label))
  coverage.append(row)
with (root/'coverage.csv').open('w') as f:out=csv.DictWriter(f,fieldnames=list(coverage[0]));out.writeheader();out.writerows(coverage)
(root/'windows.json').write_text(json.dumps(windows,indent=2)+'\n');(root/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
plan.update(status='ready',eligible_cases=len(windows),unavailable_cases=96-len(windows),partial_cases=sum(x['status']=='partial' for x in coverage));(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Prepared',len(windows),'eligible cases;',plan['partial_cases'],'partial;',plan['unavailable_cases'],'unavailable',flush=True)
import os,sys;sys.stdout.flush();os._exit(0)
