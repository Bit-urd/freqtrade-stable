"""Generate the causal diagnostics and growth-profile validation report."""
import csv
import json
from pathlib import Path

ROOT=Path('/research');FOLDER=ROOT/'improve_btc_sol_eth'
requested=list(csv.DictReader((FOLDER/'requested_comparison.csv').open()))
all_rows=list(csv.DictReader((FOLDER/'summary.csv').open()))
by_name={r['strategy']:r for r in requested}
selection=json.loads((FOLDER/'selection.json').read_text())
selection.update(recommended_profile='Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy',
                 default_settings={'HANDOVER_TOP_UP':True,'BULL_WEEKLY_SIZING':False,
                                   'CORE_RETAIN_FRACTION':0.5,'BTC_BEAR_CONFIRM_DAYS':2,
                                   'CORE_RESTORE_ON_RECOVERY':False,'HANDOVER_CORE_HOLD':False},
                 public_profiles={'CoreNoWeeklyTopUp':'Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy',
                                  'CoreUnifiedRestoreTopUp':'Ma200BtcRegimeFullCycleCoreHoldRecoveryStrategy'},
                 validation_candidates=['CoreNoWeeklyTopUp','CoreUnifiedRestoreTopUp'])
(FOLDER/'selection.json').write_text(json.dumps(selection,indent=2))
labels={'BuyAndHold':'三币等权持有','Ma200BtcRegimeFullCyclePortfolioStrategy':'原 Portfolio',
        'Ma200BtcRegimeFullCycleCoreHoldStrategy':'旧 CoreHold 默认',
        'CoreNoWeeklyTopUp':'Growth（新默认）','CoreUnifiedRestoreTopUp':'Recovery（实验）'}
chosen=list(labels)
lines=['# BTC / SOL / ETH 收益差距与优化验证', '',
       '标的仅 BTC/USDT、SOL/USDT、ETH/USDT；3 个槽位；初始 1,000 USDT；'
       '可用资金比例 100%；单边手续费 0.1%。权益包含所有持仓，按日线收盘价盯市。', '',
       '## 收益差距来源', '',
       '- 起点仓位不足：2022-11-22 每币最初只买约 133 USDT，总仓位约 40%，现金约 600 USDT。'
       '等权基准在 2022-11-21 开盘每币投入约 333 USDT。',
       '- 熊转牛未补仓：2023-01-16 原策略仍保留约 600 USDT 现金，约占当天权益 49%。'
       '原 Portfolio 的全区间平均现金占比 39.92%，BTC 高于 MA200 期间也为约 28.37%。',
       '- SOL 暴露不足：持有 SOL 利润约 5,641.39 USDT，原 Portfolio 的 SOL 利润约 '
       '1,902.03 USDT，差额 3,739.36 USDT，占整体收益缺口约 79%。'
       'BTC 少赚约 1,215.01 USDT；ETH 多赚约 235.44 USDT，抵消部分差额。',
       '- 成交费用不是主因：原策略非期末强制卖出订单累计费用约 49.56 USDT，'
       '远小于期末权益差 4,718.93 USDT。',
       '- 规则限制持续暴露：周线转空会减到半槽位；核心仓减仓后默认不恢复。'
       '熊市开仓标签交接后按币级弱势全退出，与牛市标签保留核心不同。'
       '上述影响不能仅靠平均现金占比线性推算，已分别做下表试验。', '',
       '## 指定区间：2022-11-21 至 2025-10-07', '',
       '| 方案 | 收益 | 期末权益 | 最大组合回撤 | 平均现金占比 |',
       '|---|---:|---:|---:|---:|']
for name in chosen:
    r=by_name[name]
    lines.append(f"| {labels[name]} | {float(r['return_pct']):+.2f}% | {float(r['ending_equity']):.2f} USDT | "
                 f"{float(r['wallet_drawdown_pct']):.2f}% | {float(r['mean_idle_cash_pct']):.2f}% |")
lines += ['', 'Growth 相对旧 CoreHold 多 15.63 个百分点，期末多 156.32 USDT，'
          '最大回撤增加约 0.51 个百分点。Recovery 多 43.26 个百分点、期末多 '
          '432.63 USDT，但最大回撤增加约 7.38 个百分点。两者仍明显落后于该上涨区间的等权持有。', '',
          '## 区间之外的检查', '',
          '| 区间 | 方案 | 收益 | 最大组合回撤 |', '|---|---|---:|---:|']
for window in ['stress','later']:
    for name in chosen:
        r=next(r for r in all_rows if r['window']==window and r['strategy']==name)
        lines.append(f"| {window} | {labels[name]} | {float(r['return_pct']):+.2f}% | "
                     f"{float(r['wallet_drawdown_pct']):.2f}% |")
lines += ['', '- stress：2021-01-01 至 2022-11-20，早期历史压力检查。',
          '- later：2025-10-08 至 2026-10-05，在指定优化区间之后。',
          '两个候选在两段验证区间中的成交与权益结果相同，因此不能据此声称 '
          'Recovery 的额外恢复逻辑比 Growth 更稳定。两段验证都优于旧 CoreHold；'
          '但 later 仍有亏损，stress 的组合回撤仍超过 60%。这些是回顾性历史检验，'
          '当前选择的三币也有幸存者选择偏差。', '',
          '## 实现与采用', '',
          '将用户指定的 `ma200_btc_regime_full_cycle_core_hold_strategy.py` 默认配置调整为 '
          'Growth：`HANDOVER_TOP_UP=True`、`BULL_WEEKLY_SIZING=False`。'
          '保留原来的入场条件、50% 核心保留、BTC 转熊 2 天确认。', '',
          '核心恢复与交接核心统一为可选开关：`CORE_RESTORE_ON_RECOVERY` 和 '
          '`HANDOVER_CORE_HOLD`，默认不启用。恢复与交接补仓的状态只在订单成交后更新，'
          '并检查可用资金和最低交易金额。', '',
          '另提供 `Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy` 和 '
          '`Ma200BtcRegimeFullCycleCoreHoldRecoveryStrategy` 两个明确命名的配置类，'
          '文件为 `user_data/strategies/ma200_btc_regime_full_cycle_core_hold_growth_strategy.py`。'
          '对应独立研究配置是 config_growth.json、config_recovery.json。'
          '未更换运行中机器人的策略或币池。', '',
          '研究目录 strategies/ 保留旧默认核心策略的代码快照（含新增开关，但默认仍为 '
          'HANDOVER_TOP_UP=False、BULL_WEEKLY_SIZING=True），供旧基准复现。'
          '当前 user_data/ 策略默认已是 Growth。', '',
          '11 项代码检查通过；新默认字段与已回测的 Growth 配置一致。'
          '重建成交现金流与引擎 final_balance 核对，误差小于 0.05 USDT；'
          '同区间旧默认收益仍与前一轮相同。', '',
          '## 全部试验', '',
          '| 策略配置 | 收益 | 最大组合回撤 |', '|---|---:|---:|']
for r in requested:
    lines.append(f"| {r['strategy']} | {float(r['return_pct']):+.2f}% | {float(r['wallet_drawdown_pct']):.2f}% |")
lines += ['', '详细逐币归因见 gap_by_coin.csv、initial_entries.csv；全部统计见 summary.csv '
          '和 requested_comparison.csv；逐日现金与权益位于 results/*/equity_*.csv。', '',
          '复现脚本：diagnose_gap.py、run_improvements.py、analyze_improvements.py、'
          'run_growth_validation.py。均使用父目录 README.md 的相同镜像与挂载。'
          '模拟采用日线开盘成交，未计额外滑点。', '']
(FOLDER/'REPORT.md').write_text('\n'.join(lines))
print('Wrote',FOLDER/'REPORT.md')
