import csv,gzip,json,hashlib,shutil
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
D=Path(__file__).resolve().parent
R=D.parent
raw=R/'requested_27_half_year_20261008/raw/spot'
checks=[]
N=R/'ma200_cash_supplement_six_hold_20261010'
BASE='Ma200BtcRegimeFullCyclePortfolioStrategy'
NEW='Ma200CashSupplementStrategy'
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

assert json.loads((D/'COMPLETED.json').read_text())['complete']
base=json.loads((D/'baseline_results.json').read_text());current=list(csv.DictReader((N/'comparison.csv').open()));rows=[];sources={}
for asset in ['BTC','ETH','LINK','XRP','ADA']:
 for year in [2024,2025]:
  b=next(r for r in base if r['asset']==asset and r['window']=='start_'+str(year))
  n=next(r for r in current if r['group']==asset and r['year']==str(year))
  folder=Path(b['evidence_directory'])
  # Driver writes container absolute paths; map research mount to host.
  folder=Path(str(folder).replace('/research/',str(R.resolve())+'/'))
  audit(folder,BASE,asset,b)
  expected={'start':str(year)+'-01-01','return_pct':n['strategy_return_pct'],'wallet_drawdown_pct':n['strategy_wallet_drawdown_pct']}
  extra=audit(N/asset/'results'/('start_'+str(year)),NEW,asset,expected)
  source_root=folder.parents[1]
  source_file=source_root/'strategies/ma200_btc_regime_full_cycle_portfolio_strategy.py'
  official=R.parents[1]/'user_data/strategies/ma200_btc_regime_full_cycle_portfolio_strategy.py'
  h=hashlib.sha256(source_file.read_bytes()).hexdigest()
  assert h==hashlib.sha256(official.read_bytes()).hexdigest()=='b08519edb1883e469a59514e7c4d2e68c26203be31f044fcfd77c0057fced9fc'
  config=json.loads((source_root/'config.json').read_text())
  assert config['fee']==.001 and config['dry_run_wallet']==1000 and config['max_open_trades']==1
  assert config['exchange']['pair_whitelist']==[asset+'/USDT']
  hashes={}
  for symbol in {asset,'BTC'}:
   filename=symbol+'_USDT-1d.feather';digest=hashlib.sha256((source_root/'data'/filename).read_bytes()).hexdigest()
   assert digest==hashlib.sha256((N/asset/'data'/filename).read_bytes()).hexdigest();hashes[filename]=digest
  sources[asset]={'base_sha256':h,'data_sha256':hashes}
  r={'asset':asset,'year':year,'reused_baseline':b['reused'],'supplemental_orders':extra}
  for key in ['return_pct','wallet_drawdown_pct','cagr_pct','calmar','ending_equity']:
   r['base_'+key]=float(b[key]);r['current_'+key]=float(n['strategy_'+key])
  r['return_delta_pp']=r['current_return_pct']-r['base_return_pct'];r['dd_delta_pp']=r['current_wallet_drawdown_pct']-r['base_wallet_drawdown_pct'];rows.append(r)
counts={'return_wins':sum(r['return_delta_pp']>1e-8 for r in rows),'dd_lower':sum(r['dd_delta_pp']<-1e-6 for r in rows),'dd_same_within_0_01pp':sum(abs(r['dd_delta_pp'])<=.01 for r in rows),'calmar_wins':sum(r['current_calmar']>r['base_calmar'] for r in rows)}
with (D/'comparison.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(D/'audit.json').write_text(json.dumps({'all_passed':True,'equity_curves_audited':20,'new_native_runs':6,'reused_baseline_runs':4,'reused_current_runs':10,'checks':checks,'sources':sources,'max_error_usdt':max(c['max_reconstruction_error_usdt'] for c in checks)},indent=2))
(D/'findings.json').write_text(json.dumps(counts,indent=2))
lines=['# MA200原版与当前补仓版：2024、2025单币对比','','当前版Ma200CashSupplementStrategy；原版ma200_btc_regime_full_cycle_portfolio_strategy.py，类Ma200BtcRegimeFullCyclePortfolioStrategy。BTC、ETH、LINK、XRP、ADA，每币每起点独立1000 USDT，终点2026-10-06，手续费0.1%，无充值，无调参。新补跑6个原版案例、复用4个匹配原版案例，当前版10个案例复用此前结果；20条成交净值全部重新独立重建。','','| 标的 | 起点 | 原版收益 | 当前版收益 | 收益差pp | 原版回撤 | 当前版回撤 | 回撤差pp |','|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:lines.append(f"| {r['asset']} | {r['year']} | {r['base_return_pct']:+.2f}% | {r['current_return_pct']:+.2f}% | {r['return_delta_pp']:+.2f} | {r['base_wallet_drawdown_pct']:.2f}% | {r['current_wallet_drawdown_pct']:.2f}% | {r['dd_delta_pp']:+.4f} |")
lines+=['','| 标的 | 起点 | 原版CAGR | 当前版CAGR | 原版Calmar | 当前版Calmar |','|---|---:|---:|---:|---:|']
for r in rows:lines.append(f"| {r['asset']} | {r['year']} | {r['base_cagr_pct']:.2f}% | {r['current_cagr_pct']:.2f}% | {r['base_calmar']:.3f} | {r['current_calmar']:.3f} |")
lines+=['','## 同五币组合参考','','| 起点 | 原版收益 | 当前版收益 | 原版回撤 | 当前版回撤 |','|---|---:|---:|---:|---:|']
portfolio_base=list(csv.DictReader((R/'ma200_confirmed_handover_20261010/summary.csv').open()));portfolio_new=list(csv.DictReader((R/'ma200_cash_supplement_20261010/summary.csv').open()))
for year in [2024,2025]:
 b=next(r for r in portfolio_base if r['window']=='start_'+str(year) and r['strategy']==BASE);n=next(r for r in portfolio_new if r['window']==b['window'] and r['strategy']==NEW)
 lines.append(f"| {year} | {float(b['return_pct']):+.2f}% | {float(n['return_pct']):+.2f}% | {float(b['wallet_drawdown_pct']):.2f}% | {float(n['wallet_drawdown_pct']):.2f}% |")
lines+=['','## 解释与边界','',f"单币当前版收益领先{counts['return_wins']}/10，Calmar领先{counts['calmar_wins']}/10，回撤差不超过0.01个百分点的案例{counts['dd_same_within_0_01pp']}/10。逐项差异见表，不能用四舍五入后的相同回撤代替原始差值。",'',
'当前版包括两层改动：MA200熊市仓位在BTC牛市及个币趋势确认后交接补仓，以及原调仓之外的闲置现金补仓。原版HANDOVER_TOP_UP=False，当前版开启并增加个币趋势确认。全部10个单币当前版案例的额外闲置现金补仓成交为零，所以这里的收益变化体现确认交接补仓，不能归功于额外现金补仓或充值功能。', '',
'组合结果不等于单币收益平均，补仓和共享现金会改变后续开仓规模。2024组合当前版收益仍略低于原版；相同指标规则在组合环境下未必保留全部单币优势。', '',
'两个起点窗口重叠，既有币池存在选择偏差。无充值，候选未部署，不构成未来收益保证。']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n')
A=R.parents[1]/'user_data/archive/ma200_cash_supplement_20261010/single_vs_ma200_base_validation';A.mkdir(parents=True,exist_ok=True)
for name in ['REPORT.md','comparison.csv','audit.json','findings.json','COMPLETED.json','finish.py']:shutil.copy2(D/name,A/name)
p=A.parent/'README.md';s=p.read_text()
if 'single_vs_ma200_base_validation/REPORT.md' not in s:p.write_text(s+'\n2024及2025起点单币与MA200原版：[完整对比](single_vs_ma200_base_validation/REPORT.md)。六个原版案例补跑完成，20条净值重新核对，无充值，未部署。\n')
print(json.dumps(rows,indent=2));print(counts)
