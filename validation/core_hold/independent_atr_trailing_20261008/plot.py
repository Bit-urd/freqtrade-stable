"""Standalone equity artifact; reads CSVs without pandas."""
import csv
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
names = [('BtcCoinGuardCycleRiskStrategy', 'Original BTC guard'),
         ('IndependentHoldCycleRiskStrategy', 'Independent hold'),
         ('IndependentAtr2CycleRiskStrategy', 'ATR 2'),
         ('IndependentAtr3CycleRiskStrategy', 'ATR 3'),
         ('IndependentAtr4CycleRiskStrategy', 'ATR 4'),
         ('BuyAndHold', 'Buy and hold')]
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
for ax, window in zip(axes.flat, ['ZEC_recent', 'ZEC_bull_2023_2024', 'SUI_since_maturity', 'DOGE_bear_2022']):
    for name, label in names:
        records = list(csv.DictReader((root / 'results' / window / ('equity_' + name + '.csv')).open()))
        date_key = list(records[0])[0]
        dates = [datetime.fromisoformat(r[date_key]) for r in records]
        values = [float(r['equity']) for r in records]
        ax.plot(dates, values, label=label, lw=1.4)
    ax.set_title(window)
    ax.set_ylabel('Equity (USDT, log scale)')
    ax.set_yscale('log')
    ax.grid(alpha=.2)
    ax.tick_params(axis='x', rotation=25)
axes[0, 0].legend(fontsize=8)
fig.suptitle('Independent trend: completed-close ATR exits | initial 1,000 USDT | 0.1% fees per side')
fig.tight_layout()
fig.savefig(root / 'equity_comparison.png', dpi=160)
plt.close(fig)
