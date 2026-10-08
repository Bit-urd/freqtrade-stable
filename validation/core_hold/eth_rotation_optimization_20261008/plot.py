"""Standalone fixed-window equity chart, reading CSV without pandas."""
import csv
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
names = [('BtcCoinGuardCycleRiskStrategy', 'Original CycleRisk'),
         ('EthRotationCycleRiskStrategy', 'ETH rotation'),
         ('EthBreadthRotationCycleRiskStrategy', 'ETH rotation + breadth'),
         ('Ma200BtcRegimeFullCyclePortfolioStrategy', 'Original MA200'),
         ('BuyAndHold', 'Buy and hold')]
fig, axes = plt.subplots(2, 2, figsize=(14, 9))
for ax, label in zip(axes.flat, ['ZEC_recent', 'SUI_since_maturity', 'ADA_bear_2022', 'DOGE_bear_2022']):
    for name, legend in names:
        records = list(csv.DictReader((root / 'results' / label / ('equity_' + name + '.csv')).open()))
        key = list(records[0])[0]
        dates = [datetime.fromisoformat(r[key]) for r in records]
        equity = [float(r['equity']) for r in records]
        ax.plot(dates, equity, label=legend, lw=1.5)
    ax.set_title(label)
    ax.set_ylabel('Equity (USDT, log scale)')
    ax.set_yscale('log')
    ax.grid(alpha=.2)
    ax.tick_params(axis='x', rotation=25)
axes[0, 0].legend(fontsize=8)
fig.suptitle('ETH/BTC rotation channels | initial 1,000 USDT | fees 0.1% per side')
fig.tight_layout()
fig.savefig(root / 'equity_comparison.png', dpi=160)
plt.close(fig)
