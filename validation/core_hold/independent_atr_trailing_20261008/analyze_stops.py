"""Actual trailing exit fills; deduplicate trades repeated by overlapping windows."""
import csv
import gzip
import json
from pathlib import Path

root = Path(__file__).resolve().parent
rows, unique = [], set()
for window in json.loads((root / 'windows.json').read_text()):
    for multiple in (2, 3, 4):
        name = f'IndependentAtr{multiple}CycleRiskStrategy'
        with gzip.open(root / 'results' / window['label'] / (name + '.json.gz'), 'rt') as f:
            trades = json.load(f)['trades']
        for i, trade in enumerate(trades):
            if trade['exit_reason'] != 'independent_atr_close':
                continue
            following = next((t for t in trades[i + 1:] if t['pair'] == trade['pair']), None)
            next_entry_days = ((following['open_timestamp'] - trade['close_timestamp']) / 86400000
                               if following else None)
            key = (name, trade['pair'], trade['open_timestamp'], trade['close_timestamp'])
            unique.add(key)
            rows.append(dict(window=window['label'], strategy=name, pair=trade['pair'],
                open_date=trade['open_date'], close_date=trade['close_date'],
                open_rate=trade['open_rate'], close_rate=trade['close_rate'],
                net_trade_return_pct=trade['profit_ratio'] * 100,
                profit_abs=trade['profit_abs'], duration_days=trade['trade_duration'] / 1440,
                next_entry_days=next_entry_days))
if rows:
    with (root / 'stop_trades.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
totals = []
for multiple in (2, 3, 4):
    name = f'IndependentAtr{multiple}CycleRiskStrategy'
    sub = [r for r in rows if r['strategy'] == name]
    totals.append(dict(strategy=name, window_trade_count=len(sub),
        distinct_entry_exit_pairs=sum(k[0] == name for k in unique),
        losing_stops=sum(r['net_trade_return_pct'] < 0 for r in sub),
        winning_stops=sum(r['net_trade_return_pct'] >= 0 for r in sub),
        quick_reentry_within_7_days=sum(r['next_entry_days'] is not None and r['next_entry_days'] <= 7 for r in sub)))
(root / 'stop_analysis.json').write_text(json.dumps({'summary': totals,
    'caveat': 'Distinct entry/exit timestamp pairs across overlapping windows are descriptive, not independent experiments; budgets and risk states differ.'}, indent=2) + '\n')
print(json.dumps(totals, indent=2))
