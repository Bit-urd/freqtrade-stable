import csv
import gzip
import hashlib
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).resolve().parent
R = D.parent
N = R / 'ma200_cash_supplement_six_hold_20261010'
ASSETS = ['BTC', 'ETH', 'LINK', 'XRP', 'ADA']
NEW = 'Ma200CashSupplementStrategy'
OLD = 'CycleRiskOriginalCached'
official = R.parents[1] / 'user_data/strategies/cycle_risk_strategy.py'
official_hash = hashlib.sha256(official.read_bytes()).hexdigest()
assert official_hash == '471bb44d6617be4a5efb7862ef44dbc2f1be499e757f72666ee821893b416228'
newrows = list(csv.DictReader((N/'comparison.csv').open()))
raw = R/'requested_27_half_year_20261008/raw/spot'
checks, rows, sources = [], [], {}

def audit(folder, name, asset, expected):
    trades = json.load(gzip.open(folder/(name+'_trades.json.gz'), 'rt'))
    curve = list(csv.DictReader((folder/(name+'_equity.csv')).open()))
    history = json.loads((raw/(asset+'.json')).read_text())
    prices = {datetime.fromtimestamp(r[0]/1000, timezone.utc).strftime('%Y-%m-%d'):float(r[4]) for r in history}
    flows = defaultdict(list)
    extra = 0
    for trade in trades:
        assert trade['pair'] == asset+'/USDT'
        orders = [o for o in trade['orders'] if o['order_filled_timestamp'] is not None]
        for i, o in enumerate(orders):
            if trade['exit_reason']=='force_exit' and i==len(orders)-1:
                continue
            day=datetime.fromtimestamp(o['order_filled_timestamp']/1000, timezone.utc).strftime('%Y-%m-%d')
            q=float(o['amount']);v=q*float(o['safe_price']);buy=o['ft_is_entry']
            change=-v*(1+float(trade['fee_open'])) if buy else v*(1-float(trade['fee_close']))
            flows[day].append((q if buy else -q,change))
            if buy and str(o.get('ft_order_tag','')).startswith('idle_cash:'):
                extra += 1
    cash=1000.;quantity=0.;error=0.;peak=1000.;dd=0.
    assert curve[0][''][:10] == expected['start']
    assert curve[-1][''][:10] == '2026-10-06'
    for row in curve:
        day=row[''][:10]
        for q,c in flows[day]:quantity+=q;cash+=c
        equity=cash+quantity*prices[day]
        error=max(error,abs(equity-float(row['equity'])),abs(cash-float(row['cash'])))
        peak=max(peak,equity);dd=max(dd,(1-equity/peak)*100)
    assert error<.05
    assert abs((equity/1000-1)*100-float(expected['return_pct']))<1e-6
    assert abs(dd-float(expected['wallet_drawdown_pct']))<1e-6
    checks.append({'asset':asset,'strategy':name,'start':expected['start'],
                   'curve_file':str(folder/(name+'_equity.csv')),
                   'max_reconstruction_error_usdt':error,'supplemental_orders':extra})
    return extra

for asset in ASSETS:
    B = R/'cycle_btc_only_20261009' if asset=='BTC' else R/'cycle_five_single_assets_20261009'/asset
    baseline=list(csv.DictReader((B/'summary.csv').open()))
    assert hashlib.sha256((B/'strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==official_hash
    config=json.loads((B/'config.json').read_text())
    assert config['dry_run_wallet']==1000 and config['fee']==.001 and config['max_open_trades']==1
    assert config['exchange']['pair_whitelist']==[asset+'/USDT']
    hashes={}
    for symbol in {asset,'BTC'}:
        name=symbol+'_USDT-1d.feather'
        h=hashlib.sha256((B/'data'/name).read_bytes()).hexdigest()
        assert h==hashlib.sha256((N/asset/'data'/name).read_bytes()).hexdigest()
        hashes[name]=h
    sources[asset]={'cycle_source_sha256':official_hash,'data_sha256':hashes,
                    'cycle_evidence_directory':str(B),'current_evidence_directory':str(N/asset)}
    for year in range(2021,2026):
        window='start_'+str(year)
        b=next(r for r in baseline if r['window']==window and r['strategy']==OLD)
        n=next(r for r in newrows if r['group']==asset and r['year']==str(year))
        converted={'start':str(year)+'-01-01','return_pct':n['strategy_return_pct'],
                   'wallet_drawdown_pct':n['strategy_wallet_drawdown_pct']}
        audit(B/'results'/window,OLD,asset,b)
        extra=audit(N/asset/'results'/window,NEW,asset,converted)
        row={'asset':asset,'year':year}
        for key in ['return_pct','wallet_drawdown_pct','cagr_pct','calmar','ending_equity','exposure_pct']:
            row['cycle_'+key]=float(b[key]);row['current_'+key]=float(n['strategy_'+key])
        row['return_delta_pp']=row['current_return_pct']-row['cycle_return_pct']
        row['dd_delta_pp']=row['current_wallet_drawdown_pct']-row['cycle_wallet_drawdown_pct']
        row['profit_retention']=row['current_return_pct']/row['cycle_return_pct'] if row['cycle_return_pct']>0 else None
        row['current_supplemental_orders']=extra
        rows.append(row)

counts={}
for asset in ASSETS:
    rr=[r for r in rows if r['asset']==asset]
    counts[asset]={'return_wins':sum(r['return_delta_pp']>1e-8 for r in rr),
                   'dd_lower':sum(r['dd_delta_pp']<-1e-8 for r in rr),
                   'calmar_wins':sum(r['current_calmar']>r['cycle_calmar'] for r in rr),
                   'worst_positive_profit_retention':min((r['profit_retention'] for r in rr if r['profit_retention'] is not None),default=None)}
with (D/'comparison.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(D/'audit.json').write_text(json.dumps({'all_passed':True,'native_cases_reused':50,
    'new_native_backtests':0,'comparison_cases':25,'official_source_unchanged':True,
    'max_reconstruction_error_usdt':max(c['max_reconstruction_error_usdt'] for c in checks),
    'source_and_data_checks':sources,'checks':checks},indent=2))
(D/'findings.json').write_text(json.dumps(counts,indent=2))
lines=['# 五币分别独立运行：当前补仓版与CycleRisk对比','',
       'BTC、ETH、LINK、XRP、ADA，每币每起点均单独1000 USDT账户，max_open_trades=1，2021—2025年1月1日至2026-10-06，手续费0.1%，无充值，无调参。2020起点不纳入。', '',
       '当前版为Ma200CashSupplementStrategy；CycleRisk为当前正式cycle_risk_strategy.py，回测使用仅增加不可变历史缓存的CycleRiskOriginalCached入口。50条已完成原生回测记录构成25个成对案例，未重复运行相同回测。逐项验证正式源码、行情、配置，并重新从成交独立重建全部50条净值及回撤。', '',
       '| 标的 | 当前版收益领先 | 当前版回撤更低 | 当前版Calmar更高 |','|---|---:|---:|---:|']
for asset,c in counts.items():lines.append(f"| {asset} | {c['return_wins']}/5 | {c['dd_lower']}/5 | {c['calmar_wins']}/5 |")
for asset in ASSETS:
    lines+=['','## '+asset,'','| 起点 | CycleRisk收益 | 当前版收益 | CycleRisk回撤 | 当前版回撤 | CycleRisk CAGR | 当前版CAGR | CycleRisk Calmar | 当前版Calmar |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        if r['asset']!=asset:continue
        lines.append(f"| {r['year']} | {r['cycle_return_pct']:+.2f}% | {r['current_return_pct']:+.2f}% | {r['cycle_wallet_drawdown_pct']:.2f}% | {r['current_wallet_drawdown_pct']:.2f}% | {r['cycle_cagr_pct']:.2f}% | {r['current_cagr_pct']:.2f}% | {r['cycle_calmar']:.3f} | {r['current_calmar']:.3f} |")
lines+=['','## 判断','',
        '单币对照表明当前版并非普遍优于CycleRisk。LINK、ADA全部起点收益和回撤都更好；BTC仅2025起点收益更高，全部起点回撤高于CycleRisk。ETH多数起点收益较低，2021起点利润减少约51.37%，回撤增加约12.37个百分点；XRP在2021—2023起点明显落后。BTC在2023起点利润减少约42.62%，XRP在2023起点利润减少约94.94%，超过用户此前20%—25%的可接受收益损失范围。', '',
        'LINK在2022—2025起点体现明显改善；ADA虽然相对原版更好，2025起点仍亏约49.91%，不能把相对优势理解为绝对风险受控。组合回撤改善不能推出每个币都改善，组合资金分配和资产路径会改变总体风险。', '',
        '25个当前版单币案例均无额外闲置现金补仓成交。因此这些差异主要比较底层MA200交接、熊市分档和CycleRisk的MA150/EMA10与回撤仓位规则，不能归功于新增补仓功能；也不能据此证明定投新增资金效果。', '',
        '窗口重叠、币种选择有幸存者偏差。不能根据本次结果直接为LINK/ADA指定一个策略、BTC/ETH指定另一个，随后把同样历史当作验证；此类组合选择需要冻结规则并在未用于选择的资产或时间段检验。当前研究候选未部署。']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n')
A=R.parents[1]/'user_data/archive/ma200_cash_supplement_20261010/single_vs_cycle_validation'
A.mkdir(parents=True,exist_ok=True)
for name in ['REPORT.md','comparison.csv','audit.json','findings.json','analyze.py']:shutil.copy2(D/name,A/name)
p=A.parent/'README.md';s=p.read_text()
if 'single_vs_cycle_validation/REPORT.md' not in s:
    p.write_text(s+'\n五币单独运行与正式CycleRisk逐项对照：[25个成对案例](single_vs_cycle_validation/REPORT.md)。50条原生记录已重新重建净值，无充值，未部署。\n')
print(json.dumps(counts,indent=2))
print('All 50 native equity curves audited; archive:',A)
