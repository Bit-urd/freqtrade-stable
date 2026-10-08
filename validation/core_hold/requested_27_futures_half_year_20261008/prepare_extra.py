import json,hashlib,shutil,sys,os
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent;prior=root.parent/'without_zec_pump_20261008'
assets=['BNB','DOGE']
(root/'data').mkdir(exist_ok=True);(root/'strategies').mkdir(exist_ok=True);audit=json.loads((root/'data_audit.json').read_text())
for asset in assets:
 raw=json.loads((root/'raw'/(asset+'.json')).read_text());df=pd.DataFrame(raw['daily']['rows']).rename(columns={0:'date',1:'open',2:'high',3:'low',4:'close',5:'volume'})[['date','open','high','low','close','volume']];df.date=pd.to_datetime(df.date,unit='ms',utc=True)
 for c in ['open','high','low','close','volume']:df[c]=df[c].astype(float)
 assert not df.date.duplicated().any();assert pd.DatetimeIndex(df.date).equals(pd.date_range(df.date.iloc[0],df.date.iloc[-1],freq='D'));assert df.date.iloc[-1]==pd.Timestamp('2026-10-07',tz='UTC');assert (df.close>0).all()
 filename=asset+'_USDT_USDT-1d-futures.feather';df.to_feather(root/'data'/filename)
 f=pd.DataFrame(raw['funding']['rows']);f['date']=pd.to_datetime(f.fundingTime,unit='ms',utc=True);f['rate']=f.fundingRate.astype(float);f['mark']=f.markPrice.astype(float);assert (f.mark>0).all();assert not f.date.duplicated().any()
 for kind,value,col in [('funding_rate',f.rate,'1h'),('mark',f.mark,'1h')]:
  frame=pd.DataFrame({'date':f.date,'open':value,'high':value,'low':value,'close':value,'volume':0.});frame.to_feather(root/'data'/(asset+'_USDT_USDT-'+col+'-'+kind+'.feather'))
 item=dict(asset=asset,pair=asset+'/USDT:USDT',file=filename,first=str(df.date.iloc[0].date()),last='2026-10-07',rows=len(df),funding_rows=len(f),warm_start=str(df.date.iloc[61].date()) if len(df)>61 else None,ma150_start=str(df.date.iloc[150].date()) if len(df)>150 else None,sha256=hashlib.sha256((root/'data'/filename).read_bytes()).hexdigest());audit.append(item)
(root/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
for asset in assets:
 for f in (root/'data').glob(asset+'_USDT_USDT-*.feather'):shutil.copy2(f,root/'data/futures'/f.name)
windows=json.loads((root/'windows.json').read_text());pairs=[a+'/USDT:USDT' for a in ['BTC','ETH','BNB','LINK','XRP','UNI','DOGE','SOL','ARB']]
windows.append(dict(label='Official9',universe='Official9',pairs=pairs,valuation_pairs=pairs,slots=9,scope='official_pool_control',phase='',start='2026-04-08',end='2026-10-07',timerange='20260408-20261007'))
(root/'windows.json').write_text(json.dumps(windows,indent=2)+'\n')
print('Prepared existing official nine-asset futures control',flush=True);os._exit(0)
