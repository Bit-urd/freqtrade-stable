import json,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
root=Path(__file__).resolve().parent
start=int(datetime(2017,1,1,tzinfo=timezone.utc).timestamp()*1000);end=int(datetime(2025,3,1,tzinfo=timezone.utc).timestamp()*1000)-1
sources=[]
for coin in ['DOT','ARB','APT']:
 rows=[];cursor=start
 while cursor<=end:
  url='https://api.binance.com/api/v3/klines?'+urlencode(dict(symbol=coin+'USDT',interval='1d',startTime=cursor,endTime=end,limit=1000))
  for attempt in range(3):
   try:
    with urlopen(url,timeout=30) as reply:batch=json.load(reply)
    assert isinstance(batch,list),batch;break
   except Exception:
    if attempt==2:raise
    time.sleep(1+attempt)
  sources.append(dict(asset=coin,url=url,rows=len(batch)))
  if not batch:break
  rows.extend(batch);nexttime=int(batch[-1][0])+86400000;assert nexttime>cursor;cursor=nexttime
  if len(batch)<1000:break
 (root/('raw_'+coin+'.json')).write_text(json.dumps(rows)+'\n')
 print(coin,len(rows),'daily bars',flush=True)
(root/'download_sources.json').write_text(json.dumps(sources,indent=2)+'\n')
