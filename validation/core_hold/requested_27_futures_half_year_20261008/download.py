import concurrent.futures,datetime,json,time,urllib.parse,urllib.request,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
assets=['0G','1000BONK','AAVE','ADA','AERO','APT','ARB','BOME','BTC','DOT','ETH','FIL','GRAM','JUP','LDO','LINK','MON','OP','POL','PUMP','SKY','SOL','STRK','SUI','UNI','WCT','XRP']
shutil.copy2('/tmp/requested27_futures_exchange_info.json',root/'exchange_info.json')
start=int(datetime.datetime(2025,1,1,tzinfo=datetime.timezone.utc).timestamp()*1000);fundstart=int(datetime.datetime(2026,4,8,tzinfo=datetime.timezone.utc).timestamp()*1000);end=int(datetime.datetime(2026,10,8,tzinfo=datetime.timezone.utc).timestamp()*1000)-1
(root/'raw').mkdir(exist_ok=True)
def fetch(asset):
 result={}
 for kind,path,initial in [('daily','klines',start),('funding','fundingRate',fundstart)]:
  rows=[];urls=[];cursor=initial
  while cursor<end:
   params=dict(symbol=asset+'USDT',limit=1000,startTime=cursor,endTime=end)
   if kind=='daily':params['interval']='1d'
   url='https://fapi.binance.com/fapi/v1/'+path+'?'+urllib.parse.urlencode(params)
   for attempt in range(5):
    try:
     data=json.load(urllib.request.urlopen(url,timeout=30));assert isinstance(data,list);break
    except Exception:
     if attempt==4:raise
     time.sleep(2**attempt)
   urls.append(url)
   if not data:break
   rows+=data;cursor=(data[-1][0]+86400000) if kind=='daily' else int(data[-1]['fundingTime'])+1
   if len(data)<1000:break
  result[kind]=dict(rows=rows,urls=urls)
 (root/'raw'/(asset+'.json')).write_text(json.dumps(result));print(asset,len(result['daily']['rows']),len(result['funding']['rows']),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,assets))
print('Download complete',flush=True)
