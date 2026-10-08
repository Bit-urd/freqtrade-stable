"""Summarize only complete, reconciled engine results; no parameter fitting."""
import csv
import gzip
import hashlib
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
names = ['BtcCoinGuardCycleRiskStrategy', 'EthRotationCycleRiskStrategy',
         'EthBreadthRotationCycleRiskStrategy', 'Ma200BtcRegimeFullCyclePortfolioStrategy', 'BuyAndHold']
labels = dict(zip(names, ['原 CycleRisk', 'ETH 双趋势通道', 'ETH 通道＋市场宽度', '原 MA200', '持有']))
windows = json.loads((root / 'windows.json').read_text())
rows = list(csv.DictReader((root / 'summary.csv').open()))
index = {(r['window'], r['strategy']): r for r in rows}
assert len(rows) == len(index) == len(windows) * len(names) == 215
for window in windows:
    label = window['label']
    assert (root / 'results' / label / 'completed.json').exists()
    assert set(r['strategy'] for r in rows if r['window'] == label) == set(names)
    for name in names:
        row = index[label, name]
        assert row['start'] == window['start'] and row['end'] == window['end']
        if window['pair'] == 'BTC/USDT' and name in names[1:3]:
            for key in ['return_pct', 'wallet_drawdown_pct', 'ending_equity', 'trades', 'normal_fills']:
                assert abs(float(row[key]) - float(index[label, names[0]][key])) < 1e-7
            assert int(row['eth_rotation_entries']) == 0
max_error = max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error'])
assert max_error < .05
comparison = []
for window in windows:
    baseline = index[window['label'], names[0]]
    for name in names[1:3]:
        row = index[window['label'], name]
        comparison.append(dict(pair=window['pair'], window=window['label'], strategy=name,
            wealth_ratio=float(row['ending_equity']) / float(baseline['ending_equity']),
            return_change_pp=float(row['return_pct']) - float(baseline['return_pct']),
            drawdown_change_pp=float(row['wallet_drawdown_pct']) - float(baseline['wallet_drawdown_pct']),
            extra_rotation_positions=int(row['eth_rotation_entries']),
            quick_loss_change=int(row['quick_loss_positions']) - int(baseline['quick_loss_positions']),
            fills_change=int(row['normal_fills']) - int(baseline['normal_fills'])))
def write_csv(filename, records):
    with (root / filename).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
write_csv('comparison.csv', comparison)
aggregate = []
for group, pairs in [('all_non_btc', None), ('original_altcoins', ['SUI/USDT', 'ZEC/USDT']),
                     ('additional_coins', ['ADA/USDT', 'DOGE/USDT', 'AVAX/USDT']),
                     ('portfolio', ['PORTFOLIO'])]:
    for name in names[1:3]:
        sub = [r for r in comparison if r['strategy'] == name
               and (r['pair'] != 'BTC/USDT' if pairs is None else r['pair'] in pairs)]
        aggregate.append(dict(group=group, strategy=name, windows=len(sub),
            return_better=sum(r['return_change_pp'] > 1e-6 for r in sub),
            return_worse=sum(r['return_change_pp'] < -1e-6 for r in sub),
            return_same=sum(abs(r['return_change_pp']) <= 1e-6 for r in sub),
            drawdown_better=sum(r['drawdown_change_pp'] < -1e-6 for r in sub),
            drawdown_worse=sum(r['drawdown_change_pp'] > 1e-6 for r in sub),
            jointly_better=sum(r['return_change_pp'] > 1e-6 and r['drawdown_change_pp'] < -1e-6 for r in sub),
            median_wealth_ratio=statistics.median(r['wealth_ratio'] for r in sub),
            worst_wealth_ratio=min(r['wealth_ratio'] for r in sub),
            max_drawdown_increase_pp=max(r['drawdown_change_pp'] for r in sub),
            rotation_positions_with_overlapping_windows=sum(r['extra_rotation_positions'] for r in sub)))
write_csv('aggregate.csv', aggregate)

rotation_trades = []
distinct = set()
for window in windows:
    for name in names[1:3]:
        with gzip.open(root / 'results' / window['label'] / (name + '.json.gz'), 'rt') as f:
            trades = json.load(f)['trades']
        for trade in trades:
            if trade['enter_tag'] != 'eth_rotation_entry': continue
            distinct.add((name, trade['pair'], trade['open_timestamp']))
            rotation_trades.append(dict(window=window['label'], strategy=name, pair=trade['pair'],
                open_date=trade['open_date'], close_date=trade['close_date'], exit_reason=trade['exit_reason'],
                net_trade_return_pct=trade['profit_ratio'] * 100, profit_abs=trade['profit_abs'],
                duration_days=trade['trade_duration'] / 1440))
if rotation_trades: write_csv('rotation_trades.csv', rotation_trades)
trade_stats = []
for name in names[1:3]:
    sub = [r for r in rotation_trades if r['strategy'] == name]
    closed = [r for r in sub if r['exit_reason'] != 'force_exit']
    trade_stats.append(dict(strategy=name, count_including_overlapping_windows=len(sub),
        distinct_asset_entry_timestamps=sum(k[0] == name for k in distinct),
        normally_closed_positions=len(closed),
        losing_normally_closed=sum(r['net_trade_return_pct'] < 0 for r in closed),
        quick_loss_normally_closed=sum(r['net_trade_return_pct'] < 0 and r['duration_days'] <= 10 for r in closed)))
(root / 'rotation_trade_analysis.json').write_text(json.dumps(trade_stats, indent=2) + '\n')

# Verify the frozen sources and fixed data were not changed during the run.
manifest = json.loads((root / 'source_manifest.json').read_text())
for relative, expected in manifest.items():
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected
data_audit = json.loads((root / 'data_audit.json').read_text())
for record in data_audit['files']:
    file = root.parent / 'independent_trend_optimization_20261008/data' / record['file']
    assert hashlib.sha256(file.read_bytes()).hexdigest() == record['sha256']
preflight = json.loads((root / 'indicator_verification.json').read_text())
assert preflight['passed']
verification = dict(passed=True, windows=43, new_candidate_backtests=86,
    baseline_strategy_results=86, holding_benchmarks=43, rows=215,
    rule_and_prefix_checks=preflight['count'], btc_backtests_identical=True,
    max_ledger_error=max_error, strategy_and_data_hashes_unchanged=True,
    fresh_candidate_wallet_and_state=True,
    caveat='In-sample, overlapping windows, fixed retrospectively selected breadth universe.')
(root / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
plan = json.loads((root / 'plan.json').read_text()); plan['status'] = 'complete'
(root / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')

text = ['# ETH/BTC 轮动通道优化测试', '',
    '43 个窗口完成：86 次新增候选回测，86 组上一轮固定数据上的已核对策略基准，43 个持有基准。BTC/SUI/ZEC、ADA/DOGE/AVAX 及原 BTC/SOL/ETH 组合，统一初始 1000 USDT、单边手续费 0.1%、无滑点，截至 2026-10-06。单币一个槽位、组合三个槽位，每个窗口独立开户。收益与最大回撤均按日终盯市权益计算，包含浮亏；终点人为强平不计入该权益曲线，实际订单另核对引擎最终余额。', '',
    '## 事先固定的规则', '',
    'ETH 双趋势通道要求 ETH/USDT 收盘价 > EMA20 > EMA50，且两条均线均向上；ETH/BTC 合成收盘比值同样满足上述条件，两者合计连续两日成立，且有至少 50 日历史。ETH/BTC 由同交易所、同 UTC 日线的 ETH/USDT 与 BTC/USDT 收盘价相除构建，未使用直接 ETHBTC K 线。', '',
    '新增通道还要求 BTC 五日收益大于 -10%。这个限制仅关闭新增 ETH 通道，不覆盖原 BTC 通道。所有信号仅用完成日线，下一根日线开盘执行。', '',
    '宽度版使用 SOL、ADA、DOGE、AVAX、SUI、ZEC 六币固定观察池，排除正在交易的标的自身。仅满 50 根日线的同行计入分母；至少三个有效同行，其中至少 60% 收盘站上 MA50，且比例不低于十日前，才允许 ETH 通道。观察池按当前研究标的选择，具有事后选币偏差，不能当成无偏的全市场指数。', '',
    '非 BTC 标的的市场许可为原 BTC 许可 OR 新 ETH 通道；标的自身 coin_risk_on 入场、coin_risk_off 退出、原 14 日冷却、账户回撤降仓及 BTC 风险峰值重置均保留。BTC 自身完全沿用原规则。BTC 通道关闭时，新通道的目标档位为 min(账户风险档位, 50%)；BTC 恢复后回到原账户目标档位。只在档位变化时调仓，50% 不是每日严格市值上限。真实成交后才更新档位。没有使用独立突破例外或 ATR 移动退出。', '',
    '## 相对原 CycleRisk 的汇总', '',
    '| 范围 | 候选 | 收益更好/更差/相同 | 回撤更低 | 同时改善 | 期末资金比中位数 | 最差期末资金比 | 最大回撤恶化 |',
    '|---|---|---:|---:|---:|---:|---:|---:|']
for row in aggregate:
    text.append(f"| {row['group']} ({row['windows']}) | {labels[row['strategy']]} | {row['return_better']}/{row['return_worse']}/{row['return_same']} | {row['drawdown_better']} | {row['jointly_better']} | {row['median_wealth_ratio']:.4f} | {row['worst_wealth_ratio']:.4f} | {row['max_drawdown_increase_pp']:+.2f}pp |")
text += ['', '期末资金比为候选期末权益除以原 CycleRisk 期末权益。窗口相互重叠，以上数量不代表独立样本显著性。', '',
         '## 新通道实际入场', '', '| 候选 | 入场数（含重复窗口） | 去重币种/入场日期数 | 正常平仓 | 其中亏损 | 其中十日内亏损 |',
         '|---|---:|---:|---:|---:|---:|']
for row in trade_stats:
    text.append(f"| {labels[row['strategy']]} | {row['count_including_overlapping_windows']} | {row['distinct_asset_entry_timestamps']} | {row['normally_closed_positions']} | {row['losing_normally_closed']} | {row['quick_loss_normally_closed']} |")
coverage = list(csv.DictReader((root / 'signal_coverage.csv').open()))
text += ['', '## ETH 通道与原 BTC 通道的重叠', '',
    '两个市场通道之间是 OR；ETH 的绝对与相对趋势之间是 AND；宽度确认仅收紧新增 ETH 分支，原 BTC 分支不变。原 CycleRisk 的 BTC 许可已经包含收盘高于上升 EMA10 的恢复条件，因此即使 BTC 未站上中长期均线，也可能已经允许入场。', '',
    '| 窗口 | 候选 | ETH 双趋势天数 | 其中原 BTC 入场关闭 | 新通道额外许可天数 | 同时满足标的入场的天数 |',
    '|---|---|---:|---:|---:|---:|']
for row in coverage:
    if row['window'] in ['SUI_since_maturity', 'ZEC_full_cycle', 'DOGE_full_cycle']:
        text.append(f"| {row['window']} | {labels[row['strategy']]} | {row['eth_dual_trend_days']} | {row['eth_dual_when_btc_entry_closed_days']} | {row['extra_permission_days']} | {row['extra_permission_with_own_entry_days']} |")
text += ['', '以上按信号日期统计，次日才执行；还没有扣除已有持仓、冷却和可用资金限制，不等同于实际新增交易数。']
text += ['', '入场数只统计新增通道直接建立的交易，不包括由 BTC 通道建立、随后因 ETH 通道继续持有的交易。不同窗口起始资金和风控状态不同，去重日期也不是独立实验。十日内亏损是快速失败的描述指标，不能直接等同于假突破。', '',
         '## 全部窗口', '', '每格为累计收益 / 最大回撤。', '',
         '| 标的 / 窗口 | ' + ' | '.join(labels[n] for n in names) + ' |', '|---|' + '---:|' * len(names)]
for window in windows:
    cells = [f"{float(index[window['label'], n]['return_pct']):+.2f}% / {float(index[window['label'], n]['wallet_drawdown_pct']):.2f}%" for n in names]
    text.append('| ' + window['label'] + ' | ' + ' | '.join(cells) + ' |')
all_non_btc = {r['strategy']: r for r in aggregate if r['group'] == 'all_non_btc'}
text[4:4] = ['## 本轮判断', '',
    f"本轮不建议用这两个版本替换正式 CycleRisk。ETH 双趋势版在 36 个非 BTC 窗口中，收益更好 {all_non_btc[names[1]]['return_better']} 个、更差 {all_non_btc[names[1]]['return_worse']} 个、相同 {all_non_btc[names[1]]['return_same']} 个，仅 {all_non_btc[names[1]]['jointly_better']} 个同时改善收益和回撤。宽度版没有收益提高的窗口，只有减少部分恶化的效果。", '',
    '原 BTC 条件已有 EMA10 恢复通道，ETH 双趋势的大多数日期原策略已经允许参与。SUI 长周期 167 个 ETH 双趋势日中，只有 7 日原 BTC 通道关闭，而且这 7 日标的自身都不满足入场，故 SUI 全部六个窗口保持原结果。ZEC 完整周期 316 个 ETH 双趋势日中，只有 20 日 BTC 通道关闭，压力限制后额外许可 19 日。', '',
    '两个候选都只新增一个不同币种/入场日期的交易：DOGE 于 2022-08-18 入场。该交易在完整周期和 2022 年窗口重复出现。双趋势版 2022-08-20 退出，净交易收益 -15.68%；宽度版 2022-08-19 退出，净交易收益 -7.01%。其他效果来自持有及调仓路径变化，没有新增 SUI 或 ZEC 入场。', '',
    'ZEC 最近周期收益从 +690.92% 变为 +717.71%，期末权益实际仅提高约 3.39%，最大回撤保持 52.87%。宽度版将这部分改善也过滤掉。新增 ETH 参照没有解决该币此前大幅落后持有及 MA200 的问题。规则在此处的作用主要是补充少量市场轮动许可，仍需分别验证标的自身的独立上涨识别。', '']
text += ['', '## 检查与限制', '',
    f"{preflight['count']} 项指标/行为检查通过，包含历史截断不变、绝对及相对趋势分离、市场压力关闭、同行成熟度与自身排除、原标的退出保留、风险档位和费用。BTC 全部七个窗口的收益、回撤、交易数与成交数与原 CycleRisk 一致。逐单现金账与引擎余额最大误差 {max_error:.10g} USDT，逐日前日权益也核对控制器风险记录。策略和 16 个数据文件哈希未变。", '',
    '本轮规则在当前结果产生前固定，没有按币种或结果搜索周期；但历史已在前几轮研究中查看过，不属于严格样本外。宽度分母随历史上市和成熟变化；固定观察池有选择偏差。双趋势与两日确认会带来滞后，ETH 通道也无法覆盖 ETH 不强的个币独立行情。无滑点，未验证更细粒度成交或实盘稳健性。候选仅位于 validation 目录，未修改生产策略及运行服务。', '',
    '`summary.csv` 保留完整结果；`comparison.csv` 为逐窗口差异；`rotation_trades.csv` 为新增通道实际入场交易；`signal_audit/` 保存每日许可及宽度，便于解释遗漏与新增信号。']
(root / 'REPORT.md').write_text('\n'.join(text) + '\n')
print(json.dumps(verification, indent=2))
for row in aggregate:
    if row['group'] == 'all_non_btc': print(row)
