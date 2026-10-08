import concurrent.futures,json,urllib.parse
from pathlib import Path
scope={'__file__':str(Path(__file__).with_name('download.py'))}
source=Path(__file__).with_name('download.py').read_text();exec(source[:source.index('with concurrent.futures.ThreadPoolExecutor')],scope)
root=Path(__file__).resolve().parent;(root/'raw/marks').mkdir(exist_ok=True)
def download(asset):
 old=json.loads((root/'raw/futures'/(asset+'.json')).read_text());rows=old['mark_hourly']['rows'];cursor=rows[-1][0]+3600000 if rows else scope['fundstart'];end=scope['end'];urls=[]
 while cursor<end:
  u='https://fapi.binance.com/fapi/v1/markPriceKlines?'+urllib.parse.urlencode(dict(symbol=asset+'USDT',interval='1h',limit=1500,startTime=cursor,endTime=end));part=scope['request'](u);assert isinstance(part,list);urls.append(u)
  if not part:break
  rows+=part;cursor=part[-1][0]+3600000
  if len(part)<1500:break
 assert rows[-1][0]==end+1-3600000
 (root/'raw/marks'/(asset+'.json')).write_text(json.dumps(dict(rows=rows,urls=old['mark_hourly']['urls']+urls)));print(asset,'mark hours',len(rows),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(download,['BTC','ETH','SOL']))
