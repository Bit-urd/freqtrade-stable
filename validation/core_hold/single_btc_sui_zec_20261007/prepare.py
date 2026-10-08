import json,hashlib,shutil
from pathlib import Path
import pandas as pd
out=Path('/research/single_btc_sui_zec_20261007');data=out/'data'
for tf in ['1d','1w']:shutil.copy(Path('/research/production_comparison_2023_latest/data')/('BTC_USDT-'+tf+'.feather'),data/('BTC_USDT-'+tf+'.feather'))
for coin in ['SUI','ZEC']:
 for tf in ['1d','1w']:
  obj=json.loads((out/(coin+'USDT-'+tf+'.json')).read_text())
  h=pd.DataFrame([dict(date=pd.to_datetime(r[0],unit='ms',utc=True),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4]),volume=float(r[5])) for r in obj['rows']])
  assert h.date.is_unique and h.date.is_monotonic_increasing
  if tf=='1d':assert not pd.date_range(h.date.iloc[0],h.date.iloc[-1],freq='D').difference(pd.DatetimeIndex(h.date)).size
  h.to_feather(data/(coin+'_USDT-'+tf+'.feather'))
audit=[]
for p in data.glob('*.feather'):
 h=pd.read_feather(p);audit.append(dict(file=p.name,rows=len(h),first=str(h.date.iloc[0]),last=str(h.date.iloc[-1]),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
for w in json.loads((out/'windows.json').read_text()):
 h=pd.read_feather(data/(w['pair'].replace('/','_')+'-1d.feather'));ds=pd.date_range(w['start'],w['end'],tz='UTC',freq='D')
 assert not ds.difference(pd.DatetimeIndex(h.date)).size
 assert (h.date<pd.Timestamp(w['start'],tz='UTC')).sum()>60
(out/'data_audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit,indent=2))
