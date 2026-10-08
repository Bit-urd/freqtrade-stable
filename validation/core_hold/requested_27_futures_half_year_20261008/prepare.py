import json,hashlib,shutil,sys,os
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent;prior=root.parent/'without_zec_pump_20261008'
assets=['0G','1000BONK','AAVE','ADA','AERO','APT','ARB','BOME','BTC','DOT','ETH','FIL','GRAM','JUP','LDO','LINK','MON','OP','POL','PUMP','SKY','SOL','STRK','SUI','UNI','WCT','XRP']
(root/'data').mkdir(exist_ok=True);(root/'strategies').mkdir(exist_ok=True);audit=[]
for asset in assets:
 raw=json.loads((root/'raw'/(asset+'.json')).read_text());df=pd.DataFrame(raw['daily']['rows']).rename(columns={0:'date',1:'open',2:'high',3:'low',4:'close',5:'volume'})[['date','open','high','low','close','volume']];df.date=pd.to_datetime(df.date,unit='ms',utc=True)
 for c in ['open','high','low','close','volume']:df[c]=df[c].astype(float)
 assert not df.date.duplicated().any();assert pd.DatetimeIndex(df.date).equals(pd.date_range(df.date.iloc[0],df.date.iloc[-1],freq='D'));assert df.date.iloc[-1]==pd.Timestamp('2026-10-07',tz='UTC');assert (df.close>0).all()
 filename=asset+'_USDT_USDT-1d-futures.feather';df.to_feather(root/'data'/filename)
 f=pd.DataFrame(raw['funding']['rows']);f['date']=pd.to_datetime(f.fundingTime,unit='ms',utc=True);f['rate']=f.fundingRate.astype(float);f['mark']=f.markPrice.astype(float);assert (f.mark>0).all();assert not f.date.duplicated().any()
 for kind,value,col in [('funding_rate',f.rate,'1h'),('mark',f.mark,'1h')]:
  frame=pd.DataFrame({'date':f.date,'open':value,'high':value,'low':value,'close':value,'volume':0.});frame.to_feather(root/'data'/(asset+'_USDT_USDT-'+col+'-'+kind+'.feather'))
 item=dict(asset=asset,pair=asset+'/USDT:USDT',file=filename,first=str(df.date.iloc[0].date()),last='2026-10-07',rows=len(df),funding_rows=len(f),warm_start=str(df.date.iloc[61].date()) if len(df)>61 else None,ma150_start=str(df.date.iloc[150].date()) if len(df)>150 else None,sha256=hashlib.sha256((root/'data'/filename).read_bytes()).hexdigest());audit.append(item)
(root/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
config=json.loads((prior/'config.json').read_text());config.update(bot_name='requested27_futures_research',trading_mode='futures',margin_mode='isolated',datadir=str(root/'data'),fee=.0005,max_open_trades=27);config['exchange']['pair_whitelist']=['BTC/USDT:USDT'];(root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
# Research-only adapter: retain validated trading signals and correct futures collateral valuation.
s=(prior/'strategies/cycle_risk_strategy.py').read_text().replace('BTC_PAIR = "BTC/USDT"','BTC_PAIR = "BTC/USDT:USDT"').replace('candle_type=CandleType.SPOT','candle_type=CandleType.FUTURES')
start=s.index('    def _update_equity_risk(');end=s.index('    def custom_stake_amount(',start)
s=s[:start]+'''    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag, side, **kwargs):
        return 1.0

    def _update_equity_risk(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        from futures_accounting import live_equity
        equity = live_equity(self, current_time)
        if self._risk_peak is None:
            self._risk_peak = float(self.wallets.get_starting_balance())
        self._risk_peak = max(self._risk_peak, equity)
        dd = max(0.0, 1 - equity / self._risk_peak) if self._risk_peak > 0 else 0.0
        self._risk_fraction = self.next_fraction(self._risk_fraction, dd)
        self._risk_candle = candle
        self.risk_trace.append({'execution_date':str(candle), 'prior_closed_equity':equity,
                                'peak':self._risk_peak, 'drawdown':dd,
                                'risk_fraction':self._risk_fraction})

'''+s[end:]
(root/'strategies/cycle_risk_strategy.py').write_text(s);shutil.copy2(prior/'strategies/btc_exit_confirmation_strategy.py',root/'strategies/btc_exit_confirmation_strategy.py')
active=[a for a in assets if a!='GRAM'];windows=[]
def window(label,coins,slots=None):
 windows.append(dict(label=label,universe=label,pairs=[a+'/USDT:USDT' for a in coins],valuation_pairs=[a+'/USDT:USDT' for a in coins],slots=slots or len(coins),scope='half_year_futures',phase='',start='2026-04-08',end='2026-10-07',timerange='20260408-20261007'))
window('Requested27',assets);window('Mature26',active)
for asset in assets:window(asset,[asset])
(root/'windows.json').write_text(json.dumps(windows,indent=2)+'\n');(root/'source_manifest.json').write_text(json.dumps({'strategies/'+p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'strategies').glob('*.py')},indent=2)+'\n')
plan=dict(status='ready',assets=assets,mode='isolated_futures',leverage=1,initial_wallet=10000,fee_per_side=.0005,start='2026-04-08',end='2026-10-07',total_windows=len(windows),native_tests_expected=len(windows)*2,equity_curves_expected=len(windows)*3,production_sha256=hashlib.sha256(Path('/freqtrade/user_data/strategies/cycle_risk_strategy.py').read_bytes()).hexdigest(),funding='actual settlement rates and mark prices; no entry-time settlement charged; exit-time settlement charged',GRAM='Only98 daily bars by end; MA150 unavailable, strategy expected to stay cash; warmup-matched hold begins after61 bars')
(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2),flush=True);os._exit(0)
