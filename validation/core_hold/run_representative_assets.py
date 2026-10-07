"""Frozen multi-asset, multi-regime native backtests, one coin/account per case."""
import copy,csv,gc,gzip,hashlib,json,logging,os,sys,time
from pathlib import Path
import pandas as pd
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.configuration import TimeRange
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers import StrategyResolver
import analyze as a
ROOT=Path('/research');FOLDER=ROOT/'representative_assets'
plan=json.loads((FOLDER/'plan.json').read_text());NAMES=plan['strategies'];PAIRS=plan['pairs']
master={p:pd.read_feather(Path('/freqtrade/user_data/data/binance')/(p.replace('/','_')+'-1d.feather')).set_index('date').sort_index() for p in PAIRS}
cases=[];skipped=[];audit=[]
for pair,h in master.items():
    assert h.index.is_unique and (h.close>0).all()
    weekly=Path('/freqtrade/user_data/data/binance')/(pair.replace('/','_')+'-1w.feather');assert weekly.exists(),pair
    audit.append({'pair':pair,'first':str(h.index[0]),'last':str(h.index[-1]),'daily_sha256':hashlib.sha256((weekly.parent/(pair.replace('/','_')+'-1d.feather')).read_bytes()).hexdigest(),'weekly_sha256':hashlib.sha256(weekly.read_bytes()).hexdigest()})
    for w in plan['windows']:
        lo,hi=w['timerange'].split('-');start=pd.to_datetime(lo,utc=True);end=pd.to_datetime(hi,utc=True)
        expected=pd.date_range(start,min(end,h.index[-1]),freq='D')
        if start<h.index[0] or (h.index<start).sum()<plan['minimum_pre_start_daily_rows']:
            skipped.append({'pair':pair,'window':w['label'],'reason':'Not listed or insufficient 210-day pre-start history; do not change start.'});continue
        assert end-h.index[-1]<=pd.Timedelta(days=1),(pair,'incomplete end history')
        assert not expected.difference(h.index).size,(pair,w['label'],'missing days')
        cases.append((pair,w,expected))
(FOLDER/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n');(FOLDER/'skipped.json').write_text(json.dumps(skipped,indent=2)+'\n')
logging.disable(logging.WARNING)
cli=Arguments(['backtesting','-c',str(FOLDER/'config.json'),'--strategy-path',str(FOLDER/'strategies'),'--timerange',cases[0][1]['timerange'],'--fee','0.001','--cache','none','--strategy-list',*NAMES]).get_parsed_arg()
bt=Backtesting(setup_optimize_configuration(cli,RunMode.BACKTEST),progress_callback=lambda task:None);gc.freeze()
summary=FOLDER/'summary.csv';rows=list(csv.DictReader(summary.open())) if summary.exists() else [];started=time.monotonic()
for i,(pair,w,expected) in enumerate(cases,1):
    label=w['label'];folder=FOLDER/'results'/pair.split('/')[0]/label;folder.mkdir(parents=True,exist_ok=True)
    if (folder/'completed.json').exists() and {r['strategy'] for r in rows if r['pair']==pair and r['window']==label}==set(NAMES+['BuyAndHold']):
        print('Cached',pair,label,flush=True);continue
    rows=[r for r in rows if not(r['pair']==pair and r['window']==label)]
    bt.config['exchange']['pair_whitelist']=[pair];bt.pairlists.refresh_pairlist(pairs=[pair]);assert bt.dataprovider.current_whitelist()==[pair]
    bt.config['timerange']=w['timerange'];bt.timerange=TimeRange.parse_timerange(w['timerange']);bt.available_pairs=[];data,timerange=bt.load_bt_data();assert set(data)=={pair}
    a.PAIRS=[pair];a.HISTORY={pair:master[pair]};group=[];bt.all_bt_content={}
    for name in NAMES:
        cfg=copy.deepcopy(bt.config);cfg['strategy']=name;cfg.pop('strategy_list',None)
        strat=StrategyResolver.load_strategy(cfg);assert not hasattr(strat,'_phase_initial_capital')
        bt.init_backtest();assert bt.wallets.get_starting_balance()==1000
        minimum,maximum=bt.backtest_one_strategy(strat,data,timerange);content=bt.all_bt_content[name];trades=content['results'].to_dict(orient='records')
        assert all(t['pair']==pair for t in trades)
        dates=pd.date_range(minimum,maximum,freq='D');assert dates.equals(expected),(pair,label,name,minimum,maximum,expected[0],expected[-1])
        curve,cash,_=a.ledger(trades,dates);error=cash-content['final_balance'];assert abs(error)<.05,(pair,label,name,error)
        trace_error=0.
        if hasattr(strat,'risk_trace'):
            for t in strat.risk_trace:
                prior=pd.Timestamp(t['execution_date'])-pd.Timedelta(days=1)
                if prior in curve.index: trace_error=max(trace_error,abs(t['prior_closed_equity']-float(curve.loc[prior,'equity'])))
            assert trace_error<.05,(pair,label,'risk equity error',trace_error)
            (folder/'risk_trace.json').write_text(json.dumps(strat.risk_trace,indent=2)+'\n')
        common={'pair':pair,'asset_type':plan['asset_types'][pair],'window':label,'start':str(dates[0].date()),'end':str(dates[-1].date()),'days':len(dates)}
        group.append({**common,'strategy':name,**a.stats(curve),'ledger_error':error,'risk_trace_error':trace_error,'trades':len(trades)})
        curve.to_csv(folder/('equity_'+name+'.csv'))
        with gzip.open(folder/(name+'.json.gz'),'wt') as out: json.dump({'strategy':name,'trades':trades,'final_balance':content['final_balance']},out,default=str)
        del bt.all_bt_content[name]
    bench=a.benchmark(dates);hs=a.stats(bench);bench.to_csv(folder/'equity_BuyAndHold.csv');group.append({**common,'strategy':'BuyAndHold',**hs,'ledger_error':None,'risk_trace_error':None,'trades':None})
    for x in group:
        x['hold_return_pct']=hs['return_pct'];x['hold_drawdown_pct']=hs['wallet_drawdown_pct'];x['return_fraction_of_hold']=x['return_pct']/hs['return_pct'] if hs['return_pct']>0 else None
        x['joint_target_met']=(x['return_pct']>=hs['return_pct']*2/3 and x['wallet_drawdown_pct']<hs['wallet_drawdown_pct']) if hs['return_pct']>0 else None
    rows+=group;tmp=summary.with_suffix('.tmp')
    with tmp.open('w') as out:
        writer=csv.DictWriter(out,fieldnames=list(group[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    tmp.replace(summary);(folder/'completed.json').write_text(json.dumps({'pair':pair,'window':label,'strategies':NAMES,'max_ledger_error':max(abs(x['ledger_error'] or 0) for x in group),'max_risk_trace_error':max(x['risk_trace_error'] or 0 for x in group)},indent=2)+'\n')
    (FOLDER/'progress.json').write_text(json.dumps({'completed_cases':i,'total_cases':len(cases),'skipped':len(skipped),'elapsed_seconds':time.monotonic()-started},indent=2)+'\n')
    print(f'{i}/{len(cases)} {pair} {label}: '+'; '.join(f"{x['strategy']} {x['return_pct']:+.2f}%/{x['wallet_drawdown_pct']:.2f}%" for x in group),flush=True)
print('Finished',len(cases),'cases',len(cases)*len(NAMES),'native runs',flush=True);sys.stdout.flush();sys.stderr.flush();os._exit(0)
