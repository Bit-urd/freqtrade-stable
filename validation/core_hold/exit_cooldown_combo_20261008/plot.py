import csv
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent;parent=root.parent
curves=[('exit_cooldown_combo_20261008','BtcCoinGuardCycleRiskStrategy','Original CycleRisk'),('exit_cooldown_combo_20261008','BtcTwoDayExitCycleRiskStrategy','BTC 2-day exit'),('exit_cooldown_combo_20261008','ShortCooldownCycleRiskStrategy','7-day cooldown'),('exit_cooldown_combo_20261008','TwoDayExitSevenDayCooldownCycleRiskStrategy','BTC 2-day + 7-day cooldown'),('exit_cooldown_combo_20261008','BuyAndHold','Buy and hold')]
fig,axes=plt.subplots(2,2,figsize=(14,9))
for ax,label in zip(axes.flat,['core3_full_cycle','core3_bear_2022','core3_continuous_2023_latest','broad8_since_maturity']):
 for folder,name,title in curves:
  rows=list(csv.DictReader((parent/folder/'results'/label/('equity_'+name+'.csv')).open()))
  ax.plot([datetime.fromisoformat(r['']) for r in rows],[float(r['equity']) for r in rows],label=title,lw=1.5)
 ax.set_title(label);ax.set_yscale('log');ax.set_ylabel('Equity (USDT, log scale)');ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=25)
axes[0,0].legend(fontsize=8)
fig.suptitle('CycleRisk: exit and cooldown interaction | initial 1,000 USDT | fees 0.1% per side')
fig.tight_layout();fig.savefig(root/'equity_comparison.png',dpi=160);plt.close(fig)
