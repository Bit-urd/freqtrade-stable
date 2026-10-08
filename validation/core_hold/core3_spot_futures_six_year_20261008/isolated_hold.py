"""Hourly isolated-margin holding sensitivity; today's cached tiers, no top-ups or re-entry."""
import bisect,csv,datetime,json
from pathlib import Path
root=Path(__file__).resolve().parent;assets=['BTC','ETH','SOL'];tiers=json.loads(Path('/root/freqtrade-stable/freqtrade/exchange/binance_leverage_tiers.json').read_text());info=json.loads(Path('/root/freqtrade-stable/validation/core_hold/requested_27_futures_half_year_20261008/exchange_info.json').read_text());insurance={a:float(next(s for s in info['symbols'] if s['symbol']==a+'USDT')['liquidationFee']) for a in assets}
raw={a:json.loads((root/'raw/futures'/(a+'.json')).read_text()) for a in assets};marks={a:{r[0]:r for r in json.loads((root/'raw/marks'/(a+'.json')).read_text())['rows']} for a in assets};result=[]
def utc(ms):return datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc)
def tier(asset,notional):
 for t in tiers[asset+'/USDT:USDT']:
  if notional<=t['maxNotional']:return float(t['maintenanceMarginRate']),float(t['info'].get('cum',0))
 t=tiers[asset+'/USDT:USDT'][-1];return float(t['maintenanceMarginRate']),float(t['info'].get('cum',0))
for start in ['2020-10-08','2021-02-11']:
 label='Futures_full' if start=='2020-10-08' else 'Futures_common';startms=int(datetime.datetime.fromisoformat(start).replace(tzinfo=datetime.timezone.utc).timestamp()*1000);endms=int(datetime.datetime(2026,10,8,tzinfo=datetime.timezone.utc).timestamp()*1000);opened={};fund_events=[];dailyprice={}
 for a in assets:
  eligible=[r for r in raw[a]['daily']['rows'][61:] if startms<=r[0]<endms];opened[a]=eligible[0];dailyprice[a]={r[0]:float(r[4]) for r in raw[a]['daily']['rows']}
  for f in raw[a]['funding']['rows']:
   if startms<=int(f['fundingTime'])<endms:fund_events.append((int(f['fundingTime']),a,float(f['fundingRate'])*float(f['markPrice'])))
 fund_events.sort();index=0;free=10000.;pos={};entered=set();events=[];curve=[];fundpnl=0.;entryfees=0.;clearfees=0.
 def settle(event):
  global free,fundpnl
  time,a,cost=event
  if a not in pos:return
  cost*=pos[a]['qty'];fundpnl-=cost
  if cost<0:free-=cost
  else:paid=min(free,cost);free-=paid;pos[a]['margin']-=cost-paid
 for hour in range(startms,endms,3600000):
  while index<len(fund_events) and fund_events[index][0]<=hour:settle(fund_events[index]);index+=1
  for a in assets:
   if a not in entered and opened[a][0]==hour:
    budget=min(10000/3,free);price=float(opened[a][1]);qty=budget/1.0005/price;pos[a]=dict(qty=qty,entry=price,margin=qty*price);free-=budget;entryfees+=budget*.0005/1.0005;entered.add(a)
  while index<len(fund_events) and fund_events[index][0]<hour+3600000:settle(fund_events[index]);index+=1
  for a in list(pos):
   p=pos[a];bar=marks[a][hour];low=float(bar[3]);mmr,maint=tier(a,p['qty']*low);eq=p['margin']+p['qty']*(low-p['entry'])
   if eq<=p['qty']*low*mmr-maint:
    trigger=(p['qty']*p['entry']-p['margin']-maint)/(p['qty']*(1-mmr));px=min(float(bar[1]),trigger);remaining=max(0.,p['margin']+p['qty']*(px-p['entry']));fee=min(remaining,p['qty']*px*insurance[a]);free+=remaining-fee;clearfees+=fee;events.append(dict(asset=a,hour_utc=utc(hour).isoformat(),approx_liquidation_price=px,remaining_equity_before_clearance_fee=remaining,clearance_fee=fee));del pos[a]
  if (hour+3600000)%86400000==0:
   day=hour//86400000*86400000;equity=free+sum(p['margin']+p['qty']*(dailyprice[a][day]-p['entry']) for a,p in pos.items());curve.append(dict(date=str(utc(day).date()),equity=equity,free_margin=free,funding_pnl=fundpnl))
 peak=10000.;dd=0.
 for row in curve:peak=max(peak,row['equity']);dd=max(dd,1-row['equity']/peak)
 outcome=dict(case=label,start=start,end='2026-10-07',return_pct=(curve[-1]['equity']/10000-1)*100,drawdown_pct=dd*100,liquidations=events,ending_positions=list(pos),funding_pnl=fundpnl,entry_fees=entryfees,clearance_fees=clearfees,assumptions='current cached maintenance tiers and clearance fee, hourly mark bars, fees debit free wallet then isolated margin, no external topup/no reentry; liquidation hour approximate')
 with (root/(label+'_hold_isolated.csv')).open('w') as f:w=csv.DictWriter(f,fieldnames=list(curve[0]));w.writeheader();w.writerows(curve)
 result.append(outcome);print(json.dumps(outcome),flush=True)
(root/'isolated_hold_results.json').write_text(json.dumps(result,indent=2)+'\n')
