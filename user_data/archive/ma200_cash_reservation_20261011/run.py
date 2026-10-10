import copy,csv,gzip,json,logging,sys,gc,hashlib,os
from pathlib import Path
import pandas as pd
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import StrategyResolver
import ledger as a
ROOT=Path(__file__).resolve().parent
NAMES=['Ma200CashSupplementStrategy']
WINDOWS=json.loads((ROOT/'windows.json').read_text())
if len(sys.argv)>1:WINDOWS={sys.argv[1]:WINDOWS[sys.argv[1]]}
if len(sys.argv)>2:NAMES=[sys.argv[2]]
logging.basicConfig(level=logging.ERROR)
cli=Arguments(['backtesting','-c',str(ROOT/'config.json'),'--userdir',str(ROOT/'runtime'),'--datadir',str(ROOT/'data'),'--strategy-path',str(ROOT/'strategies'),'--timerange',next(iter(WINDOWS.values())),'--strategy-list',*NAMES,'--cache','none']).get_parsed_arg()
config=setup_optimize_configuration(cli,RunMode.BACKTEST)
a.PAIRS=config['exchange']['pair_whitelist'];a.HISTORY={p:pd.read_feather(ROOT/'data'/(p.replace('/','_')+'-1d.feather')).set_index('date').sort_index() for p in a.PAIRS}
audit={}
for p,h in a.HISTORY.items():
 assert not h.index.duplicated().any()
 audit[p]={'first':str(h.index[0]),'last':str(h.index[-1]),'rows':len(h),'missing_days':len(pd.date_range(h.index[0],h.index[-1],freq='D').difference(h.index))}
 assert audit[p]['missing_days']==0,(p,audit[p])
 weekly=h.resample('W-MON',label='left',closed='left').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index()
 pass
(ROOT/'data_audit.json').write_text(json.dumps(audit,indent=2))
(ROOT/'source_hashes.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (ROOT/'strategies').glob('*.py')},indent=2))
bt=Backtesting(config,progress_callback=lambda task:None);gc.freeze();rows=[]
def metrics(curve,trades):
 m=a.stats(curve);years=len(curve)/365.25;m['cagr_pct']=((curve.equity.iloc[-1]/a.CAPITAL)**(1/years)-1)*100;m['calmar']=m['cagr_pct']/m['wallet_drawdown_pct'] if m['wallet_drawdown_pct'] else None
 m['exposure_pct']=(1-curve.cash/curve.equity).mean()*100;m['trades']=len(trades);streak=maximum=0
 for t in sorted(trades,key=lambda t:t['close_timestamp']):
  streak=streak+1 if t['profit_abs']<0 else 0;maximum=max(maximum,streak)
 m['max_loss_streak']=maximum;return m
class CallbackErrorCheck(logging.Handler):
 def __init__(self):super().__init__(logging.ERROR);self.errors=[]
 def emit(self,record):self.errors.append(record.getMessage())
callback_check=CallbackErrorCheck();logging.getLogger('freqtrade.strategy.strategy_wrapper').addHandler(callback_check)
for label,tr in WINDOWS.items():
 folder=ROOT/'results'/label;folder.mkdir(parents=True,exist_ok=True)
 expected=TimeRange.parse_timerange(tr);dates=pd.date_range(pd.Timestamp(expected.startts,unit='s',tz='UTC'),pd.Timestamp(expected.stopts,unit='s',tz='UTC')-pd.Timedelta(days=1),freq='D')
 for name in (['CycleRiskRelativeBorrowDisabled'] if label=='disabled_parity' else NAMES):
  if label=='baseline_cache_check' and name!='CycleRiskOriginalCached':continue
  bt.all_bt_content={};c=copy.deepcopy(config);c['timerange']=tr;c['strategy']=name;c.pop('strategy_list',None);strategy=StrategyResolver.load_strategy(c)
  source=Path(strategy.populate_indicators.__code__.co_filename);assert source.parent==ROOT/'strategies',source
  bt.config['timerange']=tr;bt.timerange=TimeRange.parse_timerange(tr);bt.available_pairs=[];bt.required_startup=strategy.startup_candle_count;bt.config['startup_candle_count']=bt.required_startup
  data,timerange=bt.load_bt_data();data={p:d[d.date<=dates[-1]].copy() for p,d in data.items()};bt.init_backtest();callback_check.errors.clear();minimum,maximum=bt.backtest_one_strategy(strategy,data,timerange)
  assert not callback_check.errors,(label,name,callback_check.errors[:3])
  assert minimum==dates[0] and maximum==dates[-1],(label,name,minimum,maximum)
  content=bt.all_bt_content[name];trades=content['results'].to_dict(orient='records');curve,terminal,_=a.ledger(trades,dates)
  assert abs(terminal-content['final_balance'])<.05,(label,name,terminal,content['final_balance'])
  (folder/(name+'_funding.json')).write_text(json.dumps(getattr(strategy,'funding_trace',[]),default=str));trace=getattr(strategy,'risk_trace',[]);errors=[abs(t['prior_closed_equity']-curve.loc[pd.Timestamp(t['execution_date'])-pd.Timedelta(days=1),'equity']) for t in trace if pd.Timestamp(t['execution_date'])-pd.Timedelta(days=1) in curve.index]
  assert max(errors,default=0)<.05
  row=dict(window=label,strategy=name,start=str(dates[0].date()),end=str(dates[-1].date()),**metrics(curve,trades),ledger_error=terminal-content['final_balance'],startup=bt.required_startup);rows.append(row)
  curve.to_csv(folder/(name+'_equity.csv'))
  with gzip.open(folder/(name+'_trades.json.gz'),'wt') as f:json.dump(trades,f,default=str)
  print(label,name,f"return={row['return_pct']:.2f}% DD={row['wallet_drawdown_pct']:.2f}% Calmar={row['calmar']:.2f}",flush=True)
 with (folder/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print('Completed',label,flush=True)
sys.stdout.flush();os._exit(0)
