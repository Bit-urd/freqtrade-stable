"""Build comparisons only from completed, reconciled engine runs."""
import csv
import hashlib
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
rows = list(csv.DictReader((root / 'summary.csv').open()))
index = {(r['window'], r['strategy']): r for r in rows}
windows = json.loads((root / 'windows.json').read_text())
names = ['BtcCoinGuardCycleRiskStrategy', 'Ma200BtcRegimeFullCyclePortfolioStrategy',
         'IndependentHoldCycleRiskStrategy', 'IndependentAtr2CycleRiskStrategy',
         'IndependentAtr3CycleRiskStrategy', 'IndependentAtr4CycleRiskStrategy', 'BuyAndHold']
assert len(rows) == len(windows) * len(names) == 301
assert len(index) == len(rows)
for w in windows:
    assert set(r['strategy'] for r in rows if r['window'] == w['label']) == set(names)
    assert (root / 'results' / w['label'] / 'completed.json').exists()
    if w['pair'] == 'BTC/USDT':
        original = index[w['label'], names[0]]
        for name in names[2:6]:
            for key in ['return_pct', 'wallet_drawdown_pct', 'normal_fills']:
                assert abs(float(index[w['label'], name][key]) - float(original[key])) < 1e-7
            assert int(index[w['label'], name]['atr_stop_exits']) == 0
max_error = max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error'])
assert max_error < .05

comparisons = []
for w in windows:
    hold = index[w['label'], names[2]]
    for name in names[3:6]:
        r = index[w['label'], name]
        comparisons.append(dict(pair=w['pair'], window=w['label'], strategy=name,
            wealth_ratio=float(r['ending_equity']) / float(hold['ending_equity']),
            return_change_pp=float(r['return_pct']) - float(hold['return_pct']),
            drawdown_change_pp=float(r['wallet_drawdown_pct']) - float(hold['wallet_drawdown_pct']),
            atr_stop_exits=int(r['atr_stop_exits'])))
with (root / 'comparison.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=list(comparisons[0])); writer.writeheader(); writer.writerows(comparisons)
aggregates = []
for name in names[3:6]:
    for group in ['non_btc', 'ZEC', 'SUI', 'added_coins', 'portfolio']:
        sub = [r for r in comparisons if r['strategy'] == name and (
            (group == 'non_btc' and r['pair'] != 'BTC/USDT') or
            (group in ['ZEC', 'SUI'] and r['pair'] == group + '/USDT') or
            (group == 'added_coins' and r['pair'] in ['ADA/USDT', 'DOGE/USDT', 'AVAX/USDT']) or
            (group == 'portfolio' and r['pair'] == 'PORTFOLIO'))]
        aggregates.append(dict(strategy=name, group=group, windows=len(sub),
            return_better=sum(r['return_change_pp'] > 1e-6 for r in sub),
            return_worse=sum(r['return_change_pp'] < -1e-6 for r in sub),
            dd_better=sum(r['drawdown_change_pp'] < -1e-6 for r in sub),
            jointly_better=sum(r['return_change_pp'] > 1e-6 and r['drawdown_change_pp'] < -1e-6 for r in sub),
            median_wealth_ratio=statistics.median(r['wealth_ratio'] for r in sub),
            worst_dd_increase_pp=max(r['drawdown_change_pp'] for r in sub),
            stop_exit_count=sum(r['atr_stop_exits'] for r in sub)))
with (root / 'aggregate.csv').open('w') as f:
    writer = csv.DictWriter(f, fieldnames=list(aggregates[0])); writer.writeheader(); writer.writerows(aggregates)

verification = dict(passed=True, windows=43, rows=301, new_atr_strategy_runs=129, baseline_strategy_results=129,
    max_ledger_error=max_error, btc_unchanged=True,
    rule_checks=9, integration_checks=10,
    original_and_hold_reference_reproduction='asserted in run.py',
    caveat='Overlapping in-sample windows are not independent observations; stop counts repeat overlapping trades.')
(root / 'verification.json').write_text(json.dumps(verification, indent=2) + '\n')
manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (root / 'strategies').glob('*.py')}
(root / 'source_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
plan = json.loads((root / 'plan.json').read_text()); plan['status'] = 'completed'; plan.pop('limitations', None)
plan['limitations'] = ['Historical in-sample research, overlapping windows', 'No slippage', 'Daily close stop permits intraday losses and next-open gaps']
(root / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')

original_report = (root / 'REPORT.md').read_text()
original_report = original_report.replace('状态：策略与实验脚本已准备，9 项独立状态机检查通过，完整回测尚未执行。当前 Docker socket 无访问权限；宿主 Python 缺少 pandas、pyarrow 和 Freqtrade 运行依赖，正常 pip 安装也未成功。没有生成或推测收益、回撤、排名。',
    f'状态：完整对比已完成，43 个窗口、129 次新增 ATR 策略回测、129 组上一轮已验证策略基准及 43 个持有基准。前两个 BTC 窗口重新执行原版及例外版验证复现，其余基准沿用固定数据上的已核对结果，并检查策略文件逐字节相同及数据哈希未变。9 项状态机检查与 10 项集成/因果性检查通过。逐单现金账与引擎最终余额最大误差为 {max_error:.10g} USDT；BTC 结果保持一致。')
text = ['\n## 相对上一轮 IndependentHold 的结果\n',
    '窗口相互重叠，胜负数量与止损次数不能当作独立样本或唯一交易数。收益与回撤均来自包含浮盈亏的日终权益。\n',
    '| 参数 | 分组 | 收益更好/更差 | 回撤更低 | 两者同时改善 | 期末权益比中位数 | 最坏回撤增加 | 止损退出次数（含重复窗口） |',
    '|---|---|---:|---:|---:|---:|---:|---:|']
for r in aggregates:
    text.append(f"| ATR{r['strategy'][14]} | {r['group']} ({r['windows']}) | {r['return_better']}/{r['return_worse']} | {r['dd_better']} | {r['jointly_better']} | {r['median_wealth_ratio']:.4f} | {r['worst_dd_increase_pp']:+.2f}pp | {r['stop_exit_count']} |")
text += ['\n## 重点窗口：收益 / 最大回撤\n',
    '| 窗口 | 原 CycleRisk | 原 MA200 | 独立持有例外 | ATR2 | ATR3 | ATR4 | 持有 |',
    '|---|---:|---:|---:|---:|---:|---:|---:|']
for label in ['ZEC_recent', 'ZEC_bull_2023_2024', 'ZEC_full_cycle', 'ZEC_year_2025', 'ZEC_year_2026',
              'SUI_since_maturity', 'SUI_year_2024', 'ADA_full_cycle', 'DOGE_bear_2022', 'AVAX_full_cycle', 'PORTFOLIO_full_cycle']:
    if (label, names[0]) not in index:
        continue
    cells = [f"{float(index[label, n]['return_pct']):+.2f}% / {float(index[label, n]['wallet_drawdown_pct']):.2f}%" for n in names]
    text.append('| ' + label + ' | ' + ' | '.join(cells) + ' |')
text += ['\n完整逐窗口结果见 `summary.csv`；ATR 对例外版差异见 `comparison.csv`。没有按币种选择不同倍数，也未把回测最优参数直接替换生产策略。']
text += ['\n## 全部窗口\n', '| 标的 / 窗口 | 原 CycleRisk | 原 MA200 | 独立持有例外 | ATR2 | ATR3 | ATR4 | 持有 |',
         '|---|---:|---:|---:|---:|---:|---:|---:|']
for window in windows:
    label = window['label']
    cells = [f"{float(index[label, n]['return_pct']):+.2f}% / {float(index[label, n]['wallet_drawdown_pct']):.2f}%" for n in names]
    text.append('| ' + label + ' | ' + ' | '.join(cells) + ' |')
(root / 'REPORT.md').write_text(original_report + '\n'.join(text) + '\n')
print(json.dumps(verification, indent=2))
for r in aggregates:
    if r['group'] == 'non_btc': print(r)
