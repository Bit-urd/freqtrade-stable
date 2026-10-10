"""Generate first-available buy-and-hold and compare all frozen cases."""
import csv
import gzip
import hashlib
import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

D = Path(__file__).resolve().parent
P = json.loads((D / 'protocol.json').read_text())
RAW = D.parent / 'requested_27_half_year_20261008/raw/spot'
history = {}
for asset in P['groups'][:-1]:
    history[asset] = {datetime.fromtimestamp(r[0]/1000, timezone.utc).date(): r
                      for r in json.loads((RAW / (asset+'.json')).read_text())}

def hold(group, year):
    assets = list(history) if group == 'six_portfolio' else [group]
    start = datetime(year, 1, 1).date()
    end = datetime(2026, 10, 6).date()
    cash = 1000.
    quantities = {}
    purchases = {}
    for asset in assets:
        available = [day for day in history[asset] if start <= day <= end]
        if available:
            first = min(available)
            purchases.setdefault(first, []).append(asset)
    rows = []
    day = start
    peak = 1000.
    dd = 0.
    exposure = []
    while day <= end:
        for asset in purchases.get(day, []):
            budget = 1000./len(assets)
            cash -= budget
            quantities[asset] = budget/1.001/float(history[asset][day][1])
        equity = cash + sum(q*float(history[a][day][4]) for a, q in quantities.items())
        peak = max(peak, equity)
        dd = max(dd, (1-equity/peak)*100)
        exposure.append((1-cash/equity)*100)
        rows.append({'date':str(day),'cash':cash,'equity':equity})
        day += timedelta(days=1)
    out = D/group/'results'/('start_'+str(year))/'ImmediateHold_equity.csv'
    with out.open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    cagr=((equity/1000)**(365.25/len(rows))-1)*100
    return {'return_pct':(equity/1000-1)*100,'wallet_drawdown_pct':dd,
            'ending_equity':equity,'cagr_pct':cagr,'calmar':cagr/dd if dd else 0,
            'exposure_pct':statistics.mean(exposure),
            'purchase_dates':{a:str(min(day for day, aa in purchases.items() if a in aa)) for a in quantities}}

assert json.loads((D/'COMPLETED.json').read_text())['native_runs']==41
audit=json.loads((D/'all_stages_audit.json').read_text())
assert audit['all_passed'] and audit['native_runs_audited']==41
rows=list(csv.DictReader((D/'summary.csv').open()))
cases=[]
for group in P['groups']:
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (D/group/'strategies').glob('*.py')}
    assert actual==P['source_sha256']
    for year in range(2021,2026):
        r=next(r for r in rows if r['group']==group and r['window']=='start_'+str(year) and r['strategy']==P['strategy'])
        old=next(r for r in rows if r['group']==group and r['window']=='start_'+str(year) and r['strategy']=='BuyAndHold')
        b=hold(group,year)
        c={'group':group,'year':year,**{'strategy_'+k:float(r[k]) for k in ['return_pct','wallet_drawdown_pct','ending_equity','cagr_pct','calmar','exposure_pct']},**{'hold_'+k:v for k,v in b.items()},'warmup_hold_return_pct':float(old['return_pct']),'warmup_hold_dd_pct':float(old['wallet_drawdown_pct'])}
        c['return_delta_pp']=c['strategy_return_pct']-c['hold_return_pct']
        c['dd_delta_pp']=c['strategy_wallet_drawdown_pct']-c['hold_wallet_drawdown_pct']
        c['wealth_ratio']=c['strategy_ending_equity']/c['hold_ending_equity']
        trades=json.load(gzip.open(D/group/'results'/r['window']/(P['strategy']+'_trades.json.gz'),'rt'))
        extra=[o for t in trades for o in t['orders'] if o['order_filled_timestamp'] is not None and o['ft_is_entry'] and str(o.get('ft_order_tag','')).startswith('idle_cash:')]
        c['supplemental_orders']=len(extra)
        c['supplemental_stake_usdt']=sum(float(o['amount'])*float(o['safe_price']) for o in extra)
        cases.append(c)
with (D/'comparison.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
counts={}
for group in P['groups']:
    cc=[c for c in cases if c['group']==group]
    counts[group]={'return_wins':sum(c['return_delta_pp']>1e-8 for c in cc),'dd_lower':sum(c['dd_delta_pp']<-1e-8 for c in cc),'calmar_wins':sum(c['strategy_calmar']>c['hold_calmar'] for c in cc),'median_wealth_ratio':statistics.median(c['wealth_ratio'] for c in cc)}
(D/'findings.json').write_text(json.dumps(counts,indent=2))
lines=['# 当前补仓策略与持有：六币单独及组合对比','',
       '策略为 Ma200CashSupplementStrategy，沿用已冻结代码，不改指标参数。BTC、ETH、SOL、LINK、XRP、ADA 各单独运行及六币组合，2021—2025共35次原生回测（另有此前完成的6次2020单币记录）。各起点独立1000 USDT，手续费0.1%，终点2026-10-06，无充值。组合同时持仓6个槽位，单币1个槽位；单币仍以BTC判断市场状态。', '',
       '主持有基准：起点首个可用日线开盘买入并一直持有，新币上市前其等权份额留现金，组合不再平衡。2020起点按用户要求取消，已完成的2020单币记录不纳入主报告统计。另附等待61根日线后买入的旧口径，便于与此前报告核对。', '',
       '收益及回撤采用逐日收盘净值，计开仓费用，期末未假设卖出；策略原生强制退出费用另行对账。涨跌幅均为累计收益，pp为百分点。', '',
       '| 标的 | 收益跑赢持有 | 回撤低于持有 | Calmar更高 | 期末资金比中位数 |','|---|---:|---:|---:|---:|']
for group,v in counts.items():
    lines.append(f"| {group} | {v['return_wins']}/5 | {v['dd_lower']}/5 | {v['calmar_wins']}/5 | {v['median_wealth_ratio']:.3f} |")
for group in P['groups']:
    lines.extend(['', '## '+group,'','| 起点 | 策略收益 | 持有收益 | 收益差pp | 策略回撤 | 持有回撤 | 策略CAGR | 持有CAGR | 策略Calmar | 持有Calmar |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|'])
    for c in cases:
        if c['group']!=group:continue
        lines.append(f"| {c['year']} | {c['strategy_return_pct']:+.2f}% | {c['hold_return_pct']:+.2f}% | {c['return_delta_pp']:+.2f} | {c['strategy_wallet_drawdown_pct']:.2f}% | {c['hold_wallet_drawdown_pct']:.2f}% | {c['strategy_cagr_pct']:.2f}% | {c['hold_cagr_pct']:.2f}% | {c['strategy_calmar']:.3f} | {c['hold_calmar']:.3f} |")
lines.extend(['','## 旧预热持有口径','','| 标的 | 起点 | 首日可用持有收益 | 61日预热持有收益 |','|---|---:|---:|---:|'])
for c in cases:lines.append(f"| {c['group']} | {c['year']} | {c['hold_return_pct']:+.2f}% | {c['warmup_hold_return_pct']:+.2f}% |")
lines.extend(['','## 额外补仓成交','','| 标的 | 起点 | 额外补仓笔数 | 累计投入U |','|---|---:|---:|---:|'])
for c in cases:lines.append(f"| {c['group']} | {c['year']} | {c['supplemental_orders']} | {c['supplemental_stake_usdt']:.2f} |")
lines.extend(['','没有额外补仓成交的案例，其表现体现底层交接策略，不证明补仓机制创造了收益；累计补仓金额包含重复资金使用，不代表充值额。'])
contrib=list(csv.DictReader((D/'all_stages_contributions.csv').open()))
lines.extend(['','## 六币组合收益贡献','','每币贡献来自组合实际成交及期末收盘估值，不是单币独立回测收益。用于检查是否被SOL等单币主导。','','| 起点 | BTC贡献U | ETH贡献U | SOL贡献U | LINK贡献U | XRP贡献U | ADA贡献U |','|---|---:|---:|---:|---:|---:|---:|'])
for year in range(2021,2026):
    file='six_portfolio/results/start_'+str(year)+'/'+P['strategy']+'_trades.json.gz'
    profit={r['pair'].split('/')[0]:float(r['profit_usdt']) for r in contrib if r['file']==file}
    lines.append('| '+str(year)+' | '+' | '.join(f"{profit.get(a,0):+.2f}" for a in history)+' |')
lines.extend(['','## 验证及限制','',f"全部41次已完成回测成交净值独立重建通过，其中主报告35次，最大误差{audit['max_error']:.3g} USDT；冻结源文件哈希全部一致。组合从实际成交重建，不能用六个单币收益平均代替。五个起点高度重叠，币种选择有幸存者偏差，结果不代表未来收益保证。没有充值，因此本报告检验策略择时与资金分配，不能用于证明工资定投效果。当前候选未部署。"])
(D/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(counts,indent=2))
