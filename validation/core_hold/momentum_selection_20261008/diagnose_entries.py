"""Attribute original positions to their causal initial-entry MA150 regime."""
import csv
import gzip
import json
import statistics
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent
prior = root.parent / 'independent_trend_optimization_20261008'
histories = {p.stem.split('-')[0].replace('_', '/'): pd.read_feather(p).set_index('date')
             for p in (prior / 'data').glob('*-1d.feather')}
for history in histories.values():
    history['ma150'] = history.close.rolling(150).mean()
    history['ema10'] = history.close.ewm(span=10, adjust=False).mean()

records, summaries = [], []
for window in json.loads((prior / 'windows.json').read_text()):
    label = window['label']
    with gzip.open(prior / 'results' / label / 'BtcCoinGuardCycleRiskStrategy.json.gz', 'rt') as f:
        trades = json.load(f)['trades']
    ending = pd.Timestamp(window['end'], tz='UTC')
    for trade in trades:
        history = histories[trade['pair']]
        opened = pd.Timestamp(trade['open_date'])
        available = history.loc[history.index < opened.normalize()]
        assert not available.empty
        signal = available.iloc[-1]
        assert pd.notna(signal.ma150)
        group = 'above_ma150' if signal.close > signal.ma150 else 'ema10_recovery_below_ma150'
        if group == 'ema10_recovery_below_ma150':
            assert signal.close > signal.ema10 and signal.ema10 > available.ema10.iloc[-2]
        orders = [o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
        mtm_profit, amount = 0., 0.
        for i, order in enumerate(orders):
            if trade['exit_reason'] == 'force_exit' and i == len(orders) - 1:
                continue
            quantity, price = float(order['amount']), float(order['safe_price'])
            if order['ft_is_entry']:
                mtm_profit -= quantity * price * (1 + trade['fee_open']); amount += quantity
            else:
                mtm_profit += quantity * price * (1 - trade['fee_close']); amount -= quantity
        mtm_profit += amount * float(history.loc[ending, 'close'])
        records.append(dict(window=label, pair=trade['pair'], group=group,
            open_date=trade['open_date'], signal_date=str(available.index[-1]),
            signal_close=float(signal.close), signal_ma150=float(signal.ma150),
            exit_reason=trade['exit_reason'], duration_days=trade['trade_duration'] / 1440,
            net_closed_return_pct=trade['profit_ratio'] * 100 if trade['exit_reason'] != 'force_exit' else None,
            mtm_profit_abs=mtm_profit,
            quick_loss=trade['exit_reason'] != 'force_exit' and trade['profit_abs'] < 0 and trade['trade_duration'] <= 14400))
    subset = [r for r in records if r['window'] == label]
    prior_rows = list(csv.DictReader((prior / 'summary.csv').open()))
    original = next(r for r in prior_rows if r['window'] == label and r['strategy'] == 'BtcCoinGuardCycleRiskStrategy')
    error = sum(r['mtm_profit_abs'] for r in subset) - (float(original['ending_equity']) - 1000)
    assert abs(error) < .05, (label, 'attribution mismatch', error)
    for group in ['above_ma150', 'ema10_recovery_below_ma150']:
        group_rows = [r for r in subset if r['group'] == group]
        closed = [r for r in group_rows if r['net_closed_return_pct'] is not None]
        summaries.append(dict(window=label, group=group, positions=len(group_rows),
            normally_closed=len(closed), winning_closed=sum(r['net_closed_return_pct'] > 0 for r in closed),
            quick_losses=sum(r['quick_loss'] for r in group_rows),
            median_closed_return_pct=statistics.median(r['net_closed_return_pct'] for r in closed) if closed else None,
            mean_closed_return_pct=statistics.mean(r['net_closed_return_pct'] for r in closed) if closed else None,
            mtm_profit_abs=sum(r['mtm_profit_abs'] for r in group_rows), attribution_error=error))
for name, rows in [('entry_regime_trades.csv', records), ('entry_regime_summary.csv', summaries)]:
    with (root / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
(root / 'diagnostic_verification.json').write_text(json.dumps(dict(passed=True, windows=43,
    positions=len(records), max_attribution_error=max(abs(r['attribution_error']) for r in summaries),
    terminal_open_trades='Valued at final daily close, exclude artificial terminal exit',
    partial_fills='Attributed to initial-entry regime for the complete position lifecycle',
    caveat='Overlapping windows; descriptive attribution, not causal removal effect.'), indent=2) + '\n')
print('Attributed', len(records), 'positions across 43 windows', flush=True)
