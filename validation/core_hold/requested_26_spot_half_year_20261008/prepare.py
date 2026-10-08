import json,os,sys,hashlib
from pathlib import Path
import pandas as pd
r=Path(__file__).resolve().parent
(r/'data').mkdir(exist_ok=True)
records=[]
for pair in json.loads((r/'config.json').read_text())['exchange']['pair_whitelist']:
 asset=pair.split('/')[0]; src=r.parent/'requested_27_half_year_20261008'/'raw'/'spot'/(asset+'.json')
 rows=json.loads(src.read_text());df=pd.DataFrame([[pd.to_datetime(x[0],unit='ms',utc=True),*map(float,x[1:6])] for x in rows],columns=['date','open','high','low','close','volume'])
 assert df.date.is_unique and df.date.is_monotonic_increasing
 out=r/'data'/(asset+'_USDT-1d.feather');df.to_feather(out)
 records.append(dict(asset=asset,rows=len(df),first=str(df.date.iloc[0]),last=str(df.date.iloc[-1]),raw_sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
(r/'data_audit.json').write_text(json.dumps(records,indent=2))
print('Prepared',len(records),'spot pairs',flush=True)
sys.stdout.flush();os._exit(0)
