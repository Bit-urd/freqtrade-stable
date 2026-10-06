"""Render selected daily equity curves and a concise comparison report."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path('/research')
table = pd.read_csv(ROOT/'summary.csv')
selection = json.loads((ROOT/'selection.json').read_text())
chosen = list(dict.fromkeys(['BuyAndHold', 'Ma200BtcRegimeFullCyclePortfolioStrategy',
                             'Ma200BtcRegimeFullCycleCoreHoldStrategy',
                             selection['best_training_return'],
                             selection['training_return_minus_2dd']]))
alias = {'BuyAndHold': 'Equal-weight hold',
         'Ma200BtcRegimeFullCyclePortfolioStrategy': 'Original portfolio',
         'Ma200BtcRegimeFullCycleCoreHoldStrategy': 'Default core hold'}
fig, axes = plt.subplots(3, 2, figsize=(15, 12))
for i, window in enumerate(['train', 'bear', 'test']):
    for name in chosen:
        curve = pd.read_csv(ROOT/'results'/window/f'equity_{name}.csv', index_col=0,
                            parse_dates=True)
        axes[i, 0].plot(curve.index, curve.equity, label=alias.get(name,name), linewidth=1.4)
        peak = curve.equity.cummax().clip(lower=1000)
        axes[i, 1].plot(curve.index, 100*(curve.equity/peak-1), linewidth=1.4)
    axes[i, 0].set_title(f'{window}: daily closing portfolio equity')
    axes[i, 0].set_ylabel('USDT (initial 1,000)')
    axes[i, 0].legend(fontsize=8)
    axes[i, 1].set_title(f'{window}: portfolio drawdown')
    axes[i, 1].set_ylabel('% from prior peak')
    for ax in axes[i]:
        ax.grid(alpha=.25)
fig.tight_layout()
fig.savefig(ROOT/'equity_comparison.png', dpi=160)
plt.close(fig)

lines = ['# CoreHold 回测结果（2026-10-06）', '',
         '现货；当前配置的 11 币；初始资金 1,000 USDT；单边手续费 0.1%；'
         '可用资金比例 100%；日线成交模拟，周线仓位信号。未修改正在运行的交易配置。', '',
         '## 参数选择与比较', '',
         f"训练收益最高组合：`{selection['best_training_return']}`。",
         f"训练收益减两倍回撤评分最高组合：`{selection['training_return_minus_2dd']}`。",
         '两种选择仅使用训练结果；后续仅对选中组合和两个原始对照运行验证。', '',
         '收益为期末逐日收盘盯市权益相对初始资金的变化；回撤来自逐日总权益，'
         '包含持仓浮盈亏。清算收益额外扣除剩余持仓的卖出手续费。', '',
         '| 区间 | 策略 | 盯市收益 | 清算收益 | 组合最大回撤 | 平均现金占比 |',
         '|---|---|---:|---:|---:|---:|']
for window in ['train','bear','test']:
    for name in chosen:
        r = table[(table.window==window)&(table.strategy==name)].iloc[0]
        lines.append(f'| {window} | {alias.get(name,name)} | {r.return_pct:+.2f}% | '
                     f'{r.liquidated_return_pct:+.2f}% | {r.wallet_drawdown_pct:.2f}% | '
                     f'{r.mean_idle_cash_pct:.2f}% |')
lines.extend(['', '实际数据覆盖：', ''])
for window, dates in selection['windows'].items():
    lines.append(f"- {window}: {dates['start']} 至 {dates['end']}")
lines.extend(['', '## 结论', '',
              '原 Portfolio 在三个区间的收益均高于默认 CoreHold 和训练选中的候选。'
              '提前入场、75% 核心、1 天确认在训练中改善默认收益，但在历史压力与留出区间'
              '收益均下降；训练及留出区间的组合回撤也高于默认 CoreHold。'
              '因此不将该候选设为默认，不改变运行中的交易配置。', '',
              'CoreHold 的默认 50% 核心与 2 天退出确认保留，前一轮成交状态、最小交易金额'
              '和已收盘数据读取的代码修复保留。这是未能通过后续验证的参数试验，'
              '不是已证实的收益优化。', '',
              '## 会计核对与基准约定', '',
              '所有成交（包括部分卖出）的现金流重建终值，均与引擎 final_balance '
              '核对，误差小于 0.05 USDT。该引擎终值包含期末强制平仓；'
              '主比较剔除期末强制平仓订单，并将剩余代币统一按最后日线收盘价计价。'
              '清算列对这些剩余代币扣一次卖出手续费。已实现收益只通过现金流进入权益一次。', '',
              '等权基准为每币预留 1/11 初始现金，起点或该币已有 61 根完整日线后的'
              '第一个开盘买入；新上市币之前保留现金；以后不调仓。策略使用相同币池、'
              '资金、费用和日期，但资金可随策略规则在现有币间分配。', '',
              '## 数据和解释范围', '',
              '11 个币的日线和周线已下载；日线无重复、断档或非正收盘价格。'
              '逐币覆盖和检查结果见 data_manifest.json。', '',
              'train 为参数选择区间。test 使用不与训练重叠的后续行情，但历史价格现在已知，'
              '这属于回顾性留出检验；bear 为先前已经参与策略开发的历史压力测试，'
              '不应称为完全未知样本。当前固定币池存在幸存者选择偏差。', '',
              '回测以日线开盘模拟市场单，没有盘口、滑点或日内执行细节。'
              '一次留出检验不能证明实盘稳定有效。', '',
              '## 产物', '',
              '- summary.csv：全部训练组合和选中组合验证结果；包含牛市买入滞后诊断。',
              '- results/*/equity_*.csv：逐日现金及组合权益。',
              '- selection.json：冻结的训练参数选择。',
              '- equity_comparison.png：权益与回撤对比图。',
              '- README.md：下载、回测及分析复现命令。', '',
              '![权益与回撤](equity_comparison.png)', ''])
(ROOT/'REPORT.md').write_text('\n'.join(lines))
