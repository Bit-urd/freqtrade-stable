"""Static shareable equity comparison; read CSVs using the standard library."""
import csv
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
names = [('BtcCoinGuardCycleRiskStrategy', 'Original: BTC 1-day exit'), ('BtcTwoDayExitCycleRiskStrategy', 'BTC 2-day exit'), ('BuyAndHold', 'Buy and hold')]
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
for ax, window in zip(axes.flat, ['core3_full_cycle', 'core3_bear_2022', 'broad7_full_cycle', 'broad8_since_maturity']):
    for name, label in names:
        records = list(csv.DictReader((root / 'results' / window / ('equity_' + name + '.csv')).open()))
        key = list(records[0])[0]
        dates = [datetime.fromisoformat(r[key]) for r in records]
        equity = [float(r['equity']) for r in records]
        ax.plot(dates, equity, label=label, lw=1.5)
    ax.set_title(window)
    ax.set_ylabel('Equity (USDT, log scale)')
    ax.set_yscale('log')
    ax.grid(alpha=.2)
    ax.tick_params(axis='x', rotation=25)
axes[0, 0].legend(fontsize=8)
fig.suptitle('BTC exit confirmation: 1 day vs 2 days | initial 1,000 USDT | fees 0.1% per side')
fig.tight_layout()
fig.savefig(root / 'equity_comparison.png', dpi=160)
plt.close(fig)
