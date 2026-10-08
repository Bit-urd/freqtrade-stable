"""Run independent-start comparisons with one exchange, fresh strategy per window.

Reuse the engine only; trades, custom data, DP cache and wallets are reset by
Freqtrade for each backtest. Fresh strategy instances prevent retained capital
or cooldown state leaking between windows. Raw fills reconcile engine balances.
"""
import argparse
import copy
import csv
import gzip
import gc
import hashlib
import json
import logging
import os
import sys
import time
import shutil
from pathlib import Path

import pandas as pd
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import StrategyResolver

_data=Path(__file__).resolve().parent.parent/'independent_trend_optimization_20261008/data'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import analyze as a

ROOT=Path(__file__).resolve().parent.parent; FOLDER=Path(__file__).resolve().parent
NAMES=['BtcCoinGuardCycleRiskStrategy','Ma200BtcRegimeFullCyclePortfolioStrategy','IndependentHoldCycleRiskStrategy','IndependentAtr2CycleRiskStrategy','IndependentAtr3CycleRiskStrategy','IndependentAtr4CycleRiskStrategy']
PAIRS=['BTC/USDT']
a.PAIRS=PAIRS; a.HISTORY={p:pd.read_feather(_data/(p.replace('/','_')+'-1d.feather')).set_index('date').sort_index() for p in PAIRS}
parser=argparse.ArgumentParser()
parser.add_argument('--labels',nargs='+')
args=parser.parse_args()
windows=json.loads((FOLDER/'windows.json').read_text())
if args.labels: windows=[w for w in windows if w['label'] in args.labels]
logging.disable(logging.WARNING)
cli=Arguments(['backtesting','-c',str(FOLDER/'config.json'),'--datadir',str(_data),'--strategy-path',str(FOLDER/'strategies'),'--timerange',windows[0]['timerange'],'--fee','0.001','--cache','none','--strategy-list',*NAMES]).get_parsed_arg()
config=setup_optimize_configuration(cli,RunMode.BACKTEST)
assert Path(config['datadir'])==_data,config['datadir']
assert config['exchange']['pair_whitelist']==PAIRS and config['max_open_trades']==1
assert config['dry_run_wallet']==1000 and config['fee']==.001
logging.getLogger().setLevel(logging.ERROR)
bt=Backtesting(config, progress_callback=lambda task:None)
# Exchange markets and imported libraries stay alive for the complete run.
# Avoid repeatedly scanning that large stable object graph on this low-RAM host.
gc.freeze()
summary_path=FOLDER/'summary.csv'
rows=list(csv.DictReader(summary_path.open())) if summary_path.exists() else []
references={}
prior_folder=ROOT/'independent_trend_optimization_20261008'
prior_rows={(r['window'],r['strategy']):r for r in csv.DictReader((prior_folder/'summary.csv').open())}
for ref in [ROOT/'single_btc_sui_zec_20261007/summary.csv',ROOT/'two_strategy_comparison_20261007/summary.csv',ROOT/'independent_trend_optimization_20261008/summary.csv']:
    for old in csv.DictReader(ref.open()):
        key=(old.get('pair','PORTFOLIO'),old['window'],old['strategy'])
        references[key]=old
started=time.monotonic()
completed=0
for window in windows:
    pair=window['pair']
    pairs=window.get('pairs',[pair])
    bt.config['max_open_trades']=len(pairs)
    bt.config['exchange']['pair_whitelist']=pairs
    for handler in bt.pairlists._pairlist_handlers:
        if hasattr(handler, '_bt_pair_cache'):
            handler._bt_pair_cache.clear()
    bt.pairlists.refresh_pairlist(pairs=pairs)
    assert bt.pairlists.whitelist==pairs and bt.dataprovider.current_whitelist()==pairs
    a.PAIRS=pairs
    a.HISTORY={p:pd.read_feather(_data/(p.replace('/','_')+'-1d.feather')).set_index('date').sort_index() for p in pairs}
    label=window['label']
    folder=FOLDER/'results'/label
    completion=folder/'completed.json'
    existing={r['strategy'] for r in rows if r['window']==label}
    if completion.exists() and existing==set(NAMES+['BuyAndHold']):
        print('Cached',label,flush=True);completed+=1;continue
    folder.mkdir(parents=True,exist_ok=True)
    rows=[r for r in rows if r['window']!=label]
    bt.config['timerange']=window['timerange']
    bt.timerange=TimeRange.parse_timerange(window['timerange'])
    bt.available_pairs=[]
    data,timerange=bt.load_bt_data()
    assert set(data)==set(pairs)
    bt.all_bt_content={}
    window_rows=[]
    dates=None
    for name in NAMES:
        # Identical frozen sources and data: reuse previously reconciled baseline
        # runs instead of repeatedly backtesting unchanged strategies.
        if name in NAMES[:3]:
            old=copy.deepcopy(prior_rows[label,name])
            assert old['start']==window['start'] and old['end']==window['end']
            assert abs(float(old['ledger_error']))<.05
            assert (FOLDER/'strategies'/('independent_cycle_risk_strategy.py' if name==NAMES[2] else ('cycle_risk_strategy.py' if name==NAMES[0] else 'ma200_btc_regime_full_cycle_portfolio_strategy.py'))).read_bytes()==(prior_folder/'strategies'/('independent_cycle_risk_strategy.py' if name==NAMES[2] else ('cycle_risk_strategy.py' if name==NAMES[0] else 'ma200_btc_regime_full_cycle_portfolio_strategy.py'))).read_bytes()
            old['atr_stop_exits']=0
            window_rows.append(old)
            for filename in [name+'.json.gz','equity_'+name+'.csv','risk_trace_'+name+'.json']:
                source=prior_folder/'results'/label/filename
                if source.exists():shutil.copy2(source,folder/filename)
            if dates is None:dates=pd.date_range(window['start'],window['end'],freq='D',tz='UTC')
            print('Reused verified baseline',name,flush=True)
            continue
        stratconf=copy.deepcopy(bt.config);stratconf['strategy']=name;stratconf.pop('strategy_list',None)
        strat=StrategyResolver.load_strategy(stratconf)
        assert not hasattr(strat,'_phase_initial_capital')
        # Full reset and a fresh wallet guarantee 1000 USDT per independent run.
        bt.init_backtest()
        assert abs(bt.wallets.get_starting_balance()-1000)<1e-8
        minimum,maximum=bt.backtest_one_strategy(strat,data,timerange)
        content=bt.all_bt_content[name]
        if hasattr(strat,'risk_trace'):
            (folder/('risk_trace_'+name+'.json')).write_text(json.dumps(strat.risk_trace,indent=2)+'\n')
        trades=content['results'].to_dict(orient='records')
        assert all(t['pair'] in pairs for t in trades)
        current_dates=pd.date_range(minimum,maximum,freq='D')
        if dates is None:
            dates=current_dates
        else:
            assert dates.equals(current_dates),(label,name,'different dates')
        if 'start' in window:
            assert str(dates[0].date())==window['start'],(label,'start shifted',dates[0])
            assert str(dates[-1].date())==window['end'],(label,'end shifted',dates[-1])
        curve,cash,_=a.ledger(trades,dates)
        for trace in getattr(strat,'risk_trace',[]):
            prior = pd.Timestamp(trace['execution_date']) - pd.Timedelta(days=1)
            if prior in curve.index:
                assert abs(trace['prior_closed_equity']-float(curve.loc[prior,'equity']))<.05, (label, 'controller equity mismatch', trace['execution_date'])
        error=cash-content['final_balance']
        assert abs(error)<.05,(label,name,error)
        metrics=a.stats(curve)
        reference=references.get((pair,label.replace('PORTFOLIO_',''),name))
        if reference:
            for key in ['return_pct','wallet_drawdown_pct']:
                assert abs(metrics[key]-float(reference[key]))<1e-5,(label,name,'baseline drift',key)
        normal_orders=[]
        fast_failed=0
        for trade in trades:
            filled=[o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
            if trade['exit_reason']=='force_exit':
                filled=filled[:-1]
            elif float(trade['profit_abs'])<0 and (pd.Timestamp(trade['close_date'])-pd.Timestamp(trade['open_date'])).total_seconds()<=10*86400:
                fast_failed+=1
            normal_orders.extend((o,trade['fee_open'] if o['ft_is_entry'] else trade['fee_close']) for o in filled)
        metrics.update(normal_fills=len(normal_orders),quick_loss_positions=fast_failed,
                       atr_stop_exits=sum(t['exit_reason']=='independent_atr_close' for t in trades),
                       independent_probe_positions=sum(t['enter_tag']=='independent_probe' for t in trades),
                       normal_fees=sum(float(o['amount'])*float(o['safe_price'])*float(fee) for o,fee in normal_orders))
        common={'pair':pair,'window':label,'cohort':window['cohort'],'start':str(dates[0].date()),'end':str(dates[-1].date()),'days':len(dates)}
        window_rows.append({**common,'strategy':name,**metrics,'ledger_error':error,'trades':len(trades)})
        curve.to_csv(folder/('equity_'+name+'.csv'))
        with gzip.open(folder/(name+'.json.gz'),'wt') as output:
            json.dump({'strategy':name,'timerange':window['timerange'],'start':common['start'],'end':common['end'],'final_balance':content['final_balance'],'trades':trades},output,default=str)
        print(f'Finished {name}: {metrics["return_pct"]:+.2f}% / DD {metrics["wallet_drawdown_pct"]:.2f}%',flush=True)
        del bt.all_bt_content[name]
    bench=a.benchmark(dates);bench.to_csv(folder/'equity_BuyAndHold.csv')
    bm=a.stats(bench)
    window_rows.append({**common,'strategy':'BuyAndHold',**bm,'ledger_error':None,'trades':None,'normal_fills':len(pairs),'quick_loss_positions':None,'atr_stop_exits':None,'independent_probe_positions':None,'normal_fees':1000*.001/1.001})
    rows+=window_rows
    columns=list(window_rows[3])
    tmp=summary_path.with_suffix('.tmp')
    with tmp.open('w') as output:
        writer=csv.DictWriter(output,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    tmp.replace(summary_path)
    completion.write_text(json.dumps({'window':window,'strategies':NAMES,'max_ledger_error':max(abs(float(r['ledger_error'] or 0)) for r in window_rows),'initial_wallet':1000,'fresh_atr_strategy_instances':True,'baseline_source':str(prior_folder)},indent=2)+'\n')
    completed+=1
    (FOLDER/'progress.json').write_text(json.dumps({'completed_in_run':completed,'requested_in_run':len(windows),'total_completed_windows':len(rows)//(len(NAMES)+1),'last_window':label,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
    print(f"{completed}/{len(windows)} {label}: "+'; '.join(f"{r['strategy']} {float(r['return_pct']):+.2f}% / DD {float(r['wallet_drawdown_pct']):.2f}%" for r in window_rows),flush=True)
print('Completed independent-start comparisons.',flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
