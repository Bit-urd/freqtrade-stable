"""Render standalone figures for frozen monthly-start comparisons."""
import csv
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT=Path(__file__).resolve().parent/'start_checks'
rows=list(csv.DictReader((ROOT/'summary.csv').open()))
NAMES={'BtcTrendPhasedStrategy':('Phased v1','#3976b5'),'BtcTrendFastExitStrategy':('Fast exit','#df7f32'),'Ma200BtcRegimeFullCyclePortfolioStrategy':('Portfolio','#389c62'),'BuyAndHold':('Buy & hold','#777777')}
for cohort,title in [('rolling_12_month','Monthly starts, fixed 12-month holding period'),('common_end','Quarterly starts, common end: 2026-10-05')]:
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True,layout='constrained')
    for name,(label,color) in NAMES.items():
        rs=sorted([r for r in rows if r['strategy']==name and r['cohort']==cohort],key=lambda r:r['start'])
        if not rs:continue
        dates=[datetime.fromisoformat(r['start']) for r in rs]
        axes[0].plot(dates,[float(r['return_pct']) for r in rs],label=label,color=color,linewidth=1.8,marker='o',markersize=3)
        axes[1].plot(dates,[float(r['wallet_drawdown_pct']) for r in rs],label=label,color=color,linewidth=1.8,marker='o',markersize=3)
    axes[0].set_yscale('symlog',linthresh=100)
    axes[0].set_ylabel('Return (%) [symlog scale]')
    axes[1].set_ylabel('Maximum drawdown (%)')
    axes[1].set_ylim(bottom=0)
    axes[0].axhline(0,color='black',linewidth=.6)
    for ax in axes:ax.grid(alpha=.2);ax.legend(ncol=4,loc='upper right')
    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    axes[1].set_xlabel('Start date (each starts independently with 1,000 USDT)')
    fig.suptitle(title+'\nBTC / SOL / ETH; daily-close equity; fee 0.1% per side')
    fig.savefig(ROOT/(cohort+'.png'),dpi=160)
    fig.savefig(ROOT/(cohort+'.svg'))
    plt.close(fig)
print(ROOT)
