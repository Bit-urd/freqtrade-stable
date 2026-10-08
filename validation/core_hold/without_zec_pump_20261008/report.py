import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent;prior=root.parent/'requested_twelve_pool_20261008';old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';hold='BuyAndHold';names=[old,new,hold]
windows=json.loads((root/'windows.json').read_text());rows=list(csv.DictReader((root/'summary.csv').open()));idx={(r['window'],r['strategy']):r for r in rows};oldrows=list(csv.DictReader((prior/'summary.csv').open()));oi={(r['window'],r['strategy']):r for r in oldrows};assert len(rows)==18
comparison=[]
for w in windows:
 c=dict(window=w['label'],start=w['start'],end=w['end'],active_pair_count=len(w['pairs']),slot_count=w['slots'],reference_window=w['reference_window'])
 for n,p in zip(names,['original','two_day','hold']):
  r=idx[w['label'],n]
  for key in ['return_pct','wallet_drawdown_pct','mean_idle_cash_pct','ending_equity']:c[p+'_'+key]=float(r[key])
 c['two_day_return_change_vs_original_pp']=c['two_day_return_pct']-c['original_return_pct'];c['two_day_dd_change_vs_original_pp']=c['two_day_wallet_drawdown_pct']-c['original_wallet_drawdown_pct'];c['two_day_return_minus_hold_pp']=c['two_day_return_pct']-c['hold_return_pct'];c['two_day_dd_minus_hold_pp']=c['two_day_wallet_drawdown_pct']-c['hold_wallet_drawdown_pct'];comparison.append(c)
with (root/'comparison.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(comparison[0]));w.writeheader();w.writerows(comparison)
lines=['# 去掉 ZEC、PUMP：原版、BTC 两天退出与持有','',
'剩余请求币池为 BTC、ETH、BNB、LINK、XRP、UNI、DOGE、SOL、ARB、HYPE。HYPE 在本交易所仅有13根现货日线，不能暖机或形成MA150，因此分别测试九个有效币投入全部预算，以及十槽位为HYPE留1/10初始预算现金。','',
'冻结上一轮相同现货数据至2026-10-06，1000 USDT初始资金、每边手续费0.1%、滑点0。只移除ZEC/PUMP，原版和两天版交易规则不改，重新运行各币预算、账户风险状态与实际成交。每个窗口独立开户，收益与回撤为含现金的日线收盘账户权益，三组均不额外强制卖出末日持仓。','',
'## 删除后的真实组合结果','', '|币池窗口|实际币数 / 槽位|起止日期|原版收益 / 回撤|两天版收益 / 回撤|持有收益 / 回撤|','|---|---:|---|---:|---:|---:|']
for c in comparison:
 vals=[f"{c[p+'_return_pct']:+.2f}% / {c[p+'_wallet_drawdown_pct']:.2f}%" for p in ['original','two_day','hold']];lines.append(f"|{c['window']}|{c['active_pair_count']}/{c['slot_count']}|{c['start']}—{c['end']}|{'|'.join(vals)}|")
lines+=['','## 与上一轮同日期币池直接比较','', '下表同时展示删除前后，不把原组合已实现盈亏直接相减当成新策略回测。原版同样重新计算，持有也重新等预算分配。','', '|对应区间 / 币池|原版收益 / 回撤|两天版收益 / 回撤|持有收益 / 回撤|','|---|---:|---:|---:|']
for label,ref,title in [('Active9_long','Main10_full_cycle','2023-08-20至今'),('Active9_same_period','Main10_mature11_control','2026-02-08至今')]:
 for source,tag,key in [(oi,'原十币含ZEC',ref),(idx,'删除ZEC后的九币',label)]:
  vals=[f"{float(source[key,n]['return_pct']):+.2f}% / {float(source[key,n]['wallet_drawdown_pct']):.2f}%" for n in names];lines.append(f"|{title}：{tag}|{'|'.join(vals)}|")
for tag,key in [('原十一币含ZEC/PUMP','Mature11_full_cycle'),('原十二槽位含ZEC/PUMP、HYPE留现金','Requested12_mature11_cash')]:
 vals=[f"{float(oi[key,n]['return_pct']):+.2f}% / {float(oi[key,n]['wallet_drawdown_pct']):.2f}%" for n in names];lines.append(f"|2026-02-08至今：{tag}|{'|'.join(vals)}|")
vals=[f"{float(idx['Requested10_same_period',n]['return_pct']):+.2f}% / {float(idx['Requested10_same_period',n]['wallet_drawdown_pct']):.2f}%" for n in names];lines.append(f"|2026-02-08至今：删除两币后十槽位、HYPE留现金|{'|'.join(vals)}|")
lines+=['','## 收益与回撤取舍','', '|窗口|两天版减原版收益 pp|两天版减原版回撤 pp|两天版减持有收益 pp|两天版减持有回撤 pp|','|---|---:|---:|---:|---:|']
for c in comparison:lines.append(f"|{c['window']}|{c['two_day_return_change_vs_original_pp']:+.2f}|{c['two_day_dd_change_vs_original_pp']:+.2f}|{c['two_day_return_minus_hold_pp']:+.2f}|{c['two_day_dd_minus_hold_pp']:+.2f}|")
lines+=['','正回撤差表示回撤扩大。各窗口有重叠，不把次数当作独立验证概率；不设置固定5个百分点回撤淘汰门槛。','',
'## 对排除实验的解释','',
'本轮是在已经知道ZEC/PUMP造成相对持有差距后，按用户要求做的固定排除实验。它验证指定币池变化的实际结果，不能据此声称未来排除这两个币就总能胜过持有，也不能把历史强势币排除后的胜出当成独立样本外证据。其他币将来也可能出现与BTC不同步的行情。','',
'HYPE预留现金导致的收益与回撤变化属于预算变化，不是HYPE策略已经获利或提供了保护；九币账户和十槽位现金账户分别列出。','']
if (root/'DECISION.md').exists():lines += [(root/'DECISION.md').read_text(),'']
lines+=['## 验证与文件','']
a=json.loads((root/'audit_verification.json').read_text());v=json.loads((root/'verification.json').read_text())
lines += [f"完成12次新原生策略回测、6条持有基准。{v['count']}项规则/截断历史检查、{a['curve_checks']}条权益重建、{a['actual_btc_exit_checks']}次实际BTC退出、{a['actual_weak_btc_entry_cooldown_checks']}次弱BTC入场冷却、{a['daily_risk_equity_checks']}日风险权益核验通过。最大现金误差{a['max_cash_error']:.10g} USDT，最大权益误差{a['max_equity_error']:.10g} USDT。",'',
'策略与数据哈希和上一轮一致，正式策略、配置与运行服务未修改。','',
'[汇总CSV](comparison.csv) · [原始指标](summary.csv) · [逐币盈亏](profit_attribution.csv) · [权益核验](audit_verification.json) · [上一轮完整报告](../requested_twelve_pool_20261008/REPORT.md)。','']
(root/'REPORT.md').write_text('\n'.join(lines));print('Wrote paired portfolio comparison')
for c in comparison:print(c['window'],*[f"{c[p+'_return_pct']:+.2f}/{c[p+'_wallet_drawdown_pct']:.2f}" for p in ['original','two_day','hold']])
