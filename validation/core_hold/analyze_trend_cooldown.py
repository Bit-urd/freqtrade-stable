"""Reconcile every fill and compare daily total equity to equal holding."""
import json
import sys
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import analyze as a
ROOT=Path('/research'); FOLDER=ROOT/'trend_cooldown'
a.PAIRS=['BTC/USDT','SOL/USDT','ETH/USDT']; a.HISTORY={p:a.HISTORY[p] for p in a.PAIRS}
rows=[]
summary_path=FOLDER/'summary.csv'
cache=pd.read_csv(summary_path) if summary_path.exists() and '--available' in sys.argv else pd.DataFrame()
cache_time=summary_path.stat().st_mtime if not cache.empty else 0.
for w in json.loads((FOLDER/'windows.json').read_text()):
    folder=FOLDER/'results'/w['label']; files=sorted(folder.glob('*.zip'))
    if not files: continue
    strategies={}
    for file in files:
        with ZipFile(file) as z:
            name=next(n for n in z.namelist() if n.endswith('.json') and not n.endswith('_config.json') and 'strategy' not in n)
            strategies.update(json.loads(z.read(name))['strategy'])
    cached=cache[cache.window==w['label']] if not cache.empty else pd.DataFrame()
    if (not cached.empty and max(f.stat().st_mtime for f in files) <= cache_time
            and set(strategies).issubset(set(cached.strategy))):
        # Archives are immutable and this sequential runner cannot export while
        # analysis is running. Reuse already reconciled, unchanged windows.
        errors=cached.ledger_error.dropna()
        assert (errors.abs()<.05).all()
        rows.extend(cached.to_dict('records'))
        continue
    example=next(iter(strategies.values()))
    dates=pd.date_range(pd.to_datetime(example['backtest_start_ts'],unit='ms',utc=True).floor('D'),pd.to_datetime(example['backtest_end_ts'],unit='ms',utc=True).floor('D'),freq='D')
    bench=a.benchmark(dates);bench.to_csv(folder/'equity_BuyAndHold.csv')
    common={'window':w['label'],'start':str(dates[0].date()),'end':str(dates[-1].date())}
    br=a.stats(bench)['return_pct']
    rows.append({**common,'strategy':'BuyAndHold',**a.stats(bench),'gap_pp':0.})
    for name,result in strategies.items():
        curve,cash,_=a.ledger(result['trades'],dates)
        error=cash-result['final_balance']; assert abs(error)<.05,(name,error)
        curve.to_csv(folder/f'equity_{name}.csv')
        st=a.stats(curve)
        rows.append({**common,'strategy':name,**st,'gap_pp':br-st['return_pct'],'ledger_error':error,'trades':result['total_trades']})
frame=pd.DataFrame(rows);frame.to_csv(FOLDER/'summary.csv',index=False)
print(frame[['window','strategy','return_pct','wallet_drawdown_pct','gap_pp']].to_string(index=False),flush=True)
