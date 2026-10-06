import json
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import analyze as a

ROOT=Path('/research')
source=ROOT/'btc_sol_eth_20221121_20251007'
output=ROOT/'improve_btc_sol_eth'
output.mkdir(exist_ok=True)
a.PAIRS=['BTC/USDT','SOL/USDT','ETH/USDT']
a.HISTORY={p:a.HISTORY[p] for p in a.PAIRS}
with ZipFile(sorted(source.glob('*.zip'))[-1]) as z:
    main=next(n for n in z.namelist() if n.endswith('.json') and not n.endswith('_config.json') and 'strategy' not in n)
    results=json.loads(z.read(main))['strategy']
bench=pd.read_csv(source/'benchmark_coins.csv').set_index('pair')
rows=[]; entry_rows=[]
for name,result in results.items():
    for pair in a.PAIRS:
        cash_flow=0.; qty=0.; fees=0.; buys=0; sells=0
        selected=[t for t in result['trades'] if t['pair']==pair]
        for t in selected:
            orders=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
            for i,o in enumerate(orders):
                if t['exit_reason']=='force_exit' and i==len(orders)-1:
                    continue
                value=o['amount']*o['safe_price']; is_entry=o['ft_is_entry']
                fee=value*(t['fee_open'] if is_entry else t['fee_close'])
                cash_flow+=-value-fee if is_entry else value-fee
                qty+=o['amount'] if is_entry else -o['amount']; fees+=fee
                buys+=int(is_entry); sells+=int(not is_entry)
        close=float(a.HISTORY[pair].loc[pd.Timestamp('2025-10-07',tz='UTC'),'close'])
        profit=cash_flow+qty*close
        rows.append({'strategy':name,'pair':pair,'net_profit_marked':profit,
                     'benchmark_profit':bench.loc[pair,'ending_equity']-1000/3,
                     'profit_gap':profit-(bench.loc[pair,'ending_equity']-1000/3),
                     'fees':fees,'buy_fills':buys,'sell_fills':sells})
        first=sorted(selected,key=lambda t:t['open_timestamp'])[0]
        first_order=next(o for o in first['orders'] if o['ft_is_entry'])
        entry_rows.append({'strategy':name,'pair':pair,'first_entry':first['open_date'],
                           'first_price':first_order['safe_price'],
                           'first_notional':first_order['amount']*first_order['safe_price'],
                           'tag':first['enter_tag']})
    curve=pd.read_csv(source/f'equity_{name}.csv',index_col=0,parse_dates=True)
    btc=a.HISTORY['BTC/USDT']; above=(btc.close>btc.close.rolling(200).mean()).reindex(curve.index)
    print(name,'average cash while BTC above MA200 (%)',100*(curve.cash/curve.equity)[above].mean())
    print(curve.loc[curve.index.intersection(pd.to_datetime(['2022-11-22','2023-01-16','2023-04-01','2023-10-23','2024-03-01','2025-01-01'],utc=True))].to_string())
frame=pd.DataFrame(rows);frame.to_csv(output/'gap_by_coin.csv',index=False)
entries=pd.DataFrame(entry_rows);entries.to_csv(output/'initial_entries.csv',index=False)
print(frame.to_string(index=False));print(entries.to_string(index=False))
