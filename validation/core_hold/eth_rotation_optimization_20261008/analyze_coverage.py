"""Measure signal overlap with the original BTC gate, using saved causal CSVs."""
import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parent
names = ['EthRotationCycleRiskStrategy', 'EthBreadthRotationCycleRiskStrategy']
history = {}
def flag(row, key):
    return row[key] == 'True'
for name in names:
    for coin in ['SUI', 'ZEC', 'ADA', 'DOGE', 'AVAX', 'SOL', 'ETH']:
        history[name, coin + '/USDT'] = list(csv.DictReader((root / 'signal_audit' / (name + '_' + coin + '_USDT.csv')).open()))
coverage = []
for window in json.loads((root / 'windows.json').read_text()):
    for pair in window.get('pairs', [window['pair']]):
        if pair == 'BTC/USDT': continue
        for name in names:
            rows = [r for r in history[name, pair] if window['start'] <= r['date'][:10] <= window['end']]
            eth = sum(flag(r, 'eth_rotation_confirmed') for r in rows)
            btc_closed = sum(flag(r, 'eth_rotation_confirmed') and not flag(r, 'exposure_entry') for r in rows)
            extra = sum(flag(r, 'rotation_allowed') and not flag(r, 'exposure_entry') for r in rows)
            own = sum(flag(r, 'extra_entry_candidate') for r in rows)
            coverage.append(dict(window=window['label'], pair=pair, strategy=name,
                days=len(rows), eth_dual_trend_days=eth,
                eth_dual_when_btc_entry_closed_days=btc_closed,
                extra_permission_days=extra, extra_permission_with_own_entry_days=own,
                caveat='Signal days precede next-open execution; no adjustment for cooldown, existing holdings or cash.'))
with (root / 'signal_coverage.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=list(coverage[0])); writer.writeheader(); writer.writerows(coverage)
print('Saved', len(coverage), 'per-window signal coverage rows')
