import urllib.request,json,datetime,concurrent.futures
from pathlib import Path
out=Path(__file__).parent
end=int(datetime.datetime(2026,10,7,tzinfo=datetime.timezone.utc).timestamp()*1000)
def fetch(job):
 symbol,interval=job;start=0;rows=[];urls=[]
 while True:
  url=f'https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&startTime={start}&endTime={end-1}&limit=1000'
  batch=json.loads(urllib.request.urlopen(url,timeout=30).read());urls.append(url)
  if not batch:break
  rows.extend(r for r in batch if r[6]<end)
  nextstart=batch[-1][0]+1
  assert nextstart>start
  start=nextstart
  if len(batch)<1000:break
 payload={'symbol':symbol,'interval':interval,'urls':urls,'rows':rows,'end_exclusive_utc':'2026-10-07'}
 (out/(symbol+'-'+interval+'.json')).write_text(json.dumps(payload))
 return dict(symbol=symbol,interval=interval,count=len(rows),first=rows[0][0],last=rows[-1][0])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 result=list(pool.map(fetch,[(s,i) for s in ['ADAUSDT','DOGEUSDT','AVAXUSDT'] for i in ['1d','1w']]))
(out/'download_audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
