import csv,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent;parent=root.parent
old='BtcCoinGuardCycleRiskStrategy';hold='BuyAndHold'
variants=[('btc_exit_confirmation_20261008','BtcTwoDayExitCycleRiskStrategy','BTC 两天退出'),('recovery_speed_20261008','FasterRecoveryCycleRiskStrategy','提前恢复仓位'),('short_cooldown_20261008','ShortCooldownCycleRiskStrategy','冷却缩至七天'),('limited_shared_cash_20261008','LimitedSharedCashCycleRiskStrategy','有限共享现金')]
windows=json.loads((parent/variants[0][0]/'windows.json').read_text());rows=[];index={};aggregate=[]
for folder,name,label in variants:
 data=list(csv.DictReader((parent/folder/'summary.csv').open()))
 for r in data:
  if r['strategy'] in [old,hold] and (r['window'],r['strategy']) in index:continue
  rows.append(r);index[r['window'],r['strategy']]=r
 group=[]
 for w in windows:
  a=index[w['label'],old];b=index[w['label'],name]
  group.append((float(b['return_pct'])-float(a['return_pct']),float(b['wallet_drawdown_pct'])-float(a['wallet_drawdown_pct'])))
 aggregate.append(dict(candidate=label,strategy=name,return_better=sum(a>1e-6 for a,b in group),return_worse=sum(a<-1e-6 for a,b in group),return_same=sum(abs(a)<=1e-6 for a,b in group),drawdown_better=sum(b<-1e-6 for a,b in group),jointly_better=sum(a>1e-6 and b<-1e-6 for a,b in group)))
assert len(rows)==114
for filename,data in [('summary.csv',rows),('aggregate.csv',aggregate)]:
 with (root/filename).open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
lines=['# CycleRisk 四项单变量顺序验证','', '四项已依次完成。90 次新原生回测：第 1 项为 19 次候选和 14 次原版重跑，另复用 5 个已核验原版窗口；后三项各 19 次候选，复用相同冻结原版及持有。最终去重后 19 个窗口 × 六组，共 114 行结果。所有候选独立从原版开始，没有叠加。','', '统一初始资金 1000 USDT、每侧费用 0.1%、无滑点、日终盯市包含浮亏、截至 2026-10-06。三币 BTC/SOL/ETH、七币 BTC/ETH/SOL/ADA/DOGE/AVAX/ZEC、八币增加 SUI（成熟后）；各窗口独立开户，连续账户年度拆分另见各报告。','', '## 综合判断','', 'BTC 两天退出是本轮最值得保留的长周期候选：三币与七币全周期、两个 2023 至今连续账户的收益提高且回撤下降，但 2022 熊市更差，2023—2024 上涨阶段收益略降。不能称作所有周期更优。','', '七天冷却在近期反弹及宽币池连续窗口有研究价值，收益和回撤同时改善的窗口较多；三币全周期收益明显下降，2022 熊市更差，且交易更频繁。当前仅保留对照候选。','', '提前恢复阈值影响有限，部分窗口不变；本轮固定设置不列优先。有限共享现金能提高两个 2023—2024 上涨窗口收益，但长周期和部分近期窗口明显退步，暂不列通用优先方案。以上判断均综合收益和风险，不使用已由用户取消的 5pp 回撤门槛。','', '正式 CycleRisk 与生产服务保持原样；未测试候选组合，未据这些已看过的历史升级实盘。','', '## 19 窗口汇总','', '| 改动 | 收益提高/下降/相同 | 回撤降低 | 收益和回撤同时改善 |','|---|---:|---:|---:|']
for a in aggregate:lines.append(f"| {a['candidate']} | {a['return_better']}/{a['return_worse']}/{a['return_same']} | {a['drawdown_better']} | {a['jointly_better']} |")
labels=[(old,'原版'),*((name,label) for folder,name,label in variants),(hold,'持有')]
lines+=['','## 全部周期','', '每格为累计收益 / 最大回撤，百分比。收益极大时应结合期末资金比理解；差额包含分币复利和账户风控路径影响。','', '| 窗口 | '+' | '.join(label for name,label in labels)+' |','|---|'+'---:|'*len(labels)]
for w in windows:
 cells=[f"{float(index[w['label'],n]['return_pct']):+.2f}% / {float(index[w['label'],n]['wallet_drawdown_pct']):.2f}%" for n,l in labels]
 lines.append('| '+w['label']+' | '+' | '.join(cells)+' |')
lines+=['','## 具体规则与实验报告','']
for folder,name,label in variants:lines.append(f'- [{label}](../{folder}/REPORT.md)：规则、完整结果、连续年度收益、事件/资金归因和核验文件。')
lines+=['','有限共享资金的上限是相对该笔原预算，不是固定账户权益占比上限。既有盈利币种自身复利仍可能形成较高集中度。预留预算仅保护当前状态，未来才符合条件的币可能仍受资金约束；不能把现金下降当成无代价改善。','']
lines+=['## 实际持仓集中度','', '下表为实际日终最大单币占权益比例；持有也会随币价变化而集中。候选并未设绝对权益占比上限。','', '| 窗口 | 原版 | BTC 两天退出 | 提前恢复 | 七天冷却 | 有限共享 | 持有 |','|---|---:|---:|---:|---:|---:|---:|']
sets=[(variants[0][0],old),*((folder,name) for folder,name,label in variants),(variants[0][0],hold)]
for label in ['core3_full_cycle','core3_continuous_2023_latest','broad8_since_maturity']:
 cells=[]
 for folder,name in sets:
  record=next(x for x in csv.DictReader((parent/folder/'position_audit.csv').open()) if x['window']==label and x['strategy']==name)
  cells.append(f"{float(record['max_single_coin_weight_pct']):.1f}%")
 lines.append('| '+label+' | '+' | '.join(cells)+' |')
lines+=['','## 验证与研究限制','']
position=json.loads((parent/'optimization_position_verification.json').read_text());assert position['passed']
rulechecks=sum(json.loads((parent/folder/'verification.json').read_text())['count'] for folder,name,label in variants)
requests=json.loads((parent/variants[3][0]/'actual_budget_verification.json').read_text());assert requests['passed']
cooldown=json.loads((parent/variants[2][0]/'actual_entry_verification.json').read_text());assert cooldown['passed']
exitchecks=json.loads((parent/variants[0][0]/'result_verification.json').read_text());assert exitchecks['passed']
manifest=json.loads((root/'manifest.json').read_text());assert hashlib.sha256(Path('/root/freqtrade-stable/user_data/strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==manifest['production_source_sha256']
lines+=[f"{rulechecks} 项规则/因果性检查通过；实际 BTC 原因退出 {exitchecks['actual_exit_checks']} 次、弱 BTC 冷却入场 {cooldown['weak_btc_entry_checks']} 次、共享现金初次成交 {requests['filled_entry_checks']} 次核对通过。114 条独立日权益曲线逐币持仓重建通过，最大权益误差 {position['max_equity_error']:.10g} USDT；全部原生回测现金账及每日账户风险权益通过核验。冻结数据/源码与正式策略哈希一致。",'', '观察池事后选择、窗口重叠且此前已看过，本轮是探索性回溯研究，没有严格样本外证据。汇总胜出次数不表示统计显著性；无滑点也不代表真实执行成本。下一步若测试组合，仍需与各单项及原版比较，并保留独立验证区间或前向记录。']
(root/'REPORT.md').write_text('\n'.join(lines)+'\n');manifest.update(status='complete',rule_checks=rulechecks,new_backtests=90,unique_comparison_rows=114);(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(aggregate,indent=2))
