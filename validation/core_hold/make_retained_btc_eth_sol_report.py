"""Merge unchanged existing profiles with fresh CoreHold/own-trend comparisons."""
import ast,csv,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;D=ROOT/'retained_btc_eth_sol';P=ROOT/'representative_assets'
plan=json.loads((D/'plan.json').read_text());names=plan['compared_strategies'];pairs=plan['pairs'];windows=plan['windows']
fresh=list(csv.DictReader((D/'summary.csv').open()));prior=list(csv.DictReader((P/'summary.csv').open()));lookup={(r['pair'],r['window'],r['strategy']):r for r in prior};new={(r['pair'],r['window'],r['strategy']):r for r in fresh}
progress=json.loads((D/'progress.json').read_text());assert progress['completed_cases']==progress['total_cases']==18
class Strip(ast.NodeTransformer):
 def visit(self,n):
  if isinstance(n,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and ast.get_docstring(n,clean=False) is not None:n.body=n.body[1:]
  return super().visit(n)
def logic(p):return ast.dump(Strip().visit(ast.parse(p.read_text())),include_attributes=False)
for f in ['cycle_risk_strategy.py','equity_risk_strategy.py','btc_trend_coin_guard_strategy.py','ma200_btc_regime_full_cycle_core_hold_strategy.py','ma200_btc_regime_full_cycle_portfolio_strategy.py']:
 assert logic(D/'strategies'/f)==logic(P/'strategies'/f),f
old_data={x['pair']:x for x in json.loads((P/'data_audit.json').read_text())};new_data={x['pair']:x for x in json.loads((D/'data_audit.json').read_text())}
for p in pairs:
 for k in ['daily_sha256','weekly_sha256']:assert old_data[p][k]==new_data[p][k],(p,k)
manifest=json.loads((D/'source_manifest.json').read_text());assert all(hashlib.sha256((D/'strategies'/f).read_bytes()).hexdigest()==h for f,h in manifest.items())
merged=[]
for w in windows:
 for p in pairs:
  for n in names+['BuyAndHold']:
   key=(p,w['label'],n);row=dict(new[key] if n in plan['strategies'] or n=='BuyAndHold' else lookup[key]);row['measurement_source']='fresh_36_native_runs' if n in plan['strategies'] else 'fresh_hold_estimate' if n=='BuyAndHold' else 'unchanged_previous_native_run'
   reference=lookup[p,w['label'],'BuyAndHold'];assert (row['start'],row['end'],row['days'])==(reference['start'],reference['end'],reference['days'])
   if n=='BuyAndHold':
    for k in ['return_pct','wallet_drawdown_pct']:assert abs(float(row[k])-float(reference[k]))<1e-5
   merged.append(row)
with (D/'comparison.csv').open('w') as f:wr=csv.DictWriter(f,fieldnames=list(merged[0]),lineterminator='\n');wr.writeheader();wr.writerows(merged)
ix={(r['pair'],r['window'],r['strategy']):r for r in merged}
short=dict(zip(names,['新正式版','原 Portfolio','分阶段','快速退出','温和 CoreHold','个币独立趋势']));short['BuyAndHold']='持有'
labels={'ref_bull_2023_2024':'2023–2024 上涨','ref_bull_to_bear_2021':'牛转熊','ref_bear_2022':'2022 熊市','ref_since_last_september':'近期','ref_requested_long':'指定长周期','bull_2024':'2024 单年'}
lines=['# 保留版本：BTC、ETH、SOL 分别与持有比较','', '六个保留版本，每个币独立投入 1000 USDT、一个槽位、现货、单边手续费 0.1%。持有同日起点买入，按同一终点收盘价估值，不调仓。回撤按每日收盘总权益计算，未加入额外滑点和盘中回撤。','', '四个主要策略复用前轮同参数、同数据、同日期的 72 条原生回测结果；补跑温和 CoreHold、个币独立趋势共 36 次原生回测，并重新计算 18 组持有。注释中文化后五个相关实现去除说明字符串的语法树与前轮一致，三币日线/周线数据哈希均一致。','', '这些是单币独立账户，不是 BTC/ETH/SOL 组合账户。正式版账户回撤控制在单币和组合中会有不同轨迹，不能把单币收益相加推算组合。窗口重叠、已经观察过的历史不作为严格样本外证据。','', '## 各周期完整对比','', '每格为收益率 / 最大回撤。']
for w in windows:
 lines += ['',f'### {labels[w["label"]]}：{w["timerange"]}','', '| 币 | '+' | '.join(short[n] for n in names+['BuyAndHold'])+' |','|---|'+'---:|'*7]
 for p in pairs:
  values=[ix[p,w['label'],n] for n in names+['BuyAndHold']]
  lines.append('| '+p.split('/')[0]+' | '+' | '.join(f'{float(x["return_pct"]):+.2f}% / {float(x["wallet_drawdown_pct"]):.2f}%' for x in values)+' |')
lines += ['','## 各币收益与风险覆盖','', '联合改善：相对原 Portfolio 收益更高且回撤更低。持有收益为正时，才计算“收益至少 2/3 且回撤更低”的联合目标；熊市不使用负收益比值。','', '| 币 | 策略 | 收益胜原版 | 回撤胜原版 | 联合改善 | 正收益持有联合目标 |','|---|---|---:|---:|---:|---:|']
summary=[]
for p in pairs:
 for n in names:
  xs=[ix[p,w['label'],n] for w in windows];bs=[ix[p,w['label'],names[1]] for w in windows]
  wins=sum(float(x['return_pct'])>float(b['return_pct'])+1e-6 for x,b in zip(xs,bs));dds=sum(float(x['wallet_drawdown_pct'])<float(b['wallet_drawdown_pct'])-1e-6 for x,b in zip(xs,bs));both=sum(float(x['return_pct'])>float(b['return_pct'])+1e-6 and float(x['wallet_drawdown_pct'])<float(b['wallet_drawdown_pct'])-1e-6 for x,b in zip(xs,bs));eligible=sum(float(x['hold_return_pct'])>0 for x in xs);hit=sum(float(x['hold_return_pct'])>0 and float(x['return_pct'])>=float(x['hold_return_pct'])*2/3 and float(x['wallet_drawdown_pct'])<float(x['hold_drawdown_pct']) for x in xs)
  summary.append({'pair':p,'strategy':n,'return_wins':wins,'drawdown_wins':dds,'joint_improvements':both,'hold_joint_hits':hit,'positive_hold_cases':eligible})
  lines.append(f'| {p.split("/")[0]} | {short[n]} | {wins}/6 | {dds}/6 | {both}/6 | {hit}/{eligible} |')
(D/'profile_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
verification={'fresh_native_backtests':36,'reused_native_backtests':72,'fresh_hold_cases':18,'comparison_rows':len(merged),'all_strategy_dates_match_hold':True,'reused_sources_logic_unchanged':True,'reused_three_coin_data_hashes_match':True,'frozen_sources_unchanged':True,'max_ledger_error':max(abs(float(x['ledger_error'] or 0)) for x in merged),'hold_anchor_rows':18}
assert verification['max_ledger_error']<.05
(D/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
lines += ['','## 结果取舍','', '新正式版相对原 Portfolio，在 BTC 六段中五段联合改善，ETH 和 SOL 各四段联合改善；近期三个币都不如原版的收益/回撤组合。','', 'BTC 长周期正式版与快速退出相同（419.93%/28.70%），收益约持有的 65.15%，接近 2/3，但回撤略高于持有 28.10%。ETH 长周期正式版 281.93%/44.12%，收益约持有的 97.55%；快速退出 339.43%/52.28%，用更多收益换更大回撤。','', 'SOL 长周期正式版 541.81%/57.99%，收益只有持有 1692.42% 的 32.01%；即使快速退出 895.51%，也只有约 52.91%。2023–2024 正式版 SOL 收益 817.73%，仅持有的约 45.51%；快速退出 1299.36%，但回撤从正式版 39.06% 增至 44.88%。正式三币组合接近 2/3 的结果不能替代 SOL 单币达标，SOL 仍是明显短板。','', '温和 CoreHold 近期 BTC/ETH/SOL 分别 5.15%/-1.65%/13.36%，比新正式版更好，但 2022 熊市与原 Portfolio 一样囤币亏损，不能当作全周期升级。个币独立趋势版在本次 2022 熊市三个币都没有交易，牛转熊防守优秀；代价是上涨和长周期收益明显不足，SOL 长周期回撤也不低。','', '因此继续保留不同探索方向有实际依据：正式版为主线，分阶段/快速退出作为上涨参与对照，CoreHold 检查近期反复行情，个币独立趋势检查熊市现金防守。此次不按照已知阶段事后拼接策略，也不改变正式版本。']
lines += ['','## 数据和复现','',f'最大成交现金账本误差 {verification["max_ledger_error"]:.3g} USDT。18 组持有收益和回撤均与前轮一致。重跑脚本 run_retained_btc_eth_sol.py；汇总脚本 make_retained_btc_eth_sol_report.py；输入和来源见 plan.json、source_manifest.json、data_audit.json、comparison.csv。','', '个币独立趋势版按原实现使用 210 根日线预热计算指标，其他策略按各自原生预热配置，统一实际交易起止日，不更改其信号规则。运行兼容的快速测试版及旧 BTC 周线版不参加收益排名。正式选择及运行服务不变。']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(verification,indent=2))
