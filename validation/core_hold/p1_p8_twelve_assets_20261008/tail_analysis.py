"""Describe exceptional gains and worst losses without an acceptance cutoff."""
import csv,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
rows=list(csv.DictReader((root/'comparison_matrix.csv').open()));cases=[r for r in rows if r['status']=='full' and r['ma150_ready_at_start']=='True']
for r in cases:
 for key in ['return_change_pp','relative_ending_wealth_change_pct','drawdown_change_pp']+[p+'_'+m for p in ['original','two_day','hold'] for m in ['return_pct','wallet_drawdown_pct']]:r[key]=float(r[key])
notes=['## 关键改善与尾部损失','',
'以下仅看 76 个完整且 MA150 已就绪案例。它们并非独立同分布样本，次数是历史描述，不是概率估计；没有用这些幅度作为淘汰门槛。关注“少数关键改善能否抵偿普遍或极端损失”，而非只按胜率投票。','',
'|方法|最差阶段收益（标的/阶段）|最高账户回撤（标的/阶段）|阶段亏损至少50%的案例|阶段亏损至少70%的案例|回撤至少60%的案例|',
'|---|---|---|---:|---:|---:|']
result={}
for prefix,label in [('original','原版'),('two_day','两天退出'),('hold','持有')]:
 worst=min(cases,key=lambda c:c[prefix+'_return_pct']);dd=max(cases,key=lambda c:c[prefix+'_wallet_drawdown_pct'])
 n50=sum(c[prefix+'_return_pct']<=-50 for c in cases);n70=sum(c[prefix+'_return_pct']<=-70 for c in cases);dd60=sum(c[prefix+'_wallet_drawdown_pct']>=60 for c in cases)
 notes.append(f"|{label}|{worst[prefix+'_return_pct']:.2f}%（{worst['asset']} {worst['phase']}）|{dd[prefix+'_wallet_drawdown_pct']:.2f}%（{dd['asset']} {dd['phase']}）|{n50}|{n70}|{dd60}|")
 result[prefix]=dict(worst_return=worst[prefix+'_return_pct'],worst_case=worst['asset']+'_'+worst['phase'],max_dd=dd[prefix+'_wallet_drawdown_pct'],max_dd_case=dd['asset']+'_'+dd['phase'],loss50_cases=n50,loss70_cases=n70,dd60_cases=dd60)
notes+=['','**两天版改善最大的六个实际案例**（按相对期末权益排序）：','',
'|标的阶段|原版收益 / 回撤|两天版收益 / 回撤|持有收益 / 回撤|相对原版期末权益变化|','|---|---:|---:|---:|---:|']
for c in sorted(cases,key=lambda c:c['relative_ending_wealth_change_pct'],reverse=True)[:6]:
 vals=[f"{c[p+'_return_pct']:+.2f}% / {c[p+'_wallet_drawdown_pct']:.2f}%" for p in ['original','two_day','hold']]
 notes.append(f"|{c['asset']} {c['phase']}|{'|'.join(vals)}|{c['relative_ending_wealth_change_pct']:+.2f}%|")
# Existing completed portfolio study is context, not merged statistically with these single-asset tests.
notes+=['','**一个实际保住行情的事件：AAVE P7，2024-08-18 入场。** 原版在 08-19 因 BTC 一天弱势退出，该笔净收益约 +1.49 USDT；两天版未在这一天退出，持有至 08-29，该笔净收益约 +97.95 USDT。两笔成交资金会受此前账户路径影响，不能把差额全部当作独立的单次退出效果；但退出时点与持仓延续确实不同。这是两天确认的具体价值，不只是“某个阶段多赚了一点”。同一阶段整体回撤仍略扩大，完整账户收益/回撤已列在上表。','']
notes+=['','**此前连续组合结果仍需一起考虑，不能因本轮熊市退步就抹去：**','',
'|连续组合区间|原版收益 / 回撤|两天版收益 / 回撤|持有收益 / 回撤|','|---|---:|---:|---:|']
prior=root.parent/'btc_exit_confirmation_20261008';pr=list(csv.DictReader((prior/'summary.csv').open()));groups={}
for r in pr:groups.setdefault(r['window'],{})[r['strategy']]=r
for window in ['core3_full_cycle','core3_continuous_2023_latest','core3_recent']:
 if window not in groups:continue
 d=groups[window];vals=[f"{float(d[n]['return_pct']):+.2f}% / {float(d[n]['wallet_drawdown_pct']):.2f}%" for n in ['BtcCoinGuardCycleRiskStrategy','BtcTwoDayExitCycleRiskStrategy','BuyAndHold']]
 example=next(iter(d.values()));notes.append(f"|BTC/SOL/ETH {example['start']}—{example['end']}|{'|'.join(vals)}|")
notes+=['','这些连续组合包含持仓复利和跨币账户风控，不能与单币阶段独立开户作同等案例计数。原有优势可支持保留候选，阶段损失则说明它不是没有代价；本轮不自动切换正式策略。完整历史组合结果见 [此前两天退出报告](../btc_exit_confirmation_20261008/REPORT.md)。','']
notes+=['## 综合判断','','两天版已有保住部分行情的实际价值，应保留为候选，不能单凭 P4 或阶段胜率淘汰。它的收益侧重减少过早退出；这组阶段并未显示它比原版更能缓解极端账户损失，尾部损失仍需承担。与持有相比，主要下跌保护在两版共有的 BTC/个币过滤和账户风控中已存在。\n\n此前 BTC/SOL/ETH 连续账户在长期、2023 至今和近期均有明显改善，说明少数时段收益及后续复利可以改变最终结果；本轮扩大到十二币后，阶段优势集中于少数标的，不能直接推出十二币统一改为两天退出就会更好。八个阶段不覆盖完整历史、各阶段重置账户，和连续回测回答的是不同问题。综合证据支持保留两天版研究价值，正式策略的取舍应以确定的实际币池连续账户结果为依据。本轮未切换正式版。\n\n']
p=root/'REPORT.md';s=p.read_text();s=s.replace('## 验证与文件','\n'.join(notes)+'\n## 验证与文件');p.write_text(s)
(root/'tail_analysis.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(result,indent=2,ensure_ascii=False))
