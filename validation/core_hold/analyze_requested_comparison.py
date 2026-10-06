"""Analyze the requested 3-coin range without altering earlier reports."""
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import analyze as accounting

ROOT = Path('/research')
FOLDER = ROOT/'btc_sol_eth_20221121_20251007'
config = json.loads((FOLDER/'config.json').read_text())
accounting.PAIRS = config['exchange']['pair_whitelist']
accounting.HISTORY = {pair: accounting.HISTORY[pair] for pair in accounting.PAIRS}
archive = sorted(FOLDER.glob('*.zip'))[-1]
with ZipFile(archive) as z:
    name = next(n for n in z.namelist() if n.endswith('.json')
                and not n.endswith('_config.json') and 'strategy' not in n)
    payload = json.loads(z.read(name))
results = payload['strategy']
example = next(iter(results.values()))
start = pd.to_datetime(example['backtest_start_ts'], unit='ms', utc=True).floor('D')
end = pd.to_datetime(example['backtest_end_ts'], unit='ms', utc=True).floor('D')
assert start == pd.Timestamp('2022-11-21', tz='UTC'), start
assert end == pd.Timestamp('2025-10-07', tz='UTC'), end
dates = pd.date_range(start, end, freq='D')
bench = accounting.benchmark(dates)
bench.to_csv(FOLDER/'equity_BuyAndHold.csv')
rows = [{'strategy':'BuyAndHold', **accounting.stats(bench)}]
for name, result in results.items():
    curve, terminal_cash, events = accounting.ledger(result['trades'], dates)
    delta = terminal_cash-result['final_balance']
    assert abs(delta) < .05, (name,delta)
    curve.to_csv(FOLDER/f'equity_{name}.csv')
    rows.append({'strategy':name, **accounting.stats(curve),
                 'engine_final_balance':result['final_balance'],
                 'ledger_reconciliation_error':delta, 'trades':result['total_trades']})
frame = pd.DataFrame(rows)
frame['return_gap_vs_hold_pp'] = frame.return_pct-rows[0]['return_pct']
frame['equity_gap_vs_hold_usdt'] = frame.ending_equity-rows[0]['ending_equity']
frame['liquidated_gap_vs_hold_pp'] = frame.liquidated_return_pct-rows[0]['liquidated_return_pct']
frame.to_csv(FOLDER/'summary.csv',index=False)
coin_rows=[]
for pair,hist in accounting.HISTORY.items():
    open_rate=float(hist.loc[start,'open'])
    close_rate=float(hist.loc[end,'close'])
    budget=accounting.CAPITAL/len(accounting.PAIRS)
    quantity=budget/(1+accounting.FEE)/open_rate
    coin_rows.append({'pair':pair,'entry_open':open_rate,'terminal_close':close_rate,
                      'initial_budget':budget,'quantity':quantity,
                      'ending_equity':quantity*close_rate,
                      'return_pct':(quantity*close_rate/budget-1)*100})
pd.DataFrame(coin_rows).to_csv(FOLDER/'benchmark_coins.csv',index=False)
labels={'BuyAndHold':'BTC/SOL/ETH 等权持有',
        'Ma200BtcRegimeFullCyclePortfolioStrategy':'原 Portfolio',
        'Ma200BtcRegimeFullCycleCoreHoldStrategy':'默认 CoreHold（50% / 2 天）'}
lines=['# BTC / SOL / ETH：20221121-20251007', '',
       '原 Portfolio 是 `Ma200BtcRegimeFullCyclePortfolioStrategy`，来源文件为 '
       '`user_data/strategies/ma200_btc_regime_full_cycle_portfolio_strategy.py`。', '',
       '仅使用 BTC/USDT、SOL/USDT、ETH/USDT，max_open_trades=3。'
       '初始资金 1,000 USDT，可用资金比例 100%，单边手续费 0.1%。'
       '日线时间为 UTC；范围包括 2022-11-21 和 2025-10-07 两根日线。', '',
       '基准在 2022-11-21 开盘各投入 1/3 初始资金（含买入手续费），之后不再平衡。'
       '三币在起点前均有充分历史，无需为未上市币保留现金。', '',
       '| 方案 | 期末盯市权益 | 盯市收益 | 扣期末卖出手续费收益 | 最大组合回撤 | 平均现金占比 |',
       '|---|---:|---:|---:|---:|---:|']
for row in rows:
    lines.append(f"| {labels[row['strategy']]} | {row['ending_equity']:.2f} USDT | "
                 f"{row['return_pct']:+.2f}% | {row['liquidated_return_pct']:+.2f}% | "
                 f"{row['wallet_drawdown_pct']:.2f}% | {row['mean_idle_cash_pct']:.2f}% |")
lines += ['', '## 与持有的差距', '']
for _, row in frame[frame.strategy!='BuyAndHold'].iterrows():
    lines.append(f"- {labels[row.strategy]}：收益差 {row.return_gap_vs_hold_pp:+.2f} 个百分点，"
                 f"期末权益差 {row.equity_gap_vs_hold_usdt:+.2f} USDT（策略减持有）。"
                 f"双方均扣期末卖出费后的收益差为 {row.liquidated_gap_vs_hold_pp:+.2f} 个百分点。")
lines += ['', '## 各币持有贡献', '',
          '| 币 | 起点开盘价 | 终点收盘价 | 持有收益（含买入费用） | 期末权益 |',
          '|---|---:|---:|---:|---:|']
for row in coin_rows:
    lines.append(f"| {row['pair']} | {row['entry_open']:.6f} | {row['terminal_close']:.6f} | "
                 f"{row['return_pct']:+.2f}% | {row['ending_equity']:.2f} USDT |")
lines += ['', '## 估值与复现', '',
          '主比较剔除引擎在结束时自动执行的 force_exit 卖单，'
          '以现金加剩余代币乘 2025-10-07 日线收盘价计算总权益。'
          '已实现利润已体现在现金流中，不重复添加。另列统一扣除期末卖出手续费的收益。', '',
          '全部成交现金流（包含 force_exit）与引擎 final_balance 核对，误差小于 0.05 USDT。'
          '逐日权益曲线用于计算最大回撤，包含持仓浮盈亏。', '',
          '复现：使用父目录 README.md 的相同 Docker 挂载和镜像，运行 '
          '`/research/run_requested_comparison.py`。配置见 config.json，'
          '完整执行参数见 command.json，统计见 summary.csv，逐日权益见 equity_*.csv。', '',
          '这是指定历史区间的回顾性比较，采用日线开盘成交模拟，不包含额外滑点。'
          '只改变本次独立回测的币池与槽位数，运行中的交易配置未修改。', '']
(FOLDER/'REPORT.md').write_text('\n'.join(lines))
print(frame.to_string(index=False))
print(f'Actual daily valuation range: {start} through {end}')
