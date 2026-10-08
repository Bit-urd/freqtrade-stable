"""Freeze exchange daily candles for the requested assets, before choosing execution mode."""
import concurrent.futures,datetime,json,time,urllib.parse,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent
assets=['BTC','ETH','BNB','LINK','XRP','UNI','ZEC','DOGE','SOL','ARB','PUMP','HYPE']
end=int(datetime.datetime(2026,10,7,tzinfo=datetime.timezone.utc).timestamp()*1000)-1
manifest=[]
def fetch(item):
 coin,mode=item;base='https://api.binance.com' if mode=='spot' else 'https://fapi.binance.com';path='/api/v3/klines' if mode=='spot' else '/fapi/v1/klines';start=0;rows=[];urls=[]
 while start<end:
  url=base+path+'?'+urllib.parse.urlencode(dict(symbol=coin+'USDT',interval='1d',limit=1000,startTime=start,endTime=end))
  for attempt in range(4):
   try:
    with urllib.request.urlopen(url,timeout=30) as response:part=json.load(response)
    if not isinstance(part,list):raise ValueError(part)
    break
   except Exception:
    if attempt==3:raise
    time.sleep(2**attempt)
  urls.append(url)
  if not part:break
  rows.extend(part);start=part[-1][0]+86400000
  if len(part)<1000:break
 return coin,mode,rows,urls
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for coin,mode,rows,urls in pool.map(fetch,[(c,m) for m in ['spot','futures'] for c in assets]):
  folder=root/'raw'/mode;folder.mkdir(parents=True,exist_ok=True);(folder/(coin+'.json')).write_text(json.dumps(rows))
  manifest.append(dict(asset=coin,mode=mode,rows=len(rows),first=datetime.datetime.fromtimestamp(rows[0][0]/1000,datetime.timezone.utc).isoformat() if rows else None,last=datetime.datetime.fromtimestamp(rows[-1][0]/1000,datetime.timezone.utc).isoformat() if rows else None,urls=urls))
  print(mode,coin,len(rows),manifest[-1]['first'],flush=True)
(root/'download_sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Daily snapshots completed',flush=True)
