"""Run ten isolated one-coin groups, three frozen profiles and holding."""
import copy
import csv
import gc
import gzip
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

ROOT=Path('/research');FOLDER=ROOT/'single_coin_comparison'
plan=json.loads((FOLDER/'plan.json').read_text());NAMES=plan['strategies'];PAIRS=plan['pairs']
master={p:pd.read_feather(Path('/freqtrade/user_data/data/binance')/(p.replace('/','_')+'-1d.feather')).set_index('date').sort_index() for p in PAIRS}
data_audit=[]
start=pd.Timestamp('2022-11-21',tz='UTC');end=pd.Timestamp('2025-10-07',tz='UTC');expected=pd.date_range(start,end,freq='D')
for pair,h in master.items():
    assert h.index.is_unique and (h.close>0).all()
    assert not expected.difference(h.index).size,(pair,'missing interval days')
    assert (h.index<start).sum()>60,(pair,'insufficient warmup')
    weekly=Path('/freqtrade/user_data/data/binance')/(pair.replace('/','_')+'-1w.feather')
    assert weekly.exists()
    data_audit.append({'pair':pair,'first':str(h.index[0]),'last':str(h.index[-1]),'rows':len(h),'window_missing_days':0,'warmup_days':int((h.index<start).sum()),'weekly_sha256':hashlib.sha256(weekly.read_bytes()).hexdigest()})
(FOLDER/'data_audit.json').write_text(json.dumps(data_audit,indent=2)+'\n')
logging.disable(logging.WARNING)
cli=Arguments(['backtesting','-c',str(FOLDER/'config.json'),'--strategy-path',str(FOLDER/'strategies'),'--timerange',plan['timerange'],'--fee','0.001','--cache','none','--strategy-list',*NAMES]).get_parsed_arg()
config=setup_optimize_configuration(cli,RunMode.BACKTEST)
assert config['max_open_trades']==1 and config['dry_run_wallet']==1000
bt=Backtesting(config,progress_callback=lambda task:None);gc.freeze()
summary=FOLDER/'summary.csv';rows=list(csv.DictReader(summary.open())) if summary.exists() else []
started=time.monotonic()
for i,pair in enumerate(PAIRS,1):
    label=pair.split('/')[0];folder=FOLDER/'results'/label;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'completed.json').exists() and {r['strategy'] for r in rows if r['pair']==pair}==set(NAMES+['BuyAndHold']):
        print('Cached',pair,flush=True);continue
    rows=[r for r in rows if r['pair']!=pair]
    bt.config['exchange']['pair_whitelist']=[pair]
    bt.pairlists.refresh_pairlist(pairs=[pair])
    assert bt.pairlists.whitelist==[pair] and bt.dataprovider.current_whitelist()==[pair]
    bt.timerange=TimeRange.parse_timerange(plan['timerange']);bt.available_pairs=[]
    data,timerange=bt.load_bt_data();assert set(data)=={pair}
    a.PAIRS=[pair];a.HISTORY={pair:master[pair]}
    group_rows=[];dates=None
    for name in NAMES:
        cfg=copy.deepcopy(bt.config);cfg['strategy']=name;cfg.pop('strategy_list',None)
        assert cfg['exchange']['pair_whitelist']==[pair] and cfg['max_open_trades']==1
        strat=StrategyResolver.load_strategy(cfg);assert not hasattr(strat,'_phase_initial_capital')
        bt.init_backtest();assert bt.wallets.get_starting_balance()==1000
        minimum,maximum=bt.backtest_one_strategy(strat,data,timerange)
        content=bt.all_bt_content[name];trades=content['results'].to_dict(orient='records')
        assert all(t['pair']==pair for t in trades),(pair,name,'other coin traded')
        ds=pd.date_range(minimum,maximum,freq='D')
        assert ds.equals(expected),(pair,name,'changed dates')
        dates=ds
        curve,cash,_=a.ledger(trades,dates);error=cash-content['final_balance'];assert abs(error)<.05,(pair,name,error)
        common={'pair':pair,'start':str(dates[0].date()),'end':str(dates[-1].date()),'days':len(dates)}
        group_rows.append({**common,'strategy':name,**a.stats(curve),'ledger_error':error,'trades':len(trades)})
        curve.to_csv(folder/('equity_'+name+'.csv'))
        with gzip.open(folder/(name+'.json.gz'),'wt') as out:
            json.dump({'pair':pair,'strategy':name,'final_balance':content['final_balance'],'trades':trades,'timerange':plan['timerange']},out,default=str)
        del bt.all_bt_content[name]
    benchmark=a.benchmark(dates);benchmark.to_csv(folder/'equity_BuyAndHold.csv')
    hold_stats=a.stats(benchmark)
    group_rows.append({**common,'strategy':'BuyAndHold',**hold_stats,'ledger_error':None,'trades':None})
    for row in group_rows:
        row['hold_return_pct']=hold_stats['return_pct'];row['hold_drawdown_pct']=hold_stats['wallet_drawdown_pct']
        row['return_fraction_of_hold']=row['return_pct']/hold_stats['return_pct'] if hold_stats['return_pct']>0 else None
        row['drawdown_improvement_pp']=hold_stats['wallet_drawdown_pct']-row['wallet_drawdown_pct']
        row['drawdown_better_than_hold']=row['wallet_drawdown_pct']<hold_stats['wallet_drawdown_pct']
        row['two_thirds_return_met']=row['return_pct']>=hold_stats['return_pct']*2/3 if hold_stats['return_pct']>0 else None
        row['joint_target_met']=row['two_thirds_return_met'] and row['drawdown_better_than_hold'] if hold_stats['return_pct']>0 else None
    rows+=group_rows
    tmp=summary.with_suffix('.tmp')
    with tmp.open('w') as out:
        writer=csv.DictWriter(out,fieldnames=list(group_rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    tmp.replace(summary)
    (folder/'completed.json').write_text(json.dumps({'pair':pair,'max_open_trades':1,'initial_capital':1000,'only_requested_coin_traded':True,'btc_indicator_only':pair!='BTC/USDT','max_ledger_error':max(abs(x['ledger_error'] or 0) for x in group_rows)},indent=2)+'\n')
    (FOLDER/'progress.json').write_text(json.dumps({'completed_groups':i,'groups':len(PAIRS),'last_pair':pair,'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
    print(f'{i}/{len(PAIRS)} {pair}: '+'; '.join(f"{x['strategy']} {x['return_pct']:+.2f}% / DD {x['wallet_drawdown_pct']:.2f}%" for x in group_rows),flush=True)
print('Completed 10 single-coin groups.',flush=True);sys.stdout.flush();sys.stderr.flush();os._exit(0)
