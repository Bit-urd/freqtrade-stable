"""Common fixed-candidate reporting; all measurements come from reconciled runs."""
import csv,json,hashlib,sys
from pathlib import Path
root=Path(sys.argv[1]);plan=json.loads((root/'plan.json').read_text());names=plan['candidates'];original='BtcCoinGuardCycleRiskStrategy';hold='BuyAndHold'
windows=json.loads((root/'windows.json').read_text());rows=list(csv.DictReader((root/'summary.csv').open()));index={(x['window'],x['strategy']):x for x in rows}
assert len(rows)==len(windows)*(2+len(names))
prior={(x['window'],x['strategy']):x for x in csv.DictReader((root.parent/'momentum_selection_20261008/summary.csv').open())}
for w in windows:
 for n in [original,hold]:
  for k in ['return_pct','wallet_drawdown_pct','ending_equity']:
   assert abs(float(index[w['label'],n][k])-float(prior[w['label'],n][k]))<1e-6
assert (root/'strategies/cycle_risk_strategy.py').read_bytes()==(root.parent/'momentum_selection_20261008/strategies/cycle_risk_strategy.py').read_bytes()
audit=json.loads((root.parent/'momentum_selection_20261008/data_audit.json').read_text())
for record in audit['files']:
 assert hashlib.sha256((root.parent/'independent_trend_optimization_20261008/data'/record['file']).read_bytes()).hexdigest()==record['sha256']
(root/'data_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
for filename,digest in json.loads((root/'source_manifest.json').read_text()).items():
 assert hashlib.sha256((root/filename).read_bytes()).hexdigest()==digest
verification=json.loads((root/'verification.json').read_text());assert verification['passed']
comparisons=[];aggregate=[]
for n in names:
 group=[]
 for w in windows:
  a=index[w['label'],original];b=index[w['label'],n]
  x=dict(window=w['label'],candidate=n,return_change_pp=float(b['return_pct'])-float(a['return_pct']),drawdown_change_pp=float(b['wallet_drawdown_pct'])-float(a['wallet_drawdown_pct']),wealth_ratio=float(b['ending_equity'])/float(a['ending_equity']),cash_change_pp=float(b['mean_idle_cash_pct'])-float(a['mean_idle_cash_pct']),fill_change=int(b['normal_fills'])-int(a['normal_fills']))
  comparisons.append(x);group.append(x)
 aggregate.append(dict(candidate=n,windows=len(group),return_better=sum(x['return_change_pp']>1e-6 for x in group),return_worse=sum(x['return_change_pp']<-1e-6 for x in group),return_same=sum(abs(x['return_change_pp'])<=1e-6 for x in group),drawdown_better=sum(x['drawdown_change_pp']<-1e-6 for x in group),jointly_better=sum(x['return_change_pp']>1e-6 and x['drawdown_change_pp']<-1e-6 for x in group)))
for filename,data in [('comparison.csv',comparisons),('aggregate.csv',aggregate)]:
 with (root/filename).open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
labels=[original,*names,hold]
lines=['# '+plan['title'],'',plan['rules'],'','固定组合候选，与两个单项分别比较；仅叠加退出天数和冷却天数。19 个相同窗口、1000 USDT、每侧费用 0.1%、无滑点、2026-10-06 为终点，日终盯市包含未实现盈亏，终点人工平仓费用另计。','', '## 汇总','']
for x in aggregate:lines.append(f"{x['candidate']}：收益改善 {x['return_better']}、退步 {x['return_worse']}、相同 {x['return_same']}；回撤降低 {x['drawdown_better']}、收益及回撤同时改善 {x['jointly_better']}（共 19 个重叠窗口）。")
lines+=['','每格为收益 / 最大回撤 / 平均现金比例。','', '| 窗口 | '+' | '.join(labels)+' |','|---|'+'---:|'*len(labels)]
for w in windows:
 cells=[f"{float(index[w['label'],n]['return_pct']):+.2f}% / {float(index[w['label'],n]['wallet_drawdown_pct']):.2f}% / {float(index[w['label'],n]['mean_idle_cash_pct']):.1f}%" for n in labels]
 lines.append('| '+w['label']+' | '+' | '.join(cells)+' |')
annual=[]
for label in ['core3_continuous_2023_latest','broad7_continuous_2023_latest','broad8_since_maturity']:
 for n in labels:
  curve=list(csv.DictReader((root/'results'/label/('equity_'+n+'.csv')).open()))
  previous=1000.; groups={}
  for record in curve:groups.setdefault(int(record[''][:4]),[]).append(float(record['equity']))
  for year,values in groups.items():
   start=previous;peak=start;dd=0.
   for value in values:peak=max(peak,value);dd=max(dd,1-value/peak)
   previous=values[-1]
   annual.append(dict(window=label,year=year,strategy=n,return_pct=(previous/start-1)*100,drawdown_pct=dd*100))
  assert abs(previous-float(index[label,n]['ending_equity']))<1e-6
with (root/'continuous_annual.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(annual[0]));writer.writeheader();writer.writerows(annual)
lines+=['','## 连续账户年度表现','', '年度收益从前一年度末权益计算，不重置资金、持仓或风控状态；首年从初始 1000 USDT 开始。','', '| 连续窗口 | 年份 | '+' | '.join(labels)+' |','|---|---:|'+'---:|'*len(labels)]
annualindex={(x['window'],x['year'],x['strategy']):x for x in annual}
for label,year in dict.fromkeys((x['window'],x['year']) for x in annual):
 cells=[]
 for n in labels:
  x=annualindex[label,year,n];cells.append(f"{x['return_pct']:+.2f}% / {x['drawdown_pct']:.2f}%")
 lines.append('| '+label+' | '+str(year)+' | '+' | '.join(cells)+' |')
lines+=['','## 验证及限制','',f"规则检查 {verification['count']} 项通过。原版及持有 114 个指标对比复现；每日账户风控权益及成交现金账由回测脚本核对，余额最大误差 {max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error']):.10g} USDT。来源及数据哈希一致。",'','用户要求综合考虑最终结果，无 5 个百分点等固定回撤扩大淘汰线。窗口已查看、存在重叠，币池事后选择；本轮是回溯研究，没有严格样本外证据。候选仅放研究目录，没有生产策略或服务切换。','']
for p in root.glob('*diagnos*.csv'):lines.append('归因文件：`'+p.name+'`，基于原版路径的描述，不是删改规则后的因果收益。')
(root/'REPORT.md').write_text('\n'.join(lines)+'\n');plan['status']='complete';(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
(root/'result_verification.json').write_text(json.dumps(dict(passed=True,windows=19,baseline_metrics=114,rule_checks=verification['count'],unchanged_hashes=True,max_ledger_error=max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error'])),indent=2)+'\n')
print(json.dumps(aggregate,indent=2))
combo='TwoDayExitSevenDayCooldownCycleRiskStrategy'
references=[original,'BtcTwoDayExitCycleRiskStrategy','ShortCooldownCycleRiskStrategy',hold]
relative=[];relative_aggregate=[]
for reference in references:
 group=[]
 for w in windows:
  a=index[w['label'],reference];b=index[w['label'],combo]
  item=dict(window=w['label'],reference=reference,return_change_pp=float(b['return_pct'])-float(a['return_pct']),drawdown_change_pp=float(b['wallet_drawdown_pct'])-float(a['wallet_drawdown_pct']),wealth_ratio=float(b['ending_equity'])/float(a['ending_equity']),normal_fill_change=int(b['normal_fills'])-int(a['normal_fills']))
  group.append(item);relative.append(item)
 relative_aggregate.append(dict(reference=reference,return_better=sum(x['return_change_pp']>1e-6 for x in group),return_worse=sum(x['return_change_pp']<-1e-6 for x in group),return_same=sum(abs(x['return_change_pp'])<=1e-6 for x in group),drawdown_better=sum(x['drawdown_change_pp']<-1e-6 for x in group),jointly_better=sum(x['return_change_pp']>1e-6 and x['drawdown_change_pp']<-1e-6 for x in group)))
for filename,data in [('combo_relative.csv',relative),('combo_relative_aggregate.csv',relative_aggregate)]:
 with (root/filename).open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
text=(root/'REPORT.md').read_text()
extra=['## 组合相对各对照','', '| 对照 | 组合收益提高/下降/相同 | 回撤降低 | 同时改善 |','|---|---:|---:|---:|']
for x in relative_aggregate:extra.append(f"| {x['reference']} | {x['return_better']}/{x['return_worse']}/{x['return_same']} | {x['drawdown_better']} | {x['jointly_better']} |")
extra+=['','叠加后的持仓结束、重新买入、账户回撤档位和各币复利路径都会变化。不能将两个单项的收益增幅直接相加，也不能把重叠窗口胜出数量当独立样本显著性。','']
extra.insert(0,'## 综合判断\n\n组合不是通用升级。相对原版，19 个窗口收益提高 13、下降 6；相对 BTC 两天退出单项，提高 10、下降 9，只有 5 个收益及回撤同时改善；相对七天冷却单项，提高 6、下降 13。三币全周期、熊市、上涨与 2023 至今连续账户均不如两天退出单项，近期及 2026 年存在局部优势。综合收益、回撤和周期取舍，优先保留两天退出单项作为研究方向，组合仅留实验记录，不替换正式版。\n\n')
text=text.replace('## 汇总','\n'.join(extra)+'\n## 汇总',1)
(root/'REPORT.md').write_text(text)
print('Combo vs each reference:',json.dumps(relative_aggregate,indent=2))
scoped=[]
for reference in references:
 for universe in dict.fromkeys(w['universe'] for w in windows):
  labels_in_scope={w['label'] for w in windows if w['universe']==universe}
  group=[x for x in relative if x['reference']==reference and x['window'] in labels_in_scope]
  scoped.append(dict(universe=universe,reference=reference,windows=len(group),return_better=sum(x['return_change_pp']>1e-6 for x in group),return_worse=sum(x['return_change_pp']<-1e-6 for x in group),drawdown_better=sum(x['drawdown_change_pp']<-1e-6 for x in group),jointly_better=sum(x['return_change_pp']>1e-6 and x['drawdown_change_pp']<-1e-6 for x in group)))
with (root/'combo_relative_by_universe.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(scoped[0]));writer.writeheader();writer.writerows(scoped)
text=(root/'REPORT.md').read_text()
extra=['## 分币池比较','', '| 币池 | 对照 | 组合收益提高/下降 | 回撤降低 | 同时改善 |','|---|---|---:|---:|---:|']
for x in scoped:extra.append(f"| {x['universe']} ({x['windows']}) | {x['reference']} | {x['return_better']}/{x['return_worse']} | {x['drawdown_better']} | {x['jointly_better']} |")
text+='\n'+'\n'.join(extra)+'\n'
audit=json.loads((root/'actual_entry_verification.json').read_text());position=json.loads((root/'position_verification.json').read_text());assert audit['passed'] and position['passed']
assert hashlib.sha256(Path('/root/freqtrade-stable/user_data/strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==plan['production_sha256']
text+=f"\n实际退出与冷却核验：{audit['two_day_exit_checks']} 次 BTC 两天弱势退出、{audit['weak_btc_entry_checks']} 次弱 BTC 新入场冷却通过。95 条日权益曲线持仓重建核验通过，最大误差 {position['max_equity_error']:.10g} USDT。正式策略哈希未变。\n"
(root/'REPORT.md').write_text(text)
print('By universe:',json.dumps(scoped,indent=2))
