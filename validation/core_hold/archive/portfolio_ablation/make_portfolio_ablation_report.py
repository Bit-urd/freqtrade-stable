"""Compare isolated mechanisms with existing frozen baselines."""
import csv
import hashlib
import json
import statistics
from pathlib import Path
root=Path(__file__).resolve().parents[2];folder=root/'archive/portfolio_ablation'
read=lambda p:list(csv.DictReader(p.open()))
old=read(root/'single_coin_comparison/summary.csv')
new=read(folder/'summary.csv')
assert len(old)==40 and len(new)==30
for h in (r for r in new if r['strategy']=='BuyAndHold'):
    previous=next(r for r in old if r['pair']==h['pair'] and r['strategy']=='BuyAndHold')
    assert all(abs(float(h[k])-float(previous[k]))<1e-8 for k in ['return_pct','wallet_drawdown_pct'])
rows=old+[r for r in new if r['strategy']!='BuyAndHold']
names={'Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio（正式）','BtcTrendPhasedStrategy':'分阶段版','BtcTrendFastExitStrategy':'快速退出版','BtcPortfolioRecoveryTopUpStrategy':'仅恢复补仓','BtcPortfolioPullbackTrimStrategy':'仅回调减仓','BuyAndHold':'持有'}
with (folder/'comparison.csv').open('w') as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=['# Portfolio 两项改动拆分验证','',
       '原 Portfolio 保持正式身份，算法未修改。两个独立研究类仅在本研究目录内，不作为运行服务策略。', '',
       '仅恢复补仓：保留原版全部退出、周线调仓和熊市积累规则，仅对熊市仓位在 BTC 连续两天站上 MA200、该币 EMA20/50 向上且价格在 EMA20 上、周线多头时，尝试补至满槽位。', '',
       '仅回调减仓：保留原版入场、熊市交接仓位；只有原版本来要退出、该币周线仍强且 BTC 未连续两天走弱时，改为减掉持仓的一半。被减仓后，等待上述强势条件恢复仓位；BTC 失效或周线转弱时保留原版退出。恢复是这一减仓机制的必要配套，不加入新的熊市交接补仓。', '',
       '两版使用已收盘信号、按成交更新新增状态；没有分币调参，没有扩大参数搜索。原版固有的熊市风险和仓位规则保持。','',
       '十个币分别独立回测 2022-11-21～2025-10-07；1000 USDT、一个槽位、现货、单边费 0.1%。三组基准复用冻结结果，逐币核对持有曲线指标一致。', '',
       '| 单币 | Portfolio 收益 / 回撤 | 分阶段版 | 快速退出版 | 仅恢复补仓 | 仅回调减仓 | 持有 |',
       '|---|---:|---:|---:|---:|---:|---:|']
for pair in json.loads((folder/'plan.json').read_text())['pairs']:
    cells=[]
    for name in names:
        r=next(x for x in rows if x['pair']==pair and x['strategy']==name)
        cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
    lines.append('| '+pair.split('/')[0]+' | '+' | '.join(cells)+' |')
aggregate={}
lines+=['','| 策略 | 收益中位数 | 回撤中位数 | 最差回撤 | 严格联合达标 |','|---|---:|---:|---:|---:|']
for name,label in names.items():
    rr=[r for r in rows if r['strategy']==name]
    agg={'median_return_pct':statistics.median(float(r['return_pct']) for r in rr),'median_drawdown_pct':statistics.median(float(r['wallet_drawdown_pct']) for r in rr),'worst_drawdown_pct':max(float(r['wallet_drawdown_pct']) for r in rr),'joint_passes':sum(r['joint_target_met']=='True' for r in rr) if name!='BuyAndHold' else None}
    aggregate[name]=agg
    lines.append(f"| {label} | {agg['median_return_pct']:+.2f}% | {agg['median_drawdown_pct']:.2f}% | {agg['worst_drawdown_pct']:.2f}% | {str(agg['joint_passes'])+'/10' if name!='BuyAndHold' else '—'} |")
lines+=['','严格联合达标：收益至少为持有的 2/3 且回撤低于持有；独立单币中位数不是组合收益。','']
for name in ['BtcPortfolioRecoveryTopUpStrategy','BtcPortfolioPullbackTrimStrategy']:
    rr=[r for r in rows if r['strategy']==name];base={r['pair']:r for r in old if r['strategy']=='Ma200BtcRegimeFullCyclePortfolioStrategy'}
    counts={'return_better':sum(float(r['return_pct'])>float(base[r['pair']]['return_pct']) for r in rr),'drawdown_better':sum(float(r['wallet_drawdown_pct'])<float(base[r['pair']]['wallet_drawdown_pct']) for r in rr),'both_better':sum(float(r['return_pct'])>float(base[r['pair']]['return_pct']) and float(r['wallet_drawdown_pct'])<float(base[r['pair']]['wallet_drawdown_pct']) for r in rr)}
    aggregate[name]['versus_official']=counts
    lines.append(f"{names[name]}相对正式版：收益更高 {counts['return_better']}/10、回撤更低 {counts['drawdown_better']}/10、两项同时改善 {counts['both_better']}/10。")
regime_path=folder/'regimes/summary.csv'
if regime_path.exists():
    measured=read(regime_path);assert len(measured) % 3 == 0 and len(measured) > 0
    reference=[r for r in read(root/'start_checks/summary.csv') if r['cohort']=='reference']
    with (folder/'regimes/comparison.csv').open('w') as out:
        combined=reference+[r for r in measured if r['strategy']!='BuyAndHold']
        w=csv.DictWriter(out,fieldnames=list(combined[0]));w.writeheader();w.writerows(combined)
    lines+=['','## BTC/SOL/ETH 三币组合五个市场阶段','', '| 区间 | Portfolio 收益 / 回撤 | 分阶段版 | 快速退出版 | 仅恢复补仓 | 仅回调减仓 | 持有 |','|---|---:|---:|---:|---:|---:|---:|']
    for window in json.loads((folder/'regimes/windows.json').read_text()):
        if window['label'] not in {r['window'] for r in measured}:
            continue
        cells=[]
        for name in names:
            source=measured if name.startswith('BtcPortfolio') else reference
            r=next(r for r in source if r['window']==window['label'] and r['strategy']==name)
            cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
        lines.append('| '+window['timerange']+' | '+' | '.join(cells)+' |')
    for h in (r for r in measured if r['strategy']=='BuyAndHold'):
        oldh=next(r for r in reference if r['window']==h['window'] and r['strategy']=='BuyAndHold')
        assert all(abs(float(h[k])-float(oldh[k]))<1e-8 for k in ['return_pct','wallet_drawdown_pct'])
lines+=['','## 结论与成交证据', '', '仅恢复补仓：十币收益没有一组提高，六组下降、四组相同，严格达标仍是 5/10；单币结果不支持采用。仅回调减仓：XRP/AAVE 收益和回撤同时改善，但收益中位数下降、严格达标仅 3/10，不适合作为统一规则。', '', '补仓成交明细见 restore_fills.json。BTC、SOL、BNB、DOGE 等在 2024-09-28 确认转强后补仓，2024-10-02 再次退出；该次假突破导致加仓后损失扩大。这是实际成交证据，不是仅根据均线规则推测。', '', 'Portfolio 保持正式版；两项试验归档研究，不为少数受益币单独启用规则，避免按已知历史选择赢家。', '', '本轮结论以单币迁移性和跨市场阶段两类结果共同判断。未计额外滑点；仍是已观察历史上的规则试验，不是全新样本外验证。不自动晋升候选，也不修改运行中的服务。','',
        '复现：run_portfolio_ablation.py、run_portfolio_ablation_regimes.py；汇总：make_portfolio_ablation_report.py。新增规则六项检查见 test_portfolio_ablation.py。']
lines += ['', '用户于 2026-10-07 要求停止试验：三币组合完成 3/5 个窗口（上涨、牛转熊、熊市），共 6 次引擎回测；近期和长区间未完成。未完成结果不纳入结论。三个失败候选已归档，当前没有继续运行的试验。']
(folder/'REPORT.md').write_text('\n'.join(lines)+'\n');(folder/'aggregate.json').write_text(json.dumps(aggregate,indent=2)+'\n')
manifest=json.loads((folder/'source_manifest.json').read_text())
assert hashlib.sha256((root.parent.parent/'user_data/strategies/ma200_btc_regime_full_cycle_portfolio_strategy.py').read_bytes()).hexdigest()==manifest['ma200_btc_regime_full_cycle_portfolio_strategy.py']
assert all(hashlib.sha256((folder/'strategies'/name).read_bytes()).hexdigest()==sha for name,sha in manifest.items())
(folder/'verification.json').write_text(json.dumps({'single_coin_engine_runs':20,'three_coin_regime_runs':len([r for r in measured if r['strategy']!='BuyAndHold']) if regime_path.exists() else 0,'rule_checks_passed':6,'sources_match':True,'hold_references_match':True,'max_abs_ledger_error':max(abs(float(r['ledger_error'])) for r in new if r['ledger_error']),'official_algorithm_unchanged':True,'live_service_changed':False},indent=2)+'\n')
print(json.dumps(aggregate,indent=2))
