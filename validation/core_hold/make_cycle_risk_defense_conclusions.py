"""综合四项固定防守试验，全部收益代价与持有对照公开。"""
from pathlib import Path
import csv,json
R=Path(__file__).parent;D=R/'cycle_risk_half_peak_revision'
folders=['cycle_risk_defense_revision','cycle_risk_loss_cooldown_revision','cycle_risk_half_peak_revision']
labels={'BtcCoinGuardCycleRiskStrategy':'CycleRisk 正式版','BtcCoinGuardConfirmedBtcEntryStrategy':'BTC 确认才入场','BtcCoinGuardSelectiveRecoveryEntryStrategy':'个币强势修复例外','BtcCoinGuardLossCooldownStrategy':'亏损后冷却','BtcCoinGuardHalfPeakRearmStrategy':'恢复保留一半峰值记忆','BuyAndHold':'持有'}
merged={};annual=[]
for name in folders:
 for x in csv.DictReader((R/name/'comparison.csv').open()):
  key=(x['window'],x['strategy'])
  if key in merged:
   for metric in ['return_pct','wallet_drawdown_pct']:assert abs(float(x[metric])-float(merged[key][metric]))<1e-7
  merged[key]=x
 for x in csv.DictReader((R/name/'annual_metrics.csv').open()):
  if not any(t['strategy']==x['strategy'] and t['year']==x['year'] for t in annual):annual.append(x)
rows=list(merged.values())
with (D/'all_candidates.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
lines=['# 防守优化：四项固定规则综合比较','','用户要求：收益不能降低太多的情况下，降低回撤。没有以最小回撤单独选优，也没有进行参数网格搜索。','', '共四项结构假设：BTC 确认入场、个币强势修复例外、亏损退出后的弱 BTC 冷却、风险恢复时保留一半旧权益峰值差额。最后一项不增加账户状态，不改变入场、退出和原权益阈值。','', 'BTC/SOL/ETH 共享1000 USDT、三槽位、每侧手续费0.1%，日线收盘真实权益回撤，持有等权不再平衡。最新完整日线为2026-10-06；近期基准较之前截至10月5日的报告略有变化。每个窗口独立账户；连续2023至今的年度拆分不重置账户。','']
for window in json.loads((D/'windows.json').read_text()):
 label=window['label'];lines += [f'## {label}','','| 策略 | 收益率 | 最大回撤 | 相对正式版收益变化 | 回撤变化 |','|---|---:|---:|---:|---:|']
 base=merged[label,'BtcCoinGuardCycleRiskStrategy'];br=float(base['return_pct']);bd=float(base['wallet_drawdown_pct'])
 for name,title in labels.items():
  x=merged[label,name];ret=float(x['return_pct']);dd=float(x['wallet_drawdown_pct'])
  lines.append(f'| {title} | {ret:+.2f}% | {dd:.2f}% | {ret-br:+.2f} 个百分点 | {dd-bd:+.2f} 个百分点 |')
 lines.append('')
lines+=['## 连续2023至今的年度收益与频率','','| 策略 | 年份 | 收益率 | 年内最大回撤 | 新开仓 | 正常平仓 |','|---|---:|---:|---:|---:|---:|']
for name in labels:
 for x in annual:
  if x['strategy']==name:lines.append(f"| {labels[name]} | {x['year']} | {float(x['return_pct']):+.2f}% | {float(x['within_year_drawdown_pct']):.2f}% | {x['opens']} | {x['normal_closes']} |")
lines+=['','## 验证与限制','','修复入场过滤在缺失数据时的布尔类型问题后，对前两项候选完整重跑18次，结果与原正常行情输入一致，旧失败测试及原源码保留。最终前三个报告为18+12+12=42次有效原生回测；入场、亏损冷却、峰值记忆分别20/21/20项规则与原风控检查，均须通过。各组复现10条正式版/持有基准，成交账本及每一日前收盘权益核对。','', '行情和起止日期已反复观察，重叠窗口不能当独立样本。报告最大回撤始终使用真实账户全历史峰值，内部风控峰值调整不能美化该指标。当前正式版实盘重启状态仍未持久化，本轮不自动切换正式或运行服务。','']
(D/'CONCLUSIONS.md').write_text('\n'.join(lines));print('Merged',len(rows),'unique strategy/window comparisons.')
