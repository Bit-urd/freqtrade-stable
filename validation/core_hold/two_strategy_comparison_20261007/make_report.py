from pathlib import Path
import json, csv, hashlib
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('/research/two_strategy_comparison_20261007')
rows=list(csv.DictReader((root/'summary.csv').open()))
assert len(rows)==15
names={'BtcCoinGuardCycleRiskStrategy':'CycleRisk','Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio','BuyAndHold':'三币等权持有'}
btc=pd.read_feather('/research/production_comparison_2023_latest/data/BTC_USDT-1d.feather').set_index('date')
text=['# 两个当前策略的静态分析与回测对比','', 'BTC/SOL/ETH；现货；1000 USDT；3槽位；每侧手续费0.1%；无额外滑点。每个窗口独立重置账户，窗口内部连续运行。数据采用既有冻结快照，截至2026-10-06完整UTC日线。本次未重新联网下载。收益、回撤均按每日收盘权益，包含浮亏，排除终点人为强平。持有在首日开盘等权买入且不再平衡。', '', '| 区间 | CycleRisk 收益 / 回撤 | Portfolio 收益 / 回撤 | 三币持有 收益 / 回撤 | BTC持有 收益 / 回撤 |','|---|---:|---:|---:|---:|']
btcrows=[]
for window in json.loads((root/'windows.json').read_text()):
 r=[r for r in rows if r['window']==window['label']]
 assert len(r)==3
 start=pd.Timestamp(window['start'],tz='UTC');end=pd.Timestamp(window['end'],tz='UTC');h=btc.loc[start:end]
 equity=1000/(1.001)/float(h.open.iloc[0])*h.close
 ret=(equity.iloc[-1]/1000-1)*100;dd=(1-equity/equity.cummax().clip(lower=1000)).max()*100
 btcrows.append(dict(window=window['label'],return_pct=ret,wallet_drawdown_pct=dd))
 cells=[f"{float(v['return_pct']):+.2f}% / {float(v['wallet_drawdown_pct']):.2f}%" for v in r]
 text.append('| '+window['start']+'～'+window['end']+' | '+' | '.join(cells)+f' | {ret:+.2f}% / {dd:.2f}% |')
 for v in r:
  if v['strategy']!='BuyAndHold': assert abs(float(v['ledger_error']))<.05
with (root/'btc_hold.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(btcrows[0]));w.writeheader();w.writerows(btcrows)
text+=['', (root/'analysis_notes.md').read_text(), '## 结论', '', 'CycleRisk侧重趋势参与、快速退出和账户风险仓位管理；Portfolio侧重牛市趋势加熊市积累筹码。2022纯熊市CycleRisk明显少亏，但长周期最大回撤仍超过60%，35%风控阈值不是最大亏损上限。2023以来CycleRisk收益更高、Portfolio回撤更浅；近期区间可能改变收益排序。不能宣称一个策略在全部市场环境中占优。', '', '2021起点结果受SOL早期上涨和各币独立复利预算强烈影响。固定BTC/ETH/SOL存在事后选币与幸存者偏差；已有历史被多轮研究，不能视为严格样本外。未加入流动性、滑点、税费和日内执行细节。未运行专门前视偏差检查。本次不调参、不修改运行服务。', '', '原生成交现金账本与引擎期末余额逐次核对误差小于0.05 USDT；CycleRisk风控使用的前日权益逐日核对；每个策略的起止日期一致；保存代码哈希、原生成交、风险轨迹和逐日权益。']
(root/'REPORT.md').write_text('\n'.join(text)+'\n')
fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True)
for name in names:
 curve=pd.read_csv(root/'results/full_cycle'/('equity_'+name+'.csv'),index_col=0,parse_dates=True)
 axes[0].plot(curve.index,curve.equity/1000,label=names[name] if name!='BuyAndHold' else 'Equal-weight hold')
 axes[1].plot(curve.index,(curve.equity/curve.equity.cummax().clip(lower=1000)-1)*100,label=names[name] if name!='BuyAndHold' else 'Equal-weight hold')
axes[0].set_yscale('log');axes[0].set_ylabel('Equity / initial (log)');axes[1].set_ylabel('Drawdown %')
for ax in axes: ax.grid(alpha=.25);ax.legend()
fig.tight_layout();fig.savefig(root/'equity_comparison.png',dpi=150)
print((root/'REPORT.md').read_text())
