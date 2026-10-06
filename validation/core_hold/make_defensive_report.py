"""Build the complete adaptive-research report from reconciled CSV results."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent/'trend_exposure'
rows=list(csv.DictReader((root/'summary.csv').open()))
windows=json.loads((root/'windows.json').read_text())
decision=json.loads((root/'final_decision.json').read_text())
lines=['# BTC / SOL / ETH：上涨参与与熊市防守优化','',decision['conclusion'],'',
'初始 1000 USDT，3 个槽位，单边手续费 0.1%，每段独立从现金开始。持有基准三币各 1/3 买入不再平衡。收益与最大回撤均按逐日收盘总权益计算。','',
'## 收益 / 最大回撤','',
'| 区间 | 原 Growth | 快速恢复候选 | 严格 MA150 趋势 | 等权持有 |','|---|---:|---:|---:|---:|']
for w in windows:
    group={r['strategy']:r for r in rows if r['window']==w['label']}
    names=['Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy','BtcTrendFullCycleStrategy','BtcTrendFullCycleDefensiveStrategy','BuyAndHold']
    if not all(n in group for n in names):continue
    values=[f"{float(group[n]['return_pct']):+.2f}% / {float(group[n]['wallet_drawdown_pct']):.2f}%" for n in names]
    lines.append('| '+w['title']+' ('+group[names[0]]['start']+'～'+group[names[0]]['end']+') | '+' | '.join(values)+' |')
lines+=['','## 上涨期收益差距（百分点）','','| 区间 | 原 Growth 落后持有 | 快速恢复落后持有 | 严格趋势落后持有 |','|---|---:|---:|---:|']
for label in ['bull_2023_2024','requested_long']:
    group={r['strategy']:r for r in rows if r['window']==label}
    names=['Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy','BtcTrendFullCycleStrategy','BtcTrendFullCycleDefensiveStrategy']
    if all(n in group for n in names):
        lines.append('| '+label+' | '+' | '.join(f"{float(group[n]['gap_pp']):.2f}" for n in names)+' |')
lines+=['','## 规则与处理','',
'- 原 Growth：此前已采用的交接补仓、关闭周线半仓，原入场、50% 核心与 BTC 两日转熊退出。','- 快速恢复：BTC 高于 MA150 或高于上升的 EMA10 时全仓；两者同时失效连续两天退出到现金。各币保留自己的已实现盈亏。无永久核心仓、无熊市分档买入。','- 严格趋势：BTC 收盘高于 MA150 才允许三币满仓；低于 MA150 连续两天后下一日全部退出；长均线下短反弹不开仓。无永久核心仓、无熊市分档买入。入场仍按组合权益分为三槽，与第一轮候选 TrendExposure150 完全一致。','',
'快速恢复在选参上涨期 +565.73%，回撤 30.80%，但长区间回撤 59.69%、牛转熊回撤 73.28%；2022 熊市 66 笔交易仍亏 50.24%。因此拒绝作为默认。','',decision['details'],'',
'## 全部选参候选（含失败方案）','',
'三轮自适应训练搜索共 19 个候选，仅在 2023–2024 上涨窗口筛选。先筛落后持有≤200个百分点且回撤低于持有的候选；无人达标，再按收益－2×回撤排序。快速恢复选定后冻结规则做五区间复测。它失败后，追加复测第一轮已经测试过的严格 MA150 对照，没有继续修改参数。这个追加选择利用了已观察的复测结果，不能视为干净样本外验证。','',
'| 候选 | 收益 | 最大回撤 | 落后持有（百分点） |','|---|---:|---:|---:|']
for r in rows:
    if r['window']=='bull_2023_2024' and r['strategy'].startswith('Trend'):
        lines.append(f"| {r['strategy']} | {float(r['return_pct']):+.2f}% | {float(r['wallet_drawdown_pct']):.2f}% | {float(r['gap_pp']):.2f} |")
lines+=['','## 验证、复现与限制','',
'原 11 项回归检查通过；最终保留源码的趋势与冷却检查见 trend_cooldown/REPORT.md，覆盖闭合日线、指标前缀不受未来数据影响、可用资金 / 最小订单、独立币资金、缺失 BTC 数据、公开类与冻结研究候选的一致性。公开类和研究候选的五区间权益须一致。','',
'完整成交现金流与引擎 final_balance 核对误差 <0.05 USDT；期末强制退出从盯市曲线排除，剩余持仓按相同终点收盘估值。已实现利润已经进入现金，不重复相加。清算收益另扣终点剩余持仓卖出费。','',
'数据和手续费与先前比较相同。固定三币存在选币幸存者偏差；历史区间已经反复查看，参数又经搜索，不保证未来收益。日线开盘模拟成交，未计额外滑点；所列回撤为日线收盘回撤，并非盘中最大回撤。','',
'现有交易服务与其配置没有更改。公开候选在 user_data/strategies/ma200_btc_regime_full_cycle_core_hold_strategy.py；原始归档和逐日权益在 results；决策在 final_decision.json；全部统计在 summary.csv。','',
'复现：按父目录 README 挂载，使用固定镜像 freqtradeorg/freqtrade@sha256:7031bca43ed7668ebf421725dd5016acade6ef88b0771db3e08c96e6d19a42db 与单线程环境。已删除旧试验的源码位于原始结果 ZIP。运行 /research/run_trend_exposure.py --phase validation 重放当前保留的 Growth、快速恢复、严格 MA150 三类五区间比较。最后运行 /research/make_defensive_report.py。','']
(root/'REPORT.md').write_text('\n'.join(lines))
print(root/'REPORT.md')
