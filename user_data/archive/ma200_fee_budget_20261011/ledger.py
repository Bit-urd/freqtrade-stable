"""Rebuild daily mark-to-market equity from fills, including partial exits.

Run in the same image as backtesting. Terminal force exits are excluded from
mark-to-market curves; a separate fill ledger reconciles engine final_balance.
"""
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

ROOT = Path('/research')
DATA = Path('/research/core3_spot_futures_six_year_20261008/data')
CAPITAL = 1000.
FEE = .001
PAIRS = ['BTC/USDT','ETH/USDT','SOL/USDT']
HISTORY = {}


def stats(curve):
    peak = curve.equity.cummax().clip(lower=CAPITAL)
    return {'return_pct': (curve.equity.iloc[-1]/CAPITAL-1)*100,
            'liquidated_return_pct': ((curve.cash.iloc[-1] +
                                      (curve.equity.iloc[-1]-curve.cash.iloc[-1])*(1-FEE))
                                     /CAPITAL-1)*100,
            'wallet_drawdown_pct': (1-curve.equity/peak).max()*100,
            'mean_idle_cash_pct': (curve.cash/curve.equity).mean()*100,
            'ending_equity': curve.equity.iloc[-1]}


def ledger(trades, dates, skip_force=True):
    flows = pd.Series(0., index=dates)
    quantities = pd.DataFrame(0., index=dates, columns=PAIRS)
    total_cash = CAPITAL
    events = []
    for trade in trades:
        orders = [o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
        for i, order in enumerate(orders):
            amount, rate = float(order['amount']), float(order['safe_price'])
            entry = order['ft_is_entry']
            fee = trade['fee_open'] if entry else trade['fee_close']
            cash_change = -amount*rate*(1+fee) if entry else amount*rate*(1-fee)
            total_cash += cash_change
            if skip_force and trade['exit_reason'] == 'force_exit' and i == len(orders)-1:
                continue
            day = pd.to_datetime(order['order_filled_timestamp'], unit='ms', utc=True).floor('D')
            if day not in dates:
                raise ValueError(f'Order outside valuation dates: {day}')
            flows.loc[day] += cash_change
            quantities.loc[day, trade['pair']] += amount if entry else -amount
            events.append((trade['pair'], day, entry))
    cash = CAPITAL + flows.cumsum()
    qty = quantities.cumsum()
    prices = pd.DataFrame({pair: hist.close.reindex(dates).ffill()
                           for pair, hist in HISTORY.items()})
    if ((qty.abs()>1e-8) & prices.isna()).any().any():
        raise ValueError('Missing prices for a held asset')
    curve = pd.DataFrame({'cash': cash,
                          'equity': cash + (qty*prices).fillna(0).sum(axis=1)})
    return curve, total_cash, events


def benchmark(dates):
    flows = pd.Series(0., index=dates)
    qty = pd.DataFrame(0., index=dates, columns=PAIRS)
    for pair, hist in HISTORY.items():
        # Signal must have >60 own completed candles, then execute next open.
        available = hist.iloc[61:]
        available = available[(available.index >= dates[0]) & (available.index <= dates[-1])]
        if available.empty:
            continue
        day = available.index[0]
        budget = CAPITAL/len(PAIRS)
        flows.loc[day] -= budget
        qty.loc[day, pair] = budget/(1+FEE)/float(hist.loc[day, 'open'])
    cash = CAPITAL+flows.cumsum()
    prices = pd.DataFrame({pair: hist.close.reindex(dates).ffill()
                           for pair, hist in HISTORY.items()})
    return pd.DataFrame({'cash': cash, 'equity': cash+(qty.cumsum()*prices).fillna(0).sum(axis=1)})


def entry_lag(events, dates):
    btc = HISTORY['BTC/USDT']
    above = btc.close > btc.close.rolling(200).mean()
    # BTC regime signal uses today's close; earliest execution is next day's open.
    starts = btc.index[above & ~above.shift(1, fill_value=False)] + pd.Timedelta(days=1)
    lags = []
    for pair, day, entry in events:
        if not entry or day not in btc.index or not above.shift(1, fill_value=False).loc[day]:
            continue
        prior = starts[starts <= day]
        if len(prior):
            lags.append((day-prior[-1]).days)
    return float(np.median(lags)) if lags else None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--windows', nargs='+', default=['train', 'bear', 'test'])
    args = parser.parse_args()
    all_rows = []
    snapshots = {}
    for label in args.windows:
        folder = ROOT/'results'/label
        archive = sorted(folder.glob('*.zip'))[-1]
        with ZipFile(archive) as z:
            name = next(n for n in z.namelist() if n.endswith('.json')
                        and not n.endswith('_config.json') and 'strategy' not in n)
            payload = json.loads(z.read(name))
        strategies = payload['strategy']
        example = next(iter(strategies.values()))
        start = pd.to_datetime(example['backtest_start_ts'], unit='ms', utc=True).floor('D')
        end = pd.to_datetime(example['backtest_end_ts'], unit='ms', utc=True).floor('D')
        dates = pd.date_range(start, end, freq='D')
        print(label, start, end)
        bench = benchmark(dates)
        bench.to_csv(folder/'equity_BuyAndHold.csv')
        all_rows.append({'window': label, 'strategy': 'BuyAndHold', **stats(bench)})
        for name, result in strategies.items():
            curve, terminal_cash, events = ledger(result['trades'], dates)
            delta = terminal_cash - result['final_balance']
            if abs(delta) > .05:
                raise ValueError(f'{label}/{name}: fill ledger differs from engine by {delta}')
            row = {'window': label, 'strategy': name, **stats(curve),
                   'engine_final_balance': result['final_balance'],
                   'ledger_reconciliation_error': delta,
                   'trades': result['total_trades'],
                   'median_bull_entry_lag_days': entry_lag(events, dates)}
            all_rows.append(row)
            curve.to_csv(folder/f'equity_{name}.csv')
        snapshots[label] = {'start': str(start), 'end': str(end)}
    table = pd.DataFrame(all_rows)
    table.to_csv(ROOT/'summary.csv', index=False)
    candidates = table[(table.window=='train') & table.strategy.str.startswith('CoreHold_')]
    best_return = candidates.sort_values('return_pct', ascending=False).iloc[0].strategy
    # Secondary choice penalizes large drawdowns; criterion defined before inspecting results.
    score = candidates.return_pct - 2*candidates.wallet_drawdown_pct
    balanced = candidates.loc[score.idxmax(), 'strategy']
    chosen = ['BuyAndHold', 'Ma200BtcRegimeFullCyclePortfolioStrategy',
              'Ma200BtcRegimeFullCycleCoreHoldStrategy', best_return, balanced]
    view = table[table.strategy.isin(chosen)].copy()
    (ROOT/'selection.json').write_text(json.dumps({'best_training_return': best_return,
                                                  'training_return_minus_2dd': balanced,
                                                  'windows': snapshots}, indent=2))
    print(view[['window','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct']]
          .to_string(index=False))
    print('All fills reconciled with engine final balances (tolerance 0.05 USDT).')


if __name__ == '__main__':
    main()
