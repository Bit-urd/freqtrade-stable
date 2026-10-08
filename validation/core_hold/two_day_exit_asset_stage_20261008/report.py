import csv,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent;parent=root.parent
old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';hold='BuyAndHold'
windows=json.loads((root/'windows.json').read_text());rows=list(csv.DictReader((root/'summary.csv').open()));idx={(x['window'],x['strategy']):x for x in rows};assert len(rows)==len(windows)*3
verification=json.loads((root/'audit_verification.json').read_text());assert verification['passed'];rules=json.loads((root/'verification.json').read_text());assert rules['passed']
comparisons=[]
for w in windows:
 a=idx[w['label'],old];b=idx[w['label'],new];h=idx[w['label'],hold]
 comparisons.append(dict(window=w['label'],asset=w['universe'],start=w['start'],end=w['end'],return_change_pp=float(b['return_pct'])-float(a['return_pct']),drawdown_change_pp=float(b['wallet_drawdown_pct'])-float(a['wallet_drawdown_pct']),wealth_ratio=float(b['ending_equity'])/float(a['ending_equity']),return_vs_hold_pp=float(b['return_pct'])-float(h['return_pct']),drawdown_vs_hold_pp=float(b['wallet_drawdown_pct'])-float(h['wallet_drawdown_pct']),fill_change=int(b['normal_fills'])-int(a['normal_fills']),cash_change_pp=float(b['mean_idle_cash_pct'])-float(a['mean_idle_cash_pct'])))
aggregate=[]
for coin in ['all',*dict.fromkeys(x['asset'] for x in comparisons)]:
 group=[x for x in comparisons if coin=='all' or x['asset']==coin]
 aggregate.append(dict(asset=coin,windows=len(group),return_better=sum(x['return_change_pp']>1e-6 for x in group),return_worse=sum(x['return_change_pp']<-1e-6 for x in group),return_same=sum(abs(x['return_change_pp'])<=1e-6 for x in group),drawdown_better=sum(x['drawdown_change_pp']<-1e-6 for x in group),jointly_better=sum(x['return_change_pp']>1e-6 and x['drawdown_change_pp']<-1e-6 for x in group),return_above_hold=sum(x['return_vs_hold_pp']>1e-6 for x in group),drawdown_below_hold=sum(x['drawdown_vs_hold_pp']<-1e-6 for x in group),jointly_above_hold=sum(x['return_vs_hold_pp']>1e-6 and x['drawdown_vs_hold_pp']<-1e-6 for x in group),median_wealth_ratio=statistics.median(x['wealth_ratio'] for x in group)))
for file,data in [('comparison.csv',comparisons),('aggregate.csv',aggregate)]:
 with (root/file).open('w') as f:writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
labels={old:'原版',new:'BTC 两天退出',hold:'持有'}
lines=['# BTC 两天退出：逐标的、逐阶段复核','', '唯一改动为 BTC 弱势退出连续确认从 1 天改为 2 天。个币弱势两天退出、入场、弱 BTC 14 天冷却、独立分币预算、账户回撤档位和恢复全部不变。各单币独立 1000 USDT、一仓，保留 BTC 作为行情过滤；每侧费用 0.1%、无滑点、终点 2026-10-06，终点人工强平不计入日终盯市，但单独核对现金余额。','',f'8 标的、{len(windows)} 单币阶段窗口，以及复核前轮 19 个共享账户组合窗口。各独立窗口重置资金和风控状态；连续账户年度切分另表。年度阶段按日期定义，不假定所有币同时处于牛熊。','', '## 单币汇总','', '窗口重叠，数量仅作描述；收益胜出次数不代表统计显著性。','', '| 标的 | 案例 | 相对原版收益提高/下降/相同 | 回撤降低 | 同时改善 | 收益超过持有 | 回撤低于持有 | 收益、回撤均优于持有 |','|---|---:|---:|---:|---:|---:|---:|---:|']
for a in aggregate:lines.append(f"| {a['asset']} | {a['windows']} | {a['return_better']}/{a['return_worse']}/{a['return_same']} | {a['drawdown_better']} | {a['jointly_better']} | {a['return_above_hold']} | {a['drawdown_below_hold']} | {a['jointly_above_hold']} |")
lines+=['','## 所有标的与阶段','', '每格为累计收益 / 最大回撤；日期及平均现金、成交、费用见 summary.csv。','', '| 标的 | 阶段 | 起点 | 原版 | BTC 两天退出 | 持有 |','|---|---|---|---:|---:|---:|']
for w in windows:
 cells=[f"{float(idx[w['label'],n]['return_pct']):+.2f}% / {float(idx[w['label'],n]['wallet_drawdown_pct']):.2f}%" for n in [old,new,hold]]
 lines.append('| '+w['universe']+' | '+w['label'].split('_',1)[1]+' | '+w['start']+' | '+' | '.join(cells)+' |')
lines+=['','SUI 2022 未上市，不构造零收益或假行情。历史 since_maturity/early_bull 标签从 2023-07-05 开始，实际仅满足 60 天暖机；策略自身 MA150 从 2023-09-29 才形成，因此首次满足其他入场条件前仍持现金。持有按窗口起点买入，不等 MA150；另列 2023-10-01 起点排除暖机等待的对照。AVAX 2021 年初也尚未形成 MA150；原版和两天版等待规则一致。不同起点与币池不直接合并为一条实盘收益。','', '## 组合复核与各币贡献','']
portrows=list(csv.DictReader((parent/'btc_exit_confirmation_20261008/summary.csv').open()));portidx={(x['window'],x['strategy']):x for x in portrows}
lines+=['每格为收益 / 最大回撤。','', '| 组合窗口 | 原版 | BTC 两天退出 | 等额持有 |','|---|---:|---:|---:|']
for w in json.loads((parent/'btc_exit_confirmation_20261008/windows.json').read_text()):
 cells=[f"{float(portidx[w['label'],n]['return_pct']):+.2f}% / {float(portidx[w['label'],n]['wallet_drawdown_pct']):.2f}%" for n in [old,new,hold]]
 lines.append('| '+w['label']+' | '+' | '.join(cells)+' |')
attr=list(csv.DictReader((root/'profit_attribution.csv').open()));atidx={(x['scope'],x['window'],x['strategy'],x['pair']):x for x in attr}
lines+=['','各币贡献包含买卖现金流、全部部分调仓、费用及尾部盯市。各币贡献加总等于账户利润；差异同时包含资金复利和共享账户风险路径，不是孤立规则的因果贡献。','', '| 组合窗口 | 标的 | 原版利润贡献 | 两天版利润贡献 | 差额（USDT） |','|---|---|---:|---:|---:|']
portdiff=[]
for w in json.loads((parent/'btc_exit_confirmation_20261008/windows.json').read_text()):
 for p in w['pairs']:
  a=float(atidx['portfolio',w['label'],old,p]['profit_abs']);b=float(atidx['portfolio',w['label'],new,p]['profit_abs'])
  portdiff.append(dict(window=w['label'],pair=p,original_profit_abs=a,two_day_profit_abs=b,profit_change_abs=b-a))
  if w['label'] in ['core3_full_cycle','core3_continuous_2023_latest','broad7_full_cycle','broad8_since_maturity']:lines.append(f"| {w['label']} | {p} | {a:+.2f} | {b:+.2f} | {b-a:+.2f} |")
with (root/'portfolio_profit_change.csv').open('w') as f:writer=csv.DictWriter(f,fieldnames=list(portdiff[0]));writer.writeheader();writer.writerows(portdiff)
lines+=['','## 连续账户按年切分','', '从已有连续账户计算，不年初重置本金、持仓或风控；年内回撤从年初权益开始。','', '| 标的/窗口 | 年份 | 原版 | BTC 两天退出 | 持有 |','|---|---:|---:|---:|---:|']
annual=list(csv.DictReader((root/'continuous_annual.csv').open()));anidx={(x['scope'],x['window'],x['year'],x['strategy']):x for x in annual}
selected=[w['label'] for w in windows if w['label'].endswith('continuous_2023_latest') or w['label']=='SUI_after_ma150_maturity']
for label in selected:
 for year in dict.fromkeys(x['year'] for x in annual if x['scope']=='single' and x['window']==label):
  cells=[]
  for n in [old,new,hold]:
   x=anidx['single',label,year,n];cells.append(f"{float(x['return_pct']):+.2f}% / {float(x['drawdown_pct']):.2f}%")
  lines.append('| '+label+' | '+year+' | '+' | '.join(cells)+' |')
lines+=['','## 核验与边界','', f"{rules['count']} 项规则/历史截断检查通过；{verification['curve_checks']} 条日权益曲线、{verification['summary_metric_checks']} 项收益/回撤/现金指标、{verification['actual_btc_exit_checks']} 次实际 BTC 原因退出及 {verification['daily_risk_equity_checks']} 条风险权益核对通过。持仓权益最大误差 {verification['max_equity_error']:.10g} USDT，成交现金余额最大误差 {verification['max_cash_error']:.10g} USDT。冻结数据、研究源码及正式策略哈希一致。",'', '无 5pp 回撤扩大硬门槛，综合评价收益、回撤和阶段取舍。全部为已查看、重叠的历史区间，币池有存续选择偏差，无严格样本外证据；不保证实盘表现。生产策略与服务未切换。']
(root/'REPORT.md').write_text('\n'.join(lines)+'\n');plan=json.loads((root/'plan.json').read_text());plan['status']='complete';plan['new_backtests']=74;plan['reused_single_baselines']=38;plan['verified_portfolio_windows']=19;(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps(aggregate,indent=2))
