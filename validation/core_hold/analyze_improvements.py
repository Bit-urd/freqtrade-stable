import argparse
import json
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import analyze as a

ROOT=Path('/research');FOLDER=ROOT/'improve_btc_sol_eth'
parser=argparse.ArgumentParser();parser.add_argument('--labels',nargs='+',default=['requested','recovery'])
args=parser.parse_args()
a.PAIRS=['BTC/USDT','SOL/USDT','ETH/USDT'];a.HISTORY={p:a.HISTORY[p] for p in a.PAIRS}
rows=[]
for label in args.labels:
    folder=FOLDER/'results'/label
    with ZipFile(sorted(folder.glob('*.zip'))[-1]) as z:
        main=next(n for n in z.namelist() if n.endswith('.json') and not n.endswith('_config.json') and 'strategy' not in n)
        strategies=json.loads(z.read(main))['strategy']
    example=next(iter(strategies.values()))
    start=pd.to_datetime(example['backtest_start_ts'],unit='ms',utc=True).floor('D')
    end=pd.to_datetime(example['backtest_end_ts'],unit='ms',utc=True).floor('D')
    dates=pd.date_range(start,end,freq='D')
    bench=a.benchmark(dates);bench.to_csv(folder/'equity_BuyAndHold.csv')
    rows.append({'window':label,'strategy':'BuyAndHold','start':str(start),'end':str(end),**a.stats(bench)})
    for name,result in strategies.items():
        curve,cash,_=a.ledger(result['trades'],dates)
        delta=cash-result['final_balance'];assert abs(delta)<.05,(label,name,delta)
        curve.to_csv(folder/f'equity_{name}.csv')
        rows.append({'window':label,'strategy':name,'start':str(start),'end':str(end),
                     **a.stats(curve),'engine_final_balance':result['final_balance'],
                     'ledger_reconciliation_error':delta,'trades':result['total_trades']})
frame=pd.DataFrame(rows);frame.to_csv(FOLDER/'summary.csv',index=False)
requested=frame[frame.window.isin(['requested','recovery'])].drop_duplicates('strategy',keep='last')
if not requested.empty:
    # Add original/default reference from the exact same three-pair period.
    baseline=pd.read_csv(ROOT/'btc_sol_eth_20221121_20251007/summary.csv')
    for _,r in baseline.iterrows():
        if r.strategy not in requested.strategy.values:
            requested=pd.concat([requested,pd.DataFrame([{**r.to_dict(),'window':'baseline'}])],ignore_index=True)
    requested=requested.sort_values('return_pct',ascending=False)
    requested.to_csv(FOLDER/'requested_comparison.csv',index=False)
    if 'recovery' in args.labels:
        r=requested[requested.strategy=='Ma200BtcRegimeFullCycleCoreHoldStrategy'].iloc[0]
        original=baseline[baseline.strategy==r.strategy].iloc[0]
        assert abs(r.return_pct-original.return_pct)<1e-7, 'Default performance changed'
    candidates=requested[~requested.strategy.isin(['BuyAndHold','Ma200BtcRegimeFullCyclePortfolioStrategy','Ma200BtcRegimeFullCycleCoreHoldStrategy'])]
    if not candidates.empty:
        selection={'highest_return':candidates.iloc[0].strategy,
                   'return_minus_2dd':candidates.loc[(candidates.return_pct-2*candidates.wallet_drawdown_pct).idxmax(),'strategy']}
        (FOLDER/'selection.json').write_text(json.dumps(selection,indent=2))
    print('Requested-window comparison:')
    print(requested[['strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct','ending_equity']].to_string(index=False))
print('All windows:')
print(frame[['window','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct']].to_string(index=False))
