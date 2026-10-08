import concurrent.futures,datetime,json,time,urllib.parse,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent;start=int(datetime.datetime(2019,1,1,tzinfo=datetime.timezone.utc).timestamp()*1000);fundstart=int(datetime.datetime(2020,10,8,tzinfo=datetime.timezone.utc).timestamp()*1000);end=int(datetime.datetime(2026,10,8,tzinfo=datetime.timezone.utc).timestamp()*1000)-1
(root/'raw/spot').mkdir(parents=True,exist_ok=True);(root/'raw/futures').mkdir(parents=True,exist_ok=True)
def request(url):
 for attempt in range(5):
  try:return json.load(urllib.request.urlopen(url,timeout=30))
  except Exception:
   if attempt==4:raise
   time.sleep(2**attempt)
def fetch(asset):
 for mode in ['spot','futures']:
  base='https://api.binance.com/api/v3/' if mode=='spot' else 'https://fapi.binance.com/fapi/v1/';cursor=start;rows=[];urls=[]
  while cursor<end:
   u=base+'klines?'+urllib.parse.urlencode(dict(symbol=asset+'USDT',interval='1d',limit=1000,startTime=cursor,endTime=end));part=request(u);assert isinstance(part,list);urls.append(u)
   if not part:break
   rows+=part;cursor=part[-1][0]+86400000
   if len(part)<1000:break
  result=dict(daily=dict(rows=rows,urls=urls))
  if mode=='futures':
   rates=[];cursor=fundstart;fundurls=[]
   while cursor<end:
    u=base+'fundingRate?'+urllib.parse.urlencode(dict(symbol=asset+'USDT',limit=1000,startTime=cursor,endTime=end));part=request(u);assert isinstance(part,list);fundurls.append(u)
    if not part:break
    rates+=part;cursor=int(part[-1]['fundingTime'])+1
    if len(part)<1000:break
   missing=[r for r in rates if not r.get('markPrice') or float(r['markPrice'])<=0];marks=[];markurls=[]
   if missing:
    cursor=min(int(r['fundingTime'])//3600000*3600000 for r in missing);last=max(int(r['fundingTime'])//3600000*3600000 for r in missing)+3599999
    while cursor<=last:
     u=base+'markPriceKlines?'+urllib.parse.urlencode(dict(symbol=asset+'USDT',interval='1h',limit=1500,startTime=cursor,endTime=last));part=request(u);assert isinstance(part,list);markurls.append(u)
     if not part:break
     marks+=part;cursor=part[-1][0]+3600000
     if len(part)<1500:break
    indexed={r[0]:r[1] for r in marks}
    for r in missing:
     hour=int(r['fundingTime'])//3600000*3600000;assert hour in indexed,(asset,hour);r['markPrice']=indexed[hour];r['markPriceSource']='hour_open_proxy_for_missing_settlement_mark'
   result.update(funding=dict(rows=rates,urls=fundurls,proxy_mark_count=len(missing)),mark_hourly=dict(rows=marks,urls=markurls))
  (root/'raw'/mode/(asset+'.json')).write_text(json.dumps(result));print(mode,asset,len(rows),len(result.get('funding',{}).get('rows',[])),'mark_proxies',result.get('funding',{}).get('proxy_mark_count',0),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,['BTC','ETH','SOL']))
print('Downloaded six-year comparison history',flush=True)
