import csv,datetime,sys
from pathlib import Path
sys.path.insert(0,'/tmp/single-coin-plot-deps-20261007')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).parent
names={'BtcCoinGuardCycleRiskStrategy':'Original CycleRisk','IndependentHoldCycleRiskStrategy':'Hold exception','IndependentProbeCycleRiskStrategy':'25% probe','IndependentFastGuardCycleRiskStrategy':'Hold + EMA10 guard','Ma200BtcRegimeFullCyclePortfolioStrategy':'Original Portfolio','BuyAndHold':'Buy and hold'}
fig,axes=plt.subplots(2,2,figsize=(14,10))
for ax,label in zip(axes.flat,['ZEC_recent','SUI_recent','AVAX_recent','PORTFOLIO_continuous_2023_latest']):
 for strategy,name in names.items():
  folder=ROOT/'fast_guard_study' if strategy=='IndependentFastGuardCycleRiskStrategy' else ROOT
  raw=list(csv.DictReader((folder/'results'/label/('equity_'+strategy+'.csv')).open()))
  dates=[datetime.datetime.fromisoformat(r['']) for r in raw]
  ax.plot(dates,[float(r['equity'])/1000 for r in raw],label=name,linewidth=1.1)
 ax.set_title(label.replace('_',' ')+' (log equity)');ax.set_yscale('log');ax.set_ylabel('Equity / initial');ax.grid(alpha=.2);ax.legend(fontsize=7)
fig.autofmt_xdate();fig.tight_layout();fig.savefig(ROOT/'equity_comparison.png',dpi=150)
print(ROOT/'equity_comparison.png')
