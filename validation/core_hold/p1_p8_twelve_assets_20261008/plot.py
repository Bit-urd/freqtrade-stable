import csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
root=Path(__file__).resolve().parent
assets=json.loads((root/'plan.json').read_text())['assets'];phases=['P'+str(i) for i in range(1,9)]
rows=list(csv.DictReader((root/'comparison_matrix.csv').open()));idx={(r['asset'],r['phase']):r for r in rows}
plt.rcParams.update({'font.size':10,'figure.facecolor':'white'})
fig,axes=plt.subplots(1,2,figsize=(17,9))
for ax,key,title,limit in [(axes[0],'relative_ending_wealth_change_pct','Ending wealth: two-day vs original (%)',60),(axes[1],'drawdown_change_pp','Drawdown change: two-day minus original (pp)',20)]:
 values=np.full((12,8),np.nan)
 for i,a in enumerate(assets):
  for j,p in enumerate(phases):
   r=idx[a,p]
   if r[key]!='':values[i,j]=float(r[key])
 cmap=plt.get_cmap('RdYlGn' if key.startswith('relative') else 'RdYlGn_r').copy();cmap.set_bad('#eeeeee')
 im=ax.imshow(values,cmap=cmap,norm=TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit),aspect='auto')
 ax.set_xticks(range(8),phases);ax.set_yticks(range(12),assets);ax.set_title(title,pad=14)
 for i,a in enumerate(assets):
  for j,p in enumerate(phases):
   r=idx[a,p];v=values[i,j]
   marker='*' if r['status']=='partial' or r['ma150_ready_at_start']=='False' else ''
   label='N/A' if np.isnan(v) else f'{v:+.1f}{marker}'
   ax.text(j,i,label,ha='center',va='center',fontsize=9,color='black')
 fig.colorbar(im,ax=ax,shrink=.7,extend='both')
fig.suptitle('P1-P8 | 12 individual assets | BTC exit confirmation only',fontsize=18,y=.99)
fig.text(.5,.025,'Green = improvement; gray = unavailable. * = partial interval or MA150 not ready. Color saturation is capped; labels show actual values.\n1,000 USDT per case | 0.1% fee each side | daily close equity | independent stage starts',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.08,1,.95));fig.savefig(root/'exit_comparison_heatmap.png',dpi=170);plt.close(fig)
# Same data for all three methods, showing returns and true wallet DD.
fig,axes=plt.subplots(2,3,figsize=(20,13))
for col,(prefix,label) in enumerate([('original','Original'),('two_day','BTC two-day exit'),('hold','Buy and hold')]):
 for row,(key,title,limit) in enumerate([('return_pct','Return (%)',200),('wallet_drawdown_pct','Wallet drawdown (%)',100)]):
  vals=np.full((12,8),np.nan)
  for i,a in enumerate(assets):
   for j,p in enumerate(phases):
    r=idx[a,p];v=r[prefix+'_'+key]
    if v!='':vals[i,j]=float(v)
  ax=axes[row,col];cmap=plt.get_cmap('RdYlGn' if row==0 else 'RdYlGn_r').copy();cmap.set_bad('#eeeeee')
  im=ax.imshow(vals,cmap=cmap,norm=TwoSlopeNorm(vmin=-100,vcenter=0,vmax=limit) if row==0 else matplotlib.colors.Normalize(0,100),aspect='auto')
  ax.set_title(label+' | '+title);ax.set_xticks(range(8),phases);ax.set_yticks(range(12),assets)
  for i,a in enumerate(assets):
   for j,p in enumerate(phases):
    v=vals[i,j];r=idx[a,p];marker='*' if r['status']=='partial' or r['ma150_ready_at_start']=='False' else ''
    ax.text(j,i,'N/A' if np.isnan(v) else f'{v:.1f}{marker}',ha='center',va='center',fontsize=8)
  fig.colorbar(im,ax=ax,shrink=.65,extend='max' if row==0 else 'neither')
fig.suptitle('Same effective intervals | Returns AND drawdowns | P1-P8 x 12 assets',fontsize=19)
fig.text(.5,.015,'* = partial interval or MA150 not ready. N/A = no usable exchange history. Return color cap +200%; labels retain full numbers.\nEach stage starts from cash independently. P6 and P7 overlap; do not compound stage returns.',ha='center',fontsize=11)
fig.tight_layout(rect=(0,.055,1,.95));fig.savefig(root/'three_way_return_drawdown.png',dpi=160);plt.close(fig)
print('Saved two heatmaps')
