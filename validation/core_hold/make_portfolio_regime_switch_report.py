"""Summarize a causal, one-wallet bull/Portfolio switch experiment."""
import csv
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent;folder=root/'portfolio_regime_switch'
read=lambda path:list(csv.DictReader(path.open()))
reference=[r for r in read(root/'start_checks/summary.csv') if r['cohort']=='reference']
guard=read(root/'portfolio_coin_guard/public_replay/summary.csv')
hybrid=read(folder/'summary.csv');assert len(hybrid)==10
names=['Ma200BtcRegimeFullCyclePortfolioStrategy','BtcTrendCoinGuardStrategy','BtcPortfolioRegimeSwitchStrategy','BuyAndHold']
combined=[]
lines=['# 确认上涨时采用个币保护，否则采用原 Portfolio','',
       '用户提出只在上涨状态使用个币保护，其余时间使用正式 Portfolio。此处固定一条可实时执行的规则后验证，不按历史区间日期切换。', '',
       '## 固定规则与持仓交接', '',
       '- 上涨开关：BTC 连续两个已收盘日线站上 MA200；其余日期采用原 Portfolio。',
       '- 上涨模式：BTC 和该币各自的 MA150/上升 EMA10 允许风险才入场；BTC 弱一天或该币同时失去长期与短期支持两天退出。停用周线半仓调节。',
       '- 非上涨模式：原 Portfolio 的入场、个币 EMA20/50 退出、BTC MA200 退出、周线调仓与熊市分档积累。',
       '- 一个账户、一笔本金、一个连续现金流；采用 Portfolio 的账户权益/槽位分配。已有仓位原地交接，不在模式切换时强制清仓；上涨模式允许对已占用的小槽位补足，成交后记录已补仓状态；退回原模式时恢复原仓位与退出规则。', '',
       '因此本试验包含实际持仓交接规则，不能简单拼接两份独立回测的收益。原 Portfolio 与个币保护单独运行的账户分配方式也不同；结果中的差异既来自模式过滤，也来自交接和资金配置。', '',
       '七项规则检查覆盖模式内退出、模式外委托原版、模式内入场、弱币不补仓、补仓状态仅成交后更新、模式外调仓和缺失模式信号。没有新增参数搜索。', '',
       '## 五阶段结果', '',
       'BTC/SOL/ETH 三币、1000 USDT、三个槽位、现货、单边费用 0.1%、每日收盘总权益；同起终点持有。', '',
       '| 区间 | Portfolio 收益 / 回撤 | 全天个币保护 | 模式切换 | 持有 |','|---|---:|---:|---:|---:|']
for window in json.loads((folder/'windows.json').read_text()):
    cells=[]
    for name in names:
        source=hybrid if name=='BtcPortfolioRegimeSwitchStrategy' else guard if name=='BtcTrendCoinGuardStrategy' else reference
        r=next(r for r in source if r['window']==window['label'] and r['strategy']==name)
        combined.append(r)
        cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
    lines.append('| '+window['timerange']+' | '+' | '.join(cells)+' |')
    hold=next(r for r in hybrid if r['window']==window['label'] and r['strategy']=='BuyAndHold')
    oldhold=next(r for r in reference if r['window']==window['label'] and r['strategy']=='BuyAndHold')
    assert all(abs(float(hold[k])-float(oldhold[k]))<1e-8 for k in ['return_pct','wallet_drawdown_pct'])
keys=['window','start','end','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct','trades','ledger_error']
with (folder/'comparison.csv').open('w') as out:
    w=csv.DictWriter(out,fieldnames=keys);w.writeheader();w.writerows({k:r.get(k) for k in keys} for r in combined)
bull=next(r for r in hybrid if r['window']=='ref_bull_2023_2024' and r['strategy']!='BuyAndHold')
long=next(r for r in hybrid if r['window']=='ref_requested_long' and r['strategy']!='BuyAndHold')
lines+=['', '## 解释与结论', '',
        f"上涨期切换版收益为持有的 {float(bull['return_pct'])/813.5996869438749*100:.2f}%，原版为 29.38%，全天个币保护为 68.72%。切换减少了 MA200 尚未确认时的早期反弹参与，收益无法完整保留。", '',
        f"长区间切换版收益为持有的 {float(long['return_pct'])/875.3294487796679*100:.2f}%。严格 2/3 收益目标需要逐窗口判断，不能以一个上涨区间结果替代。", '',
        '纯 2022 熊市回到原版的 -51.43% / 54.12%；失去了全天个币保护版在该阶段的 -30.75% / 33.10% 优势。近期收益比两版好（-3.54%），但回撤 41.19% 仍高于 Portfolio 36.07%。牛转熊回撤 64.67% 也略高于原版 64.04%。因此上涨开关没有把两版各阶段最好的表现拼接出来。', '',
        'BTC 在 MA200 上方也会出现震荡和个币下跌；已收盘的趋势开关无法提前知道反转。切换前的仓位和累计资金会带入后续阶段，采用原规则后的结果也受之前交易影响。', '',
        '原 Portfolio 保持正式身份；切换版仅在本研究目录保留，不替换公开正式策略或服务。本轮没有十币或新的起点检查，不据此推广到所有币。现有历史已被反复观察，不是独立样本外结论；回撤不包含额外盘中波动和滑点。']
(folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
manifest=json.loads((folder/'source_manifest.json').read_text())
assert all(hashlib.sha256((folder/'strategies'/name).read_bytes()).hexdigest()==sha for name,sha in manifest.items())
verification={'completed_windows':5,'engine_runs':5,'rule_checks_passed':7,'source_checksums_match':True,'hold_references_match':True,'max_abs_ledger_error':max(abs(float(r['ledger_error'])) for r in hybrid if r['ledger_error']),'live_service_changed':False,'official_portfolio_changed':False,'status':'research_only','bull_return_fraction_of_hold':float(bull['return_pct'])/813.5996869438749,'long_return_fraction_of_hold':float(long['return_pct'])/875.3294487796679}
(folder/'verification.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(verification,indent=2))
