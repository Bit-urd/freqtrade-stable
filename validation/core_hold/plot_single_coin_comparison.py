"""Standalone grouped-bar comparison for ten independently funded coin groups."""
import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent/'single_coin_comparison'
plan=json.loads((ROOT/'plan.json').read_text());pairs=plan['pairs']
rows=list(csv.DictReader((ROOT/'summary.csv').open()));lookup={(r['pair'],r['strategy']):r for r in rows}
names={'BtcTrendPhasedStrategy':('Phased v1','#3976b5'),'BtcTrendFastExitStrategy':('Fast exit','#df7f32'),'Ma200BtcRegimeFullCyclePortfolioStrategy':('Portfolio','#389c62'),'BuyAndHold':('Buy & hold','#777777')}
x=np.arange(len(pairs));width=.2
fig,axes=plt.subplots(2,1,figsize=(15,9),sharex=True,layout='constrained')
for i,(n,(label,color)) in enumerate(names.items()):
    for ax,field in zip(axes,['return_pct','wallet_drawdown_pct']):
        vs=[float(lookup[p,n][field]) for p in pairs]
        bars=ax.bar(x+(i-1.5)*width,vs,width,label=label,color=color)
        ax.bar_label(bars,labels=[f'{v:.0f}' for v in vs],fontsize=7,padding=2)
axes[0].set_ylabel('Cumulative return (%)');axes[0].set_ylim(top=1850)
axes[1].set_ylabel('Maximum drawdown (%)');axes[1].set_ylim(0,100)
axes[1].set_xticks(x,[p.split('/')[0] for p in pairs]);axes[1].set_xlabel('Each coin: separate 1,000 USDT wallet; one slot; BTC signal retained')
for ax in axes:ax.legend(ncol=4,loc='upper right');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.suptitle('Ten single-coin groups: 2022-11-21 to 2025-10-07\nDaily-close equity; spot; fee 0.1% per side; frozen strategy parameters')
fig.savefig(ROOT/'comparison.png',dpi=160);fig.savefig(ROOT/'comparison.svg');plt.close(fig)
print(ROOT/'comparison.png')
