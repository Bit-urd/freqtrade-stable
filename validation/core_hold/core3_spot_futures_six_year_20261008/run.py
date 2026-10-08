import argparse,copy,csv,gc,gzip,json,logging,os,sys,time
from pathlib import Path
from types import MethodType
import pandas as pd
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import StrategyResolver
import accounting as a
root=Path(__file__).resolve().parent;parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['spot','futures'],required=True);mode=parser.parse_args().mode
cases=[c for c in json.loads((root/'cases.json').read_text()) if c['mode']==mode];name='BtcCoinGuardCycleRiskStrategy' if mode=='spot' else 'BtcCoinGuardCycleRiskFuturesStrategy'
cli=Arguments(['backtesting','-c',str(root/('config_'+mode+'.json')),'--strategy',name,'--strategy-path','/freqtrade/user_data/strategies','--datadir',str(root/'data'),'--timerange','20201008-20261007','--fee',str(cases[0]['fee']),'--cache','none']).get_parsed_arg();logging.disable(logging.WARNING);config=setup_optimize_configuration(cli,RunMode.BACKTEST);bt=Backtesting(config,progress_callback=lambda task:None);gc.freeze();pairs=config['exchange']['pair_whitelist'];fund_snapshot={p:v.copy() for p,v in a.FUND.items()};rows=list(csv.DictReader((root/'summary.csv').open())) if (root/'summary.csv').exists() else []
for case in cases:
 label=case['label'];folder=root/'results'/label;folder.mkdir(parents=True,exist_ok=True)
 if (folder/'completed.json').exists():print('Cached',label,flush=True);continue
 rows=[r for r in rows if r['case']!=label];dates=pd.date_range(case['start'],case['end'],tz='UTC');bt.config['timerange']=case['start'].replace('-','')+'-'+case['end'].replace('-','');bt.timerange=TimeRange.parse_timerange(bt.config['timerange']);bt.config['fee']=case['fee'];bt.fee=case['fee'];bt.all_bt_content={};a.FEE=case['fee'];a.PAIRS=pairs;a.HISTORY={}
 for pair in pairs:
  filename=pair.replace('/','_').replace(':','_')+'-1d'+('-futures' if mode=='futures' else '')+'.feather';path=root/'data'/('futures' if mode=='futures' else '')/filename;a.HISTORY[pair]=pd.read_feather(path).set_index('date')
 if mode=='spot':a.FUND={p:pd.Series([],index=pd.DatetimeIndex([],tz='UTC'),dtype=float) for p in pairs}
 else:a.FUND={p:fund_snapshot[p]*(0 if case['zero_funding'] else 1) for p in pairs}
 data,timerange=bt.load_bt_data()
 if mode=='futures':
  for pair in pairs:
   records=json.loads((root/'raw/futures'/(pair.split('/')[0]+'.json')).read_text())['funding']['rows'];bt.futures_data[pair]=pd.DataFrame(dict(date=pd.to_datetime([r['fundingTime'] for r in records],unit='ms',utc=True),open_fund=[0. if case['zero_funding'] else float(r['fundingRate']) for r in records],open_mark=[float(r['markPrice']) for r in records]))
  def funding(self,trade,current_time,force=False):
   frame=self.futures_data[trade.pair];part=frame.loc[(frame.date>pd.Timestamp(trade.date_last_filled_utc))&(frame.date<=pd.Timestamp(current_time))];trade.set_funding_fees(float(-(part.open_fund*part.open_mark).sum()*trade.amount))
  bt._run_funding_fees=MethodType(funding,bt)
 strategy=StrategyResolver.load_strategy(copy.deepcopy(bt.config))
 if case['zero_funding']:strategy._futures_funding_total=MethodType(lambda self,pair,when:0.,strategy)
 bt.init_backtest();assert abs(bt.wallets.get_starting_balance()-10000)<1e-6;minimum,maximum=bt.backtest_one_strategy(strategy,data,timerange);assert dates.equals(pd.date_range(minimum,maximum)),(label,minimum,maximum);content=bt.all_bt_content[name];trades=content['results'].to_dict(orient='records');curve,terminal,_=a.ledger(trades,dates);assert abs(terminal-content['final_balance'])<.05,(label,terminal,content['final_balance']);assert len(strategy.risk_trace)>=len(dates)-2
 for trace in strategy.risk_trace:
  day=pd.Timestamp(trace['execution_date'])-pd.Timedelta(days=1)
  if day in dates:assert abs(trace['prior_closed_equity']-float(curve.loc[day,'equity']))<.05,(label,day)
 if mode=='futures':assert all(t['leverage']==1 and not t['is_short'] for t in trades)
 normal=[]
 for t in trades:
  orders=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
  if t['exit_reason']=='force_exit':orders=orders[:-1]
  normal +=[(o,t['fee_open'] if o['ft_is_entry'] else t['fee_close']) for o in orders]
 curve.to_csv(folder/'equity_strategy.csv');(folder/'risk_trace.json').write_text(json.dumps(strategy.risk_trace,indent=2)+'\n')
 with gzip.open(folder/'trades.json.gz','wt') as f:json.dump(dict(strategy=name,final_balance=content['final_balance'],trades=trades),f,default=str)
 benchmark=a.benchmark(dates);benchmark.to_csv(folder/'equity_hold_theoretical.csv')
 common=dict(case=label,mode=mode,start=case['start'],end=case['end'],days=len(dates),fee=case['fee'],zero_funding=case['zero_funding'])
 rows.append({**common,'strategy':name,**a.stats(curve),'funding_pnl':float(curve.funding_pnl.iloc[-1]),'normal_fees':sum(float(o['amount'])*float(o['safe_price'])*float(fee) for o,fee in normal),'trades':len(trades),'normal_fills':len(normal),'ledger_error':terminal-content['final_balance']})
 rows.append({**common,'strategy':'BuyAndHoldTheoretical',**a.stats(benchmark),'funding_pnl':float(benchmark.funding_pnl.iloc[-1]),'normal_fees':10000*case['fee']/(1+case['fee']),'trades':None,'normal_fills':3,'ledger_error':None})
 with (root/'summary.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (folder/'completed.json').write_text(json.dumps(case,indent=2)+'\n');print(label,f"return {a.stats(curve)['return_pct']:+.2f}% DD {a.stats(curve)['wallet_drawdown_pct']:.2f}% funding {curve.funding_pnl.iloc[-1]:+.2f}",flush=True)
 del bt.all_bt_content[name]
print(mode,'complete',flush=True);os._exit(0)
