from pathlib import Path
import csv,datetime,sys
sys.path.insert(0,'/tmp/single-coin-plot-deps-20261007')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).parent
names={'Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio','BtcCoinGuardCycleRiskStrategy':'CycleRisk','BuyAndHold':'Buy and hold'}
colors={'Portfolio':'#e68a00','CycleRisk':'#126bc5','Buy and hold':'#299b48'}
fig,axes=plt.subplots(3,2,figsize=(14,11))
for i,coin in enumerate(['BTC','SUI','ZEC']):
 for j,kind in enumerate(['long','recent']):
  label=coin+('_since_maturity' if coin=='SUI' else '_full_cycle') if kind=='long' else coin+'_recent'
  ax=axes[i,j]
  for strategy,name in names.items():
   data=list(csv.DictReader((root/'results'/label/('equity_'+strategy+'.csv')).open()))
   dates=[datetime.datetime.fromisoformat(r['']) for r in data]
   ax.plot(dates,[float(r['equity'])/1000 for r in data],label=name,color=colors[name],linewidth=1.2)
  ax.set_title(f'{coin}: {dates[0].date()} to {dates[-1].date()}')
  if j==0:ax.set_yscale('log')
  ax.set_ylabel('Equity / initial'+(' (log)' if j==0 else ''));ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.autofmt_xdate();fig.tight_layout();fig.savefig(root/'equity_comparison.png',dpi=150)
print(root/'equity_comparison.png')
