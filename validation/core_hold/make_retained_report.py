"""Write the final active-strategy catalog and common-equity comparison."""
import csv,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
selected=root/'trend_phased'
def read(folder):return list(csv.DictReader((root/folder/'summary.csv').open()))
all_rows=read('trend_exposure')+read('trend_cooldown')+read('trend_phased')
lookup={(r['window'],r['strategy']):r for r in all_rows}
windows=json.loads((selected/'windows.json').read_text())
names={'Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy':'Growth（保留对照）','BtcTrendFullCycleDefensiveStrategy':'严格 MA150','BtcTrendRecoveryCooldownStrategy':'14 天冷却全仓','BtcTrendPhasedStrategy':'75% 分阶段正式版','BuyAndHold':'等权持有'}
records=[]
for w in windows:
    for n in names:
        r=lookup[w['label'],n];records.append(r)
        assert abs(float(r.get('ledger_error') or 0))<.05
with (selected/'retained_comparison.csv').open('w') as f:
    columns=list(dict.fromkeys(k for r in records for k in r))
    writer=csv.DictWriter(f,fieldnames=columns,lineterminator="\n");writer.writeheader();writer.writerows(records)
decision=json.loads((selected/'final_decision.json').read_text())
cleanup=json.loads((root/'trial_cleanup.json').read_text())
lines=['# 保留版本与本轮优化','',
'按用户决定，将 BtcTrendPhasedStrategy 提升为 BTC/SOL/ETH 正式版本（2026-10-06）。2023–2024 上涨期收益 +604.65%，落后等权持有 208.95 个百分点，达到本次上涨期 ≤250 个百分点目标；收盘最大回撤 30.34%。','',
'跨周期风险检查未通过；用户查看收益与持有回撤对比后，明确选择此版本作为正式版本。正式配置指定 BtcTrendPhasedStrategy；旧 Growth 实现保留作对照，没有更改或启动现有交易服务。最近区间收益下降；长区间回撤高于 Growth 与持有。目标只在该上涨窗口达成，不能表述为所有上涨区间均达标。','',
'BTC/SOL/ETH，初始 1000 USDT，3 槽位，单边手续费 0.1%；每段独立从现金开始。持有基准三币各 1/3 买入且不再平衡。区间为 UTC 日线，最近完整日线截止 2026-10-05。','',
'## 收益率 / 最大回撤','',
'| 区间 | Growth | 严格 MA150 | 14 天冷却全仓 | 75% 分阶段优化版 | 等权持有 |','|---|---:|---:|---:|---:|---:|']
for w in windows:
    r=lookup[w['label'],'BtcTrendPhasedStrategy']
    values=[f"{float(lookup[w['label'],n]['return_pct']):+.2f}% / {float(lookup[w['label'],n]['wallet_drawdown_pct']):.2f}%" for n in names]
    lines.append('| '+w['title']+' ('+r['start']+'～'+r['end']+') | '+' | '.join(values)+' |')
lines+=['','## 上涨收益差距（百分点）','','| 区间 | Growth | 严格 MA150 | 14 天冷却全仓 | 75% 分阶段优化版 |','|---|---:|---:|---:|---:|']
for label in ['bull_2023_2024','requested_long']:
    hold=float(lookup[label,'BuyAndHold']['return_pct'])
    lines.append('| '+label+' | '+' | '.join(f"{hold-float(lookup[label,n]['return_pct']):.2f}" for n in list(names)[:-1])+' |')
lines+=['','## 保留与清理','',
'- Growth：保留为旧版对照，最近区间收益优于新候选，长区间回撤也更低。','- 严格 MA150：防守参照。熊市亏 9.77%、回撤 17.67%；牛转熊收益 +101.45%、回撤 35.99%。','- 14 天冷却全仓：上涨收益参照，2023–2024 +695.49%，只落后持有 118.11 个百分点；保留为高暴露研究方案，熊市和转折回撤偏大。','- 75% 分阶段版：当前正式版本，弱长趋势降低投入，强趋势补足；上涨目标达成，但未通过全周期风险阈值。','- 原 Portfolio、旧 CoreHold 保留为历史基准。Recovery 保留为早期长区间较高收益的独立风险方案。BtcTrendFullCycleStrategy 仅作为共享算法实现基类与历史参照，不是本轮推荐独立运行的候选。','',
f"清理 {cleanup['removed_active_class_count']} 个淘汰或重复的生成试验类，包含旧参数网格、低效动量分配、拖慢恢复的单币保护和重复别名。原始 CSV、报告及包含 Python 源码的结果 ZIP 保留，方便核对历史事实。详见 ../trial_cleanup.json。",'',
'## 优化版规则','',
'1. BTC 收盘高于 MA150，或高于上升的 EMA10 时允许参与。长均线下的恢复入场仅投入该币资金份额的 75%；站上 MA150 后补足。','2. BTC 跌回 MA150 下方时按该币当时权益减少到 75%；MA150 与 EMA10 恢复条件同时失效连续两天，下一日全部退出。没有永久持仓下限。','3. 退出后若 BTC 仍在 MA150 下方，14 个自然日内禁止该币重新入场；站回 MA150 后可以提前解除冷却。','4. 仓位仅在趋势阶段切换时调整，不每日再平衡。阶段状态在订单成交后才更新；可用资金不足的补仓保持可重试。','5. 各币使用自己的初始份额和盈亏；部分卖出的利润只记一次。初始本金缓存时扣除钱包中已经包含的未平仓部分卖出利润，避免把它重复计入本金或分给其他币。','',
'## 验证与风险界限','',
'冻结 75% / MA150 / EMA10 / 14 天规则后复测五区间，研究候选与公开类的收益、回撤和期末权益逐一相同；每组全部订单现金流与引擎 final_balance 核对误差 <0.05 USDT。', '',
f"最终检查状态：{decision['tests_status']}。覆盖闭合日线与指标前缀、冷却边界与未来订单排除、资金隔离、部分利润核算、卖出成本换算、最小订单、取消／未成交状态、限额补仓重试、旧 Growth 默认保持不变。",'',
'预设风险阈值及实际结果：','', '| 复测区间 | 回撤上限 | 实际回撤 | 通过 |','|---|---:|---:|---|']
for window,r in decision['risk_checks'].items():lines.append(f"| {window} | {r['ceiling_pct']:.2f}% | {r['actual_drawdown_pct']:.2f}% | {'是' if r['passed'] else '否'} |")
lines+=['','全部回撤按每日收盘总权益计算，并非盘中极值。期末引擎强制平仓订单从盯市曲线剔除，剩余持仓按同一终点收盘估值；清算收益另扣剩余持仓卖出费。已实现利润已在现金中，不重复加入总权益。','',
'这是自适应历史研究：区间已经查看并用于多轮诊断，不是全新样本外验证。固定三币存在幸存者偏差；日线开盘模拟成交，未计额外滑点；历史达标不保证未来达标。','',
'## 文件与复现','',
'策略：user_data/strategies/ma200_btc_regime_full_cycle_core_hold_strategy.py 中 BtcTrendPhasedStrategy。研究配置：config_selected.json；正式用户配置：user_data/config_trend_btc_sol_eth.json（默认 dry-run，三个标的、三个槽位）。该配置明确选择 BtcTrendPhasedStrategy，旧 CoreHold/Growth 类名和算法保留以兼容历史对照。','',
'按父目录 README 挂载，使用固定镜像 freqtradeorg/freqtrade@sha256:7031bca43ed7668ebf421725dd5016acade6ef88b0771db3e08c96e6d19a42db 和单线程环境。运行 /research/run_trend_phased.py 重放五区间，运行 /research/make_retained_report.py 更新报告。','',
'比较表：retained_comparison.csv；原始成交与权益：results；选择和风险决策：selection.json / final_decision.json。初版分阶段资金核算的修正记录在 implementation_correction.json，旧导出仅作归档，本报告使用修正后的冻结公开类结果。','']
(selected/'REPORT.md').write_text('\n'.join(lines))
(root/'STRATEGIES.md').write_text('# Active strategy profiles\n\nSee [current retained comparison and optimization](trend_phased/REPORT.md).\n\n'+'\n'.join('- '+n+': '+label for n,label in names.items() if n!='BuyAndHold')+'\n\nOriginal Portfolio / old CoreHold remain historical baselines; Recovery remains the earlier higher-return research alternative. Removed generated strategies are listed in trial_cleanup.json; raw source backups remain in result ZIPs.\n')
print(selected/'REPORT.md')
