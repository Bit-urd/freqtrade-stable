import json,hashlib,os,sys
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent;(root/'data').mkdir(exist_ok=True);(root/'data/futures').mkdir(exist_ok=True);audit=[];mature=[]
for mode in ['spot','futures']:
 for asset in ['BTC','ETH','SOL']:
  raw=json.loads((root/'raw'/mode/(asset+'.json')).read_text());d=pd.DataFrame(raw['daily']['rows']).rename(columns={0:'date',1:'open',2:'high',3:'low',4:'close',5:'volume'})[['date','open','high','low','close','volume']];d.date=pd.to_datetime(d.date,unit='ms',utc=True)
  for c in ['open','high','low','close','volume']:d[c]=d[c].astype(float)
  assert pd.DatetimeIndex(d.date).equals(pd.date_range(d.date.iloc[0],d.date.iloc[-1],freq='D'));assert d.date.iloc[-1]==pd.Timestamp('2026-10-07',tz='UTC');assert (d.close>0).all();mature.append(str(d.date.iloc[150].date()))
  path=root/'data'/((asset+'_USDT-1d.feather') if mode=='spot' else 'futures/'+asset+'_USDT_USDT-1d-futures.feather');d.to_feather(path)
  audit.append(dict(mode=mode,asset=asset,file=str(path.relative_to(root)),rows=len(d),first=str(d.date.iloc[0].date()),ma150_start=str(d.date.iloc[150].date()),warm_start=str(d.date.iloc[61].date()),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
  if mode=='futures':
   f=pd.DataFrame(raw['funding']['rows']);dates=pd.to_datetime(f.fundingTime,unit='ms',utc=True)
   for kind,values in [('funding_rate',f.fundingRate.astype(float)),('mark',f.markPrice.astype(float))]:
    pd.DataFrame(dict(date=dates,open=values,high=values,low=values,close=values,volume=0.)).to_feather(root/'data/futures'/(asset+'_USDT_USDT-1h-'+kind+'.feather'))
(root/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n');common=max(mature);cases=[]
for label,mode,start,zero in [('Spot_full','spot','2020-10-08',False),('Futures_full','futures','2020-10-08',False),('Spot_common','spot',common,False),('Futures_common','futures',common,False),('Futures_zero_funding_full','futures','2020-10-08',True)]:cases.append(dict(label=label,mode=mode,start=start,end='2026-10-07',fee=.001 if mode=='spot' else .0005,zero_funding=zero))
(root/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
base=json.loads(Path('/freqtrade/user_data/config_cycle_risk_futures_27.json').read_text());base.update(bot_name='core3_six_year_research',max_open_trades=3,datadir=str(root/'data'),cycle_risk_funding_data_dir=str(root/'raw/futures'),strategy_path='/freqtrade/user_data/strategies');base['exchange']['pair_whitelist']=['BTC/USDT','ETH/USDT','SOL/USDT'];base['trading_mode']='spot';base.pop('margin_mode',None);base['strategy']='BtcCoinGuardCycleRiskStrategy';(root/'config_spot.json').write_text(json.dumps(base,indent=2)+'\n');base.update(trading_mode='futures',margin_mode='isolated',strategy='BtcCoinGuardCycleRiskFuturesStrategy');base['exchange']['pair_whitelist']=[p+':USDT' for p in base['exchange']['pair_whitelist']];(root/'config_futures.json').write_text(json.dumps(base,indent=2)+'\n')
print('Common mature start',common,flush=True);os._exit(0)
