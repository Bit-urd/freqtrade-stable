"""Merge candidate measurements with the three unchanged reference profiles."""
import csv
import json
import statistics
from pathlib import Path
root=Path(__file__).resolve().parents[2]
folder=root/'archive/portfolio_improvement'
reference=list(csv.DictReader((root/'single_coin_comparison/summary.csv').open()))
candidate=list(csv.DictReader((folder/'summary.csv').open()))
assert len(candidate)==20 and len(reference)==40
rows=reference+[r for r in candidate if r['strategy']!='BuyAndHold']
for r in candidate:
    if r['strategy']=='BuyAndHold':
        old=next(x for x in reference if x['pair']==r['pair'] and x['strategy']=='BuyAndHold')
        for k in ['return_pct','wallet_drawdown_pct']:
            assert abs(float(old[k])-float(r[k]))<1e-8
with (folder/'comparison.csv').open('w') as out:
    w=csv.DictWriter(out,fieldnames=list(reference[0]));w.writeheader();w.writerows(rows)
names={'Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio（正式）',
       'BtcTrendPhasedStrategy':'分阶段版', 'BtcTrendFastExitStrategy':'快速退出版',
       'BtcPortfolioImprovedStrategy':'改进候选', 'BuyAndHold':'持有'}
lines=['# Portfolio 正式版与独立改进候选对照','',
       '原 Portfolio 已按用户要求标注为正式版；原算法未修改。Phased/FastExit 保留为对照，改进候选不自动晋升。', '',
       '十个单币独立回测，2022-11-21～2025-10-07；每组 1000 USDT、一个槽位、现货、单边费用 0.1%。采用相同每日收盘权益口径。三组基准复用此前冻结结果，候选重新跑十组；持有结果逐币核对一致。', '',
       '候选保留原版 MA200 牛熊过滤、个币 EMA20/50 与周线风控、熊市分档积累。牛市/交接后：日线转弱而周线仍强时先减至半槽位；BTC 两天站上 MA200、该币价格/均线向上且周线多头时恢复满槽位；BTC 弱两天或个币日线弱两天且周线弱时清仓。所有新增决策使用已收盘日线；减仓按市场价值换算成本量，仓位状态只在成交后更新。', '',
       '这是两个机制组合后的首次候选结果，不能据此归因各项贡献；没有按币调参，也没有参数搜索。','',
       '| 单币 | Portfolio 收益 / 回撤 | 分阶段版 | 快速退出版 | 改进候选 | 持有 |',
       '|---|---:|---:|---:|---:|---:|']
for pair in json.loads((folder/'plan.json').read_text())['pairs']:
    cells=[]
    for name in names:
        r=next(x for x in rows if x['pair']==pair and x['strategy']==name)
        cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
    lines.append('| '+pair.split('/')[0]+' | '+' | '.join(cells)+' |')
lines+=['','| 策略 | 收益中位数 | 回撤中位数 | 最差回撤 | 严格联合达标 |','|---|---:|---:|---:|---:|']
aggregate={}
for name,label in names.items():
    rr=[r for r in rows if r['strategy']==name]
    agg=dict(median_return_pct=statistics.median(float(r['return_pct']) for r in rr),
             median_drawdown_pct=statistics.median(float(r['wallet_drawdown_pct']) for r in rr),
             worst_drawdown_pct=max(float(r['wallet_drawdown_pct']) for r in rr),
             joint_passes=sum(r['joint_target_met']=='True' for r in rr) if name!='BuyAndHold' else None)
    aggregate[name]=agg
    lines.append(f"| {label} | {agg['median_return_pct']:+.2f}% | {agg['median_drawdown_pct']:.2f}% | {agg['worst_drawdown_pct']:.2f}% | {str(agg['joint_passes'])+'/10' if name!='BuyAndHold' else '—'} |")
lines+=['','联合达标：收益至少为持有收益的 2/3 且回撤严格低于持有。用户允许近似，表格采用严格阈值以便复现。','',
        '正式身份是用户指定，不代表 Portfolio 在所有币和周期都最优。候选若退步则保留结果作为研究记录，不替换正式版。跨币测试仍使用已观察的时间样本，未计额外滑点；十币中位数不是十币组合收益。', '',
        '复现：run_portfolio_improvement.py；汇总：make_portfolio_improvement_report.py。comparison.csv 包含五组完整指标；源文件校验见 source_manifest.json，成交现金流核对见 results/*/completed.json。']
lines += ['', '## 本轮结论', '', '改进候选严格联合达标 3/10（BNB、ADA、AVAX），少于 Portfolio 的 5/10；9/10 收益低于 Portfolio（仅 XRP 略高），9/10 回撤高于 Portfolio（仅 XRP 略低）。此次两机制组合不作为升级版本。下一步应分别测试恢复补仓和普通回调减仓，避免将失败组合继续叠加调参。']
(folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
(folder/'aggregate.json').write_text(json.dumps(aggregate,indent=2)+'\n')
print(json.dumps(aggregate,indent=2))
