import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parent
rows=list(csv.DictReader((root/'all_comparisons.csv').open()));idx={r['window']:r for r in rows};colors=['#2878b5','#e68121','#777777'];prefixes=['original','two_day','hold'];labels=['Original','BTC two-day exit','Buy and hold']
plt.rcParams.update({'font.size':10,'figure.facecolor':'white'})
cs=[r for r in rows if r['scope'].startswith('continuous_pool')]
fig,axes=plt.subplots(1,2,figsize=(18,11));y=np.arange(len(cs));height=.23
for k,(p,color,label) in enumerate(zip(prefixes,colors,labels)):
 wealth=np.array([float(r[p+'_ending_equity'])/1000 for r in cs]);dd=np.array([float(r[p+'_wallet_drawdown_pct']) for r in cs]);offset=(k-1)*height
 axes[0].barh(y+offset,wealth,height=height,color=color,label=label);axes[1].barh(y+offset,dd,height=height,color=color,label=label)
 for i,v in enumerate(wealth):axes[0].text(v*1.045,y[i]+offset,f'{(v-1)*100:+.1f}%',va='center',fontsize=8)
 for i,v in enumerate(dd):axes[1].text(v+.7,y[i]+offset,f'{v:.1f}',va='center',fontsize=8)
for ax in axes:
 ax.set_yticks(y,[r['window'] for r in cs]);ax.invert_yaxis();ax.grid(axis='x',alpha=.18);ax.set_axisbelow(True)
axes[0].set_xscale('log');axes[0].set_xlim(.25,max(float(r[p+'_ending_equity'])/1000 for r in cs for p in prefixes)*2);axes[0].axvline(1,color='black',lw=.8);axes[0].set_title('Ending wealth / initial capital (log axis; labels = return %)');axes[0].set_xlabel('Initial capital = 1')
axes[1].set_xlim(0,100);axes[1].set_title('Daily wallet drawdown (%)');axes[1].set_xlabel('Drawdown %');axes[1].legend(loc='lower right')
fig.suptitle('Requested asset pool | Continuous portfolio results | Spot, 1,000 USDT, 0.1% fees',fontsize=16)
fig.text(.5,.015,'Legacy9 excludes ARB/PUMP/HYPE. Main10 adds ARB. Mature11 adds PUMP. Requested12 reserves HYPE budget as cash.\nOverlapping windows are shown separately; these returns must not be compounded across rows.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.06,1,.95));fig.savefig(root/'portfolio_return_drawdown.png',dpi=160);plt.close(fig)
selected=['Legacy9_full_cycle','Main10_full_cycle','Main10_year_2025','Main10_year_2026','Main10_recent','Main10_mature11_control','Mature11_full_cycle','Requested12_mature11_cash']
fig,axes=plt.subplots(4,2,figsize=(17,15))
for ax,window in zip(axes.flat,selected):
 c=idx[window]
 for n,color,label in zip(['BtcCoinGuardCycleRiskStrategy','BtcTwoDayExitCycleRiskStrategy','BuyAndHold'],colors,labels):
  with (root/'results'/window/('equity_'+n+'.csv')).open() as f:data=list(csv.DictReader(f))
  dates=np.array([r['date'] if 'date' in r else next(iter(r.values())) for r in data],dtype='datetime64[ns]');values=np.array([float(r['equity'])/1000 for r in data]);ax.plot(dates,values,color=color,lw=1.25,label=label)
 ax.set_yscale('log');ax.set_title(window+'\n'+c['start']+' to '+c['end']);ax.set_ylabel('Wealth / initial (log)');ax.axhline(1,color='#999999',lw=.7);ax.grid(alpha=.2);ax.tick_params(axis='x',rotation=15)
axes.flat[0].legend(fontsize=9)
fig.suptitle('Continuous equity | Original vs BTC two-day exit vs holding',fontsize=19)
fig.text(.5,.01,'Each panel starts with 1,000 USDT. Requested12 includes 11 eligible assets plus the reserved HYPE cash budget.\nHYPE has only 13 daily spot candles, so its strategy performance is unavailable.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.045,1,.96));fig.savefig(root/'continuous_equity.png',dpi=150);plt.close(fig)
print('Saved portfolio bars and 8 continuous curves')
