"""Write paired single-coin returns, drawdowns and hold-relative target counts."""
import csv
import json
import statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'single_coin_comparison'
plan=json.loads((ROOT/'plan.json').read_text());names=plan['strategies'];pairs=plan['pairs']
labels={'BtcTrendPhasedStrategy':'原分阶段版','BtcTrendFastExitStrategy':'快速退出版','Ma200BtcRegimeFullCyclePortfolioStrategy':'原 Portfolio','BuyAndHold':'单币持有'}
rows=list(csv.DictReader((ROOT/'summary.csv').open()))
lookup={(r['pair'],r['strategy']):r for r in rows}
complete=[p for p in pairs if all((p,n) in lookup for n in names+['BuyAndHold'])]
lines=['# 十组单币策略与持有对比','',f'完成 {len(complete)}/10 组；每组仅一个交易币，三个策略分别独立开始。区间 2022-11-21～2025-10-07。','', '每组初始 1000 USDT，max_open_trades=1，现货，单边手续费 0.1%。BTC 日线作为所有组的大盘信号；非 BTC 组不交易 BTC、不占 BTC 仓位。三版策略参数冻结，没有为不同币调参。','', '收益为累计利润率，回撤按每日收盘总权益。单币持有在同一起点开盘投入全部预算、扣买入手续费，之后不交易；期末按同一收盘估值。双方终点均未扣盯市持仓卖出费，清算收益在 CSV 另列。','', '| 单币 | 原分阶段版 收益 / 回撤 | 快速退出版 收益 / 回撤 | Portfolio 收益 / 回撤 | 持有 收益 / 回撤 |','|---|---:|---:|---:|---:|']
for pair in complete:
    values=[f"{float(lookup[pair,n]['return_pct']):+.2f}% / {float(lookup[pair,n]['wallet_drawdown_pct']):.2f}%" for n in names+['BuyAndHold']]
    lines.append('| '+pair.split('/')[0]+' | '+' | '.join(values)+' |')
aggregate=[]
for n in names+['BuyAndHold']:
    rs=[lookup[p,n] for p in complete];positives=[x for x in rs if float(x['hold_return_pct'])>0]
    if not rs:continue
    aggregate.append({'strategy':n,'groups':len(rs),'median_return_pct':statistics.median(float(x['return_pct']) for x in rs),'median_drawdown_pct':statistics.median(float(x['wallet_drawdown_pct']) for x in rs),'worst_return_pct':min(float(x['return_pct']) for x in rs),'worst_drawdown_pct':max(float(x['wallet_drawdown_pct']) for x in rs),'profitable_groups':sum(float(x['return_pct'])>0 for x in rs),'return_better_than_hold_groups':sum(float(x['return_pct'])>float(x['hold_return_pct']) for x in rs) if n!='BuyAndHold' else None,'drawdown_better_than_hold_groups':sum(float(x['wallet_drawdown_pct'])<float(x['hold_drawdown_pct']) for x in rs) if n!='BuyAndHold' else None,'positive_hold_groups':len(positives),'two_thirds_return_groups':sum(float(x['return_pct'])>=float(x['hold_return_pct'])*2/3 for x in positives) if n!='BuyAndHold' else None,'joint_target_groups':sum(float(x['return_pct'])>=float(x['hold_return_pct'])*2/3 and float(x['wallet_drawdown_pct'])<float(x['hold_drawdown_pct']) for x in positives) if n!='BuyAndHold' else None})
lines+=['','## 跨币汇总','', '| 策略 | 收益中位数 | 回撤中位数 | 最差回撤 | 回撤低于持有 | 收益≥持有 2/3 且回撤更低 |','|---|---:|---:|---:|---:|---:|']
for x in aggregate:
    dd='—' if x['strategy']=='BuyAndHold' else f"{x['drawdown_better_than_hold_groups']}/{x['groups']}"
    joint='—' if x['strategy']=='BuyAndHold' else f"{x['joint_target_groups']}/{x['positive_hold_groups']}"
    lines.append(f"| {labels[x['strategy']]} | {x['median_return_pct']:+.2f}% | {x['median_drawdown_pct']:.2f}% | {x['worst_drawdown_pct']:.2f}% | {dd} | {joint} |")
lines+=['','十个币中，快速退出版的收益中位数最高，但回撤中位数约 60.79%；Portfolio 回撤中位数约 50.04%，严格目标达标 5/10，是这轮跨币测试更符合收益与风险要求的方案。原分阶段版仅 ETH 同时达标；快速退出版为 ETH、DOGE；Portfolio 为 ETH、BNB、ADA、DOGE、AVAX。','', '收益中位数最高不等于目标达标最多；三币组合结论不能直接推广到单币。BTC 组的三版回撤均高于持有，AVAX 两种统一 BTC 趋势版回撤均大于持有，AAVE 三版收益均明显不足持有 2/3。','', '[分币对比图](comparison.png)','', '## 各币目标检查','', '| 单币 | 原分阶段版收益占持有 / 达标 | 快速退出版收益占持有 / 达标 | Portfolio收益占持有 / 达标 |','|---|---:|---:|---:|']
for p in complete:
    vals=[]
    for n in names:
        x=lookup[p,n];fraction=float(x['return_fraction_of_hold']) if x['return_fraction_of_hold'] else None
        met=x['joint_target_met']=='True'
        vals.append(f"{fraction*100:.2f}% / {'是' if met else '否'}" if fraction is not None else '持有亏损，比例不适用')
    lines.append('| '+p.split('/')[0]+' | '+' | '.join(vals)+' |')
lines+=['','## 口径与复现','', 'BTC/ETH/BNB/SOL/XRP/ADA/DOGE/LINK/AVAX/AAVE 是固定研究币池，并非当前市值前十排名。全部标的在起点已有足够历史，不以缺失历史或上市后首日替代共同起点。日线及周线数据、起点前预热审计见 data_audit.json。','', '原始成交现金流对引擎期末资金核对误差必须 <0.05 USDT。每个策略每组均重建实例并重置交易、钱包及 custom data；确认交易记录只有该组一个标的。冻结源文件及校验值见 strategies/ 与 source_manifest.json。','', '这不是十币组合回测，不能把十组收益中位数视为组合收益；单币、单槽位是对资金配置方式的明确变更，和此前三币组合结果不应直接混用。','', '同一区间跨币测试用于观察参数可迁移性，不等于全新时间样本外验证；币池存在选择偏差，未额外加入滑点。','', '运行 /research/run_single_coin_comparison.py；汇总 /research/make_single_coin_report.py。原始指标见 summary.csv；成交与日线权益见 results/。configs/ 提供各组一个标的的独立配置，基础 config.json 是批量运行器输入，不是十币组合的测量结果。新下载的 DOGE/LINK/AVAX 日线、周线已保存在 user_data/data/binance，下载日志见 download.log。','']
(ROOT/'REPORT.md').write_text('\n'.join(lines))
(ROOT/'aggregate.json').write_text(json.dumps(aggregate,indent=2,ensure_ascii=False)+'\n')
with (ROOT/'aggregate.csv').open('w') as out:
    writer=csv.DictWriter(out,fieldnames=list(aggregate[0]),lineterminator='\n');writer.writeheader();writer.writerows(aggregate)
print(f'{len(complete)}/10 groups complete')
for x in aggregate: print(x)
