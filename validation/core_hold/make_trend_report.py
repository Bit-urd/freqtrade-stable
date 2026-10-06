"""Summarize frozen trend selection and regime checks without native-equity mixing."""
import csv,json
from pathlib import Path
root=Path('/research/trend_exposure')
rows=list(csv.DictReader((root/'summary.csv').open()))
selection=json.loads((root/'selection.json').read_text()); chosen=selection['selected']
baseline=list(csv.DictReader((root.parent/'regime_comparison/summary.csv').open()))
windows=json.loads((root/'windows.json').read_text())
lines=['# 趋势满仓与现金防守优化','', '仅 BTC/SOL/ETH，3 槽位，初始 1000 USDT，单边手续费 0.1%。每段从现金独立开始。收益按终点收盘总权益计算，回撤按逐日总权益计算。','',
'## 规则与选择','', f"本轮选择 `{chosen}`。训练选择依据：{selection['ranking']}。训练窗口为 2023-01-01～2024-12-31，之后冻结规则再做其余区间复测。",'',
'本次结果未达到上涨期落后持有≤200个百分点的目标，且长区间收益下降、回撤明显增加。候选仅保留为实验类，未替换 Growth 默认，也未修改运行服务。','',
'BTC 收盘高于 MA150，或收盘高于上升的 EMA10 时允许满仓；收盘低于 MA150 且 EMA10 恢复条件失效连续两天，下一日退出到现金。没有永久核心仓；熊市不分档抄底。三币各有独立资金份额，自己的已实现盈亏留在该币份额内，不在每次入场时把 SOL 收益分给 BTC/ETH。','',
'## 共同估值的收益 / 最大回撤','', '| 区间 | Growth 收益 | 新规则收益 | 持有收益 | 新规则落后持有（百分点） | Growth 回撤 | 新规则回撤 | 持有回撤 |','|---|---:|---:|---:|---:|---:|---:|---:|']
for w in windows:
    group={r['strategy']:r for r in rows if r['window']==w['label']}
    if chosen not in group: continue
    new=group[chosen]; hold=group['BuyAndHold']
    old=group.get('Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy') or next((r for r in baseline if r['window']==w['label'] and r['strategy']=='Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy'),None)
    if old is None: continue
    lines.append(f"| {w['title']} ({new['start']}～{new['end']}) | {float(old['return_pct']):+.2f}% | {float(new['return_pct']):+.2f}% | {float(hold['return_pct']):+.2f}% | {float(new['gap_pp']):.2f} | {float(old['wallet_drawdown_pct']):.2f}% | {float(new['wallet_drawdown_pct']):.2f}% | {float(hold['wallet_drawdown_pct']):.2f}% |")
lines+=['','## 全部上涨期候选（含失败方案）','','| 候选 | 收益 | 最大回撤 | 落后持有（百分点） |','|---|---:|---:|---:|']
for r in rows:
    if r['window']=='bull_2023_2024':
        lines.append(f"| {r['strategy']} | {float(r['return_pct']):+.2f}% | {float(r['wallet_drawdown_pct']):.2f}% | {float(r['gap_pp']):.2f} |")
lines+=['','## 验证与限制','','所有完整成交现金流与引擎 final_balance 核对，误差 <0.05 USDT。期末 force_exit 从日线盯市曲线剔除；清算收益另计终点收盘卖出手续费。不把已实现利润重复加入权益。','',
'使用固定三币历史回放，存在选币幸存者偏差；部分区间此前已查看，不能称为全新样本外验证。参数经过上涨窗口筛选，历史目标达成不保证未来目标。未计额外滑点，日线开盘模拟成交。','',
'原有 11 项回归检查以及新增 10 项检查通过，覆盖已完成日线、无未来数据影响、资金份额、最小下单金额、缺失 BTC 日线和公开类与研究候选的一致性。','',
'复现：使用父目录 README 的挂载与固定镜像 sha256:7031bca43ed7668ebf421725dd5016acade6ef88b0771db3e08c96e6d19a42db。运行 `/research/run_trend_exposure.py --phase training` 重放 19 个候选；运行 `/research/run_trend_exposure.py --phase validation` 重放固定候选与 Growth 的五区间对比。再运行 `/research/make_trend_report.py`。','',
'运行中的交易服务及其配置未更改。研究原始导出、成交和逐日权益位于 results；全部候选位于 strategies/trend_exposure_sweep.py，选择依据位于 selection_policy.json / selection.json。','']
(root/'REPORT.md').write_text('\n'.join(lines))
print('Wrote',root/'REPORT.md')
