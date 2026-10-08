import csv,hashlib,json,os,sys
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent;previous=root.parent/'p1_p8_twelve_assets_20261008'
assets=['BTC','ETH','BNB','LINK','XRP','UNI','ZEC','DOGE','SOL','ARB','PUMP','HYPE'];end='2026-10-06';history={};audit=[]
(root/'data').mkdir(exist_ok=True);(root/'strategies').mkdir(exist_ok=True)
for asset in assets:
 rows=json.loads((root/'raw/spot'/(asset+'.json')).read_text());df=pd.DataFrame(rows).rename(columns={0:'date',1:'open',2:'high',3:'low',4:'close',5:'volume'})[['date','open','high','low','close','volume']]
 df.date=pd.to_datetime(df.date,unit='ms',utc=True)
 for col in ['open','high','low','close','volume']:df[col]=df[col].astype(float)
 df=df.sort_values('date').drop_duplicates('date').reset_index(drop=True)
 assert df.date.iloc[-1]==pd.Timestamp(end,tz='UTC') and (df.close>0).all()
 assert (df.high>=df[['open','close','low']].max(axis=1)).all() and (df.low<=df[['open','close','high']].min(axis=1)).all() and (df.volume>=0).all()
 assert pd.DatetimeIndex(df.date).equals(pd.date_range(df.date.iloc[0],df.date.iloc[-1],freq='D'))
 history[asset]=df;file=root/'data'/(asset+'_USDT-1d.feather');df.to_feather(file)
 audit.append(dict(asset=asset,file=file.name,rows=len(df),first=str(df.date.iloc[0].date()),last=end,warm_start=str(df.date.iloc[61].date()) if len(df)>61 else None,ma150_start=str(df.date.iloc[150].date()) if len(df)>150 else None,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
for name in ['cycle_risk_strategy.py','btc_exit_confirmation_strategy.py']:(root/'strategies'/name).write_bytes((previous/'strategies'/name).read_bytes())
config=json.loads((previous/'config.json').read_text());config.update(bot_name='requested_twelve_pool_research',datadir=str(root/'data'));config['max_open_trades']=12;config['exchange']['pair_whitelist']=['BTC/USDT'];(root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
periods=json.loads((previous/'periods.json').read_text());(root/'periods.json').write_text(json.dumps(periods,indent=2,ensure_ascii=False)+'\n')
windows=[];coverage=[]
def window(label,pairs,start,finish,scope,slots=None,phase=''):
 slots=slots or len(pairs)
 w=dict(label=label,universe=label.split('_')[0],pairs=[a+'/USDT' for a in pairs],start=start,end=finish,timerange=start.replace('-','')+'-'+finish.replace('-',''),scope=scope,slots=slots,phase=phase,valuation_pairs=[a+'/USDT' for a in (assets if slots==12 else pairs)])
 windows.append(w)
for p in periods:
 eligible=[]
 for asset in assets:
  h=history[asset];start=pd.Timestamp(p['start'],tz='UTC');finish=pd.Timestamp(p['end'],tz='UTC');r=dict(phase=p['id'],asset=asset,requested_start=p['start'],requested_end=p['end'],data_first=str(h.date.iloc[0].date()),status='unavailable',reason='',effective_start='',effective_end='',prior_candles=0,ma150_ready_at_start=False)
  if h.date.iloc[0]>finish:r['reason']='该阶段尚无 Binance 现货历史'
  elif len(h)<=61 or h.date.iloc[61]>finish:r['reason']='阶段内不足60根完成日线'
  else:
   effective=max(start,h.date.iloc[61]);r.update(status='full' if effective==start else 'partial',effective_start=str(effective.date()),effective_end=p['end'],prior_candles=int((h.date<effective).sum()),ma150_ready_at_start=bool((h.date<effective).sum()>=150));r['reason']='完整' if effective==start else '上市/暖机后部分区间'
   if not r['ma150_ready_at_start']:r['reason']+='；MA150尚未形成'
   window(asset+'_'+p['id'],[asset],r['effective_start'],p['end'],'single',phase=p['id']);eligible.append(asset)
  coverage.append(r)
 window('EligiblePool_'+p['id'],eligible,p['start'],p['end'],'phase_pool',phase=p['id'])
 window('RequestedSlots12_'+p['id'],eligible,p['start'],p['end'],'phase_pool_reserved',slots=12,phase=p['id'])
legacy=assets[:9];main=assets[:10];pump=assets[:11]
def mature_start(group):return str(max(history[a].date.iloc[150] for a in group).date())
for tag,group in [('Legacy9',legacy),('Main10',main)]:
 first=mature_start(group)
 for suffix,start,finish in [('full_cycle',first,end),('continuous_2023','2023-01-01',end),('year_2025','2025-01-01','2025-12-31'),('year_2026','2026-01-01',end),('recent','2025-09-01',end)]:
  start=max(start,first)
  if suffix!='full_cycle' and start==first:continue
  window(tag+'_'+suffix,group,start,finish,'continuous_pool')
first=mature_start(pump)
window('Mature11_full_cycle',pump,first,end,'continuous_pool')
window('Requested12_mature11_cash',pump,first,end,'continuous_pool_reserved',slots=12)
window('Main10_mature11_control',main,first,end,'continuous_pool_control')
window('PUMP_after_ma150',['PUMP'],first,end,'new_asset')
window('PUMP_after_warmup',['PUMP'],str(history['PUMP'].date.iloc[61].date()),end,'new_asset_immature')
window('Main10_year_2024',main,'2024-01-01','2024-12-31','continuous_pool')
with (root/'coverage.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
(root/'windows.json').write_text(json.dumps(windows,indent=2)+'\n');(root/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
manifest={'strategies/'+p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'strategies').glob('*.py')};(root/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
plan=dict(status='ready',assets=assets,mode='spot',requested_phase_cells=96,eligible_single_phase_cases=sum(c['status']!='unavailable' for c in coverage),unavailable_phase_cells=sum(c['status']=='unavailable' for c in coverage),partial_single_phase_cases=sum(c['status']=='partial' for c in coverage),total_windows=len(windows),native_tests_expected=len(windows)*2,equity_curves_expected=len(windows)*3,production_sha256=manifest['strategies/cycle_risk_strategy.py'],fee_per_side=.001,initial_wallet=1000,criteria='Comprehensive final continuous portfolio results, exceptional trend participation, and worst losses; no fixed DD cutoff or stage-win-rate rejection',hype_status='Only13 daily spot candles; not eligible for strategy warmup; 12-slot runs retain its budget as cash')
(root/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True);sys.stdout.flush();os._exit(0)
