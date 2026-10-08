"""Reconcile benchmark transaction-fee totals with the budget actually invested."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent;windows=json.loads((root/'windows.json').read_text());p=root/'summary.csv';rows=list(csv.DictReader(p.open()));assert len(rows)==len(windows)*3
assert all((root/'results'/w['label']/'completed.json').exists() for w in windows)
for r in rows:
 if r['strategy']=='BuyAndHold':
  with (root/'results'/r['window']/'equity_BuyAndHold.csv').open() as f:curve=list(csv.DictReader(f))
  invested=1000-float(curve[-1]['cash']);r['normal_fees']=invested*.001/1.001
with p.with_suffix('.tmp').open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
p.with_suffix('.tmp').replace(p)
print('Benchmark fee metadata reconciled to actual invested capital')
