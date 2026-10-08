"""Report fixed entry ablations and descriptive initial-regime attribution."""
import csv
import gzip
import hashlib
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
names = ['BtcCoinGuardCycleRiskStrategy', 'TrendOnlyCycleRiskStrategy',
         'WeeklyTop2CycleRiskStrategy', 'WeeklyTop2TrendOnlyCycleRiskStrategy',
         'WeeklyTop2ConcentratedCycleRiskStrategy', 'BuyAndHold']
labels = dict(zip(names, ['原 CycleRisk', '仅 MA150 上入场', '每周动量前二', 'MA150 上＋动量前二', '前二集中配置', '持有']))
windows = json.loads((root / 'windows.json').read_text())
rows = list(csv.DictReader((root / 'summary.csv').open()))
index = {(r['window'], r['strategy']): r for r in rows}
assert len(rows) == len(index) == 114
for w in windows:
    assert (root / 'results' / w['label'] / 'completed.json').exists()
    assert (root / 'results' / w['label'] / 'concentrated_completed.json').exists()
    assert {r['strategy'] for r in rows if r['window'] == w['label']} == set(names)
    for name in names:
        r = index[w['label'], name]
        assert r['start'] == w['start'] and r['end'] == w['end'] and int(r['pair_count']) == len(w['pairs'])
max_error = max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error'])
assert max_error < .05
comparison = []
for w in windows:
    baseline = index[w['label'], names[0]]
    for name in names[1:5]:
        row = index[w['label'], name]
        comparison.append(dict(window=w['label'], universe=w['universe'], strategy=name,
            wealth_ratio=float(row['ending_equity']) / float(baseline['ending_equity']),
            return_change_pp=float(row['return_pct']) - float(baseline['return_pct']),
            drawdown_change_pp=float(row['wallet_drawdown_pct']) - float(baseline['wallet_drawdown_pct']),
            idle_cash_change_pp=float(row['mean_idle_cash_pct']) - float(baseline['mean_idle_cash_pct']),
            quick_loss_change=int(row['quick_loss_positions']) - int(baseline['quick_loss_positions']),
            fills_change=int(row['normal_fills']) - int(baseline['normal_fills'])))
def write_csv(name, records):
    with (root / name).open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
write_csv('comparison.csv', comparison)
aggregate = []
for universe in ['all', 'core3', 'broad7', 'broad8']:
    for name in names[1:5]:
        sub = [r for r in comparison if r['strategy'] == name and (universe == 'all' or r['universe'] == universe)]
        aggregate.append(dict(universe=universe, strategy=name, windows=len(sub),
            return_better=sum(r['return_change_pp'] > 1e-6 for r in sub),
            return_worse=sum(r['return_change_pp'] < -1e-6 for r in sub),
            drawdown_better=sum(r['drawdown_change_pp'] < -1e-6 for r in sub),
            jointly_better=sum(r['return_change_pp'] > 1e-6 and r['drawdown_change_pp'] < -1e-6 for r in sub),
            median_wealth_ratio=statistics.median(r['wealth_ratio'] for r in sub),
            worst_wealth_ratio=min(r['wealth_ratio'] for r in sub),
            max_drawdown_increase_pp=max(r['drawdown_change_pp'] for r in sub),
            median_cash_change_pp=statistics.median(r['idle_cash_change_pp'] for r in sub)))
write_csv('aggregate.csv', aggregate)

# Position audits validate actual filled initial entries, not just signal frames.
data_path = root.parent / 'independent_trend_optimization_20261008/data'
import sys
sys.path.insert(0, str(root / 'strategies'))
import pandas as pd
from momentum_selection_strategy import TrendOnlyCycleRiskStrategy, WeeklyTop2CycleRiskStrategy, WeeklyTop2TrendOnlyCycleRiskStrategy
from concentrated_selection_strategy import WeeklyTop2ConcentratedCycleRiskStrategy
histories = {p.stem.split('-')[0].replace('_', '/'): pd.read_feather(p)
             for p in data_path.glob('*-1d.feather')}
for h in histories.values(): h['ma150'] = h.close.rolling(150).mean()
config = json.loads((root / 'config.json').read_text())
rank_checks, trend_checks = 0, 0
position_rows = []
delays = []
for w in windows:
    with gzip.open(root / 'results' / w['label'] / (names[0] + '.json.gz'), 'rt') as f:
        baseline_trades = json.load(f)['trades']
    for name in names[:5]:
        selection = None
        if name in names[2:5]:
            cls = {names[2]: WeeklyTop2CycleRiskStrategy, names[3]: WeeklyTop2TrendOnlyCycleRiskStrategy,
                   names[4]: WeeklyTop2ConcentratedCycleRiskStrategy}[name]
            c = dict(config); c['exchange'] = dict(config['exchange']); c['exchange']['pair_whitelist'] = w['pairs']
            strategy = cls(c); strategy._history = lambda p, tf: histories[p].copy()
            selection = strategy._weekly_ranks()
        with gzip.open(root / 'results' / w['label'] / (name + '.json.gz'), 'rt') as f:
            trades = json.load(f)['trades']
        for t in trades:
            opened = pd.Timestamp(t['open_date']).normalize()
            h = histories[t['pair']]; prior = h.loc[h.date < opened].iloc[-1]
            if name in [names[1], names[3]]:
                assert prior.close > prior.ma150, (w['label'], name, t['pair'], opened)
                trend_checks += 1
            if selection is not None:
                monday = opened - pd.Timedelta(days=opened.dayofweek)
                snapshot = monday - pd.Timedelta(days=1)
                assert bool(selection.loc[snapshot, t['pair']]), (w['label'], name, t['pair'], opened)
                rank_checks += 1
            if name != names[0]:
                overlap = next((b for b in baseline_trades if b['pair'] == t['pair']
                    and b['open_timestamp'] <= t['open_timestamp'] <= b['close_timestamp']), None)
                if overlap is not None:
                    delays.append(dict(window=w['label'], strategy=name, pair=t['pair'],
                        original_open=overlap['open_date'], candidate_open=t['open_date'],
                        entry_delay_days=(t['open_timestamp'] - overlap['open_timestamp']) / 86400000,
                        entry_price_change_pct=(t['open_rate'] / overlap['open_rate'] - 1) * 100,
                        note='Matched candidate entry occurring within an original held position; descriptive, not isolated causal attribution.'))
        # Reconstruct position counts excluding final artificial force exits.
        events = []
        for t in trades:
            events.append((t['open_timestamp'], 1))
            if t['exit_reason'] != 'force_exit': events.append((t['close_timestamp'], -1))
        held, maximum = 0, 0
        for stamp, delta in sorted(events, key=lambda e: (e[0], e[1])):
            held += delta; maximum = max(maximum, held)
        actual_slots = 2 if name == names[4] else len(w['pairs'])
        assert maximum <= actual_slots
        position_rows.append(dict(window=w['label'], strategy=name, max_simultaneous_positions=maximum,
            slots=actual_slots, note='Ranking filters initial entries; fixed-budget prior winners can remain held beyond top2.'))
write_csv('position_audit.csv', position_rows)
if delays: write_csv('entry_delay.csv', delays)
preflight = json.loads((root / 'indicator_verification.json').read_text())
diagnostic = json.loads((root / 'diagnostic_verification.json').read_text())
concentrated_checks = json.loads((root / 'concentrated_verification.json').read_text())
assert preflight['passed'] and diagnostic['passed'] and concentrated_checks['passed']
for relative, expected in json.loads((root / 'source_manifest.json').read_text()).items():
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected
for d in json.loads((root / 'data_audit.json').read_text())['files']:
    assert hashlib.sha256((data_path / d['file']).read_bytes()).hexdigest() == d['sha256']
verification = dict(passed=True, windows=19, comparison_rows=114, new_backtests=90,
    reused_core3_baselines=5, holding_benchmarks=19, rule_and_prefix_checks=preflight['count'],
    concentrated_budget_checks=concentrated_checks['count'],
    actual_ranked_entry_checks=rank_checks, actual_trend_entry_checks=trend_checks,
    diagnostic_positions=diagnostic['positions'], max_ledger_error=max_error,
    max_profit_attribution_error=diagnostic['max_attribution_error'],
    unchanged_source_and_data_hashes=True, cash_and_risk_trace_reconciled=True)
(root / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
plan = json.loads((root / 'plan.json').read_text()); plan['status'] = 'complete'
(root / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')

text = ['# 原策略入场归因与强势选币测试', '',
    '## 主要结论', '',
    '保留原反弹入场更有依据。单币最长窗口中，初始在 MA150 下方、通过上升 EMA10 入场的持仓贡献约占 SUI 利润的 92%、DOGE 利润的 89%。这是持仓归因，不是删除规则的因果估计；反弹组虽然快速亏损多，也包含后续大趋势的早期入口。', '',
    '仅过滤到每周前二、仍保留分币预算，会留下大量现金。19 个窗口中收益改善 10 个、下降 9 个；三币全周期收益由 10639.45% 降至 3207.77%。不能只看回撤降低就判定选币更有效。', '',
    '集中共享资金的前二版有研究价值：19 个窗口收益改善 14 个，其中 9 个收益和回撤同时改善。七币组合 2023 年至终点收益 1792.40%，原版 219.42%；八币组合从 2023-10-01 起收益 2060.66%，原版 241.32%，回撤分别为 52.09% 和 53.30%。但三币全周期集中版收益只有 1835.05%，原版 10639.45%；八币组合 2024 年集中版回撤 43.50%，原版 30.72%。尚不能统一替换原版。', '',
    '具体机会损失：原版 SOL 首次持仓为 2021-01-08 至 2021-05-17，固定预算前二版推迟到 2021-02-01。集中两仓版 2021-01-02 至 2021-05-17 的两个槽位一直被 BTC 和 ETH 占用，SOL 直到 2021-06-03 才首次入场。排名过滤与旧仓占用都会阻碍新领涨币；原版还允许成功币种的自身利润继续复利，集中版改成共享资本，两者差异不能全部归因于排名。', '',
    '后续可研究温和资金分配、给新强势标的留出机会，以及带滞后的仓位替换规则。这些方向本轮没有测试。当前保留原策略，集中版仅作为研究候选；结果依赖观察池和起点，重叠窗口不代表独立证据。', '',
    '19 个组合窗口、五组策略与持有，共 114 行对比。90 次新回测，5 组原三币组合基准复用上一轮逐单核对结果。初始资金 1000 USDT，现货，每侧费用 0.1%，无滑点，截至 2026-10-06；日终盯市收益及最大回撤包含浮亏，终点人工强平另计现金账。每个窗口独立开户。', '',
    '## 原策略入场归因', '',
    '对上一轮 43 个窗口的 1,468 笔持仓，使用初次入场之前最后一个完成日线的标的自身收盘价及 MA150 分类。高于 MA150 为趋势组，否则必须满足高于上升 EMA10 才归入反弹组。全部生命周期的后续加减仓归入初始组，未平仓尾部按窗口终日收盘盯市；两组贡献之和与原期末利润核对。窗口有重叠，不把 1,468 笔当独立样本。', '',
    '下表展示每个单币最长窗口，避免把重叠窗口加总。利润贡献与资金复利及账户风控路径有关，不能视为删除该组后的因果结果。', '',
    '| 窗口 | 初始入场类型 | 持仓数 | 十日内亏损数 | 正常平仓收益中位数 | 含尾部盯市利润贡献（USDT） |',
    '|---|---|---:|---:|---:|---:|']
for row in csv.DictReader((root / 'entry_regime_summary.csv').open()):
    if row['window'] in ['BTC_full_cycle', 'SUI_since_maturity', 'ZEC_full_cycle', 'ADA_full_cycle', 'DOGE_full_cycle', 'AVAX_full_cycle']:
        group = 'MA150 上' if row['group'] == 'above_ma150' else 'MA150 下 EMA10 反弹'
        text.append(f"| {row['window']} | {group} | {row['positions']} | {row['quick_losses']} | {float(row['median_closed_return_pct']):+.2f}% | {float(row['mtm_profit_abs']):+.2f} |")
text += ['', '反弹组快速失败较多，但 SUI、DOGE 的大量利润也从反弹初始入场产生。仅观察亏损次数不足以支持删除，需要对限制后的完整交易及复利路径重新回测。', '',
    '## 事先固定的四组规则', '',
    '原 CycleRisk；仅允许标的信号日收盘严格高于自身 MA150 的新入场；每周只允许 60 日涨幅前两名的新入场；以及两者组合。所有币共用参数，没有按结果搜索参数。', '',
    '每周使用已完成的星期日收盘快照，选出同时满足原标的 risk_on、正成交量及 60 日历史的同行，再按 60 日涨幅排序。组合版还要求快照日标的高于 MA150。并列用交易对字母序。星期一开盘开始使用该名单，整个执行周固定；星期日开盘仍使用上一周快照。BTC 原市场许可及当前日标的条件仍须成立。', '',
    '只过滤新开仓。已有交易即使排名掉出前二也继续按原退出规则持有，因此同时持仓可能超过两个。原账户回撤控制、14 日冷却、真实成交档位、分币初始本金与利润预算、总槽位数全部保留。不将闲置本金重新分给前两名，故入场更少可能增加现金比例、降低市场暴露。回撤下降需要和收益留存、现金比例一起评估。', '',
    '## 追加的集中配置对照', '',
    '观察到入场筛选保留大量现金后，追加相同 60 日前二排名的集中配置版：实际最大两笔持仓，预算改为账户期初本金加全部已平仓利润和未平仓部分已实现利润，再除以两个槽位。未实现利润不作为可支配本金；每次实际买入仍受钱包 max_stake 限制。风控调仓中不重复加入已计入共享预算的部分实现利润。', '',
    '原 BTC/标的退出、账户风险档位及冷却保留；没有排名下降就强制卖出，也没有每日再平衡。因此现金仍可能闲置，旧持仓也可能暂时不属于本周前二。此对照同时改变了槽位和资本共享分配，是对真实集中配置的整体测试，不能把差异全部归因于选币。该版在观察首批筛选结果后追加，属于回溯研究，不是事先固定的首轮四组。', '',
    'core3：BTC/SOL/ETH，七个周期；broad7：BTC/ETH/SOL/ADA/DOGE/AVAX/ZEC，七个周期；broad8：增加 SUI，仅从 2023-10-01 成熟后及 2024/2025/2026/最近窗口测试。历史观察池是事后选择的存续币，存在选择偏差。AVAX 在 2021 年初尚未满 MA150 历史，所有策略一致等待成熟。', '',
    '## 相对原 CycleRisk 的汇总', '',
    '| 范围 | 候选 | 收益更好/更差 | 回撤更低 | 同时改善 | 期末资金比中位数 | 最差资金比 | 最大回撤恶化 | 现金占比变化中位数 |',
    '|---|---|---:|---:|---:|---:|---:|---:|---:|']
for row in aggregate:
    text.append(f"| {row['universe']} ({row['windows']}) | {labels[row['strategy']]} | {row['return_better']}/{row['return_worse']} | {row['drawdown_better']} | {row['jointly_better']} | {row['median_wealth_ratio']:.4f} | {row['worst_wealth_ratio']:.4f} | {row['max_drawdown_increase_pp']:+.2f}pp | {row['median_cash_change_pp']:+.2f}pp |")
text += ['', '窗口及观察池有重叠，上述数量是描述统计，未表示独立样本显著性。', '',
    '## 全部窗口', '', '每格为累计收益 / 最大回撤 / 平均现金占权益比例。', '',
    '| 窗口 | ' + ' | '.join(labels[n] for n in names) + ' |', '|---|' + '---:|' * len(names)]
for w in windows:
    cells = [f"{float(index[w['label'], n]['return_pct']):+.2f}% / {float(index[w['label'], n]['wallet_drawdown_pct']):.2f}% / {float(index[w['label'], n]['mean_idle_cash_pct']):.1f}%" for n in names]
    text.append('| ' + w['label'] + ' | ' + ' | '.join(cells) + ' |')
text += ['', '## 检查与限制', '',
    f"{preflight['count']} 项规则/历史截断检查及 {concentrated_checks['count']} 项集中预算检查通过；实际成交初次入场逐项核验 {rank_checks} 次排名及 {trend_checks} 次 MA150 条件。原风险控制器前日权益逐日核对；现金账与引擎余额最大误差 {max_error:.10g} USDT，原交易分类利润贡献最大误差 {diagnostic['max_attribution_error']:.10g} USDT。数据和策略哈希未变。", '',
    '历史已经在前几轮查看过，本轮是固定参数的回溯实验；没有严格样本外证据。仅采用有限观察池、无滑点，不保证实盘或更广标的有效。所有候选仅在 validation 目录，未改生产策略或运行服务。', '',
    '`summary.csv` 为全部结果；`comparison.csv` 为逐窗口差异；`entry_regime_trades.csv` 为初始入场分类明细；`position_audit.csv` 显示持仓数与固定预算槽位。']
(root / 'REPORT.md').write_text('\n'.join(text) + '\n')
print(json.dumps(verification, indent=2))
for row in aggregate:
    if row['universe'] == 'all': print(row)
