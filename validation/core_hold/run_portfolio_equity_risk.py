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
from pathlib import Path

import pandas as pd
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import StrategyResolver

import analyze as a

ROOT=Path('/research'); FOLDER=ROOT/'archive/portfolio_equity_risk'
NAMES=['BtcCoinGuardEquityRiskStrategy']
PAIRS=['BTC/USDT','SOL/USDT','ETH/USDT']
a.PAIRS=PAIRS; a.HISTORY={p:a.HISTORY[p] for p in PAIRS}
parser=argparse.ArgumentParser()
parser.add_argument('--labels',nargs='+')
args=parser.parse_args()
windows=json.loads((FOLDER/'windows.json').read_text())
if args.labels: windows=[w for w in windows if w['label'] in args.labels]
logging.disable(logging.WARNING)
cli=Arguments(['backtesting','-c',str(FOLDER/'config.json'),'--strategy-path',str(FOLDER/'strategies'),'--timerange',windows[0]['timerange'],'--fee','0.001','--cache','none','--strategy-list',*NAMES]).get_parsed_arg()
config=setup_optimize_configuration(cli,RunMode.BACKTEST)
assert config['exchange']['pair_whitelist']==PAIRS and config['max_open_trades']==3
assert config['dry_run_wallet']==1000 and config['fee']==.001
logging.getLogger().setLevel(logging.ERROR)
bt=Backtesting(config, progress_callback=lambda task:None)
# Exchange markets and imported libraries stay alive for the complete run.
# Avoid repeatedly scanning that large stable object graph on this low-RAM host.
gc.freeze()
summary_path=FOLDER/'summary.csv'
rows=list(csv.DictReader(summary_path.open())) if summary_path.exists() else []
started=time.monotonic()
completed=0
for window in windows:
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
    bt.all_bt_content={}
    window_rows=[]
    dates=None
    for name in NAMES:
        stratconf=copy.deepcopy(bt.config);stratconf['strategy']=name;stratconf.pop('strategy_list',None)
        strat=StrategyResolver.load_strategy(stratconf)
        assert not hasattr(strat,'_phase_initial_capital')
        # Full reset and a fresh wallet guarantee 1000 USDT per independent run.
        bt.init_backtest()
        assert abs(bt.wallets.get_starting_balance()-1000)<1e-8
        minimum,maximum=bt.backtest_one_strategy(strat,data,timerange)
        content=bt.all_bt_content[name]
        (folder/'risk_trace.json').write_text(json.dumps(strat.risk_trace,indent=2)+'\n')
        trades=content['results'].to_dict(orient='records')
        current_dates=pd.date_range(minimum,maximum,freq='D')
        if dates is None:
            dates=current_dates
        else:
            assert dates.equals(current_dates),(label,name,'different dates')
        if 'start' in window:
            assert str(dates[0].date())==window['start'],(label,'start shifted',dates[0])
            assert str(dates[-1].date())==window['end'],(label,'end shifted',dates[-1])
        curve,cash,_=a.ledger(trades,dates)
        error=cash-content['final_balance']
        assert abs(error)<.05,(label,name,error)
        metrics=a.stats(curve)
        common={'window':label,'cohort':window['cohort'],'start':str(dates[0].date()),'end':str(dates[-1].date()),'days':len(dates)}
        window_rows.append({**common,'strategy':name,**metrics,'ledger_error':error,'trades':len(trades)})
        curve.to_csv(folder/('equity_'+name+'.csv'))
        with gzip.open(folder/(name+'.json.gz'),'wt') as output:
            json.dump({'strategy':name,'timerange':window['timerange'],'start':common['start'],'end':common['end'],'final_balance':content['final_balance'],'trades':trades},output,default=str)
        del bt.all_bt_content[name]
    bench=a.benchmark(dates);bench.to_csv(folder/'equity_BuyAndHold.csv')
    bm=a.stats(bench)
    window_rows.append({**common,'strategy':'BuyAndHold',**bm,'ledger_error':None,'trades':None})
    # Existing five-regime measurements anchor the new engine path.
    if window['cohort']=='reference':
        old_label=window['reference_label']
        baseline=list(csv.DictReader((ROOT/'trend_phased/retained_comparison.csv').open()))
        revision=list(csv.DictReader((ROOT/'drawdown_revision/summary.csv').open()))
        portfolio=list(csv.DictReader((ROOT/'regime_comparison/summary.csv').open()))
        portfolio+=list(csv.DictReader((ROOT/'btc_sol_eth_20221121_20251007/summary.csv').open()))
        for row in window_rows:
            search_name='PhasedFastExit100' if row['strategy']=='BtcTrendFastExitStrategy' else row['strategy']
            previous=[r for r in baseline+revision+portfolio if r.get('window', 'requested_long')==old_label and r['strategy']==search_name]
            if previous:
                for key in ['return_pct','wallet_drawdown_pct']:
                    assert abs(float(previous[0][key])-row[key])<1e-5,(label,row['strategy'],key,previous[0][key],row[key])
    rows+=window_rows
    columns=list(window_rows[0])
    tmp=summary_path.with_suffix('.tmp')
    with tmp.open('w') as output:
        writer=csv.DictWriter(output,fieldnames=columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
    tmp.replace(summary_path)
    completion.write_text(json.dumps({'window':window,'strategies':NAMES,'max_ledger_error':max(abs(r['ledger_error'] or 0) for r in window_rows),'initial_wallet':1000,'fresh_strategy_instances':True},indent=2)+'\n')
    completed+=1
    (FOLDER/'progress.json').write_text(json.dumps({'completed_in_run':completed,'requested_in_run':len(windows),'total_completed_windows':len(rows)//(len(NAMES)+1),'last_window':label,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
    print(f"{completed}/{len(windows)} {label}: "+'; '.join(f"{r['strategy']} {r['return_pct']:+.2f}% / DD {r['wallet_drawdown_pct']:.2f}%" for r in window_rows),flush=True)
print('Completed independent-start comparisons.',flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
