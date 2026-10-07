"""Summarize frozen cross-asset validation without ranking overlapping profits."""
import csv,json,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;D=ROOT/'representative_assets'
plan=json.loads((D/'plan.json').read_text());rows=list(csv.DictReader((D/'summary.csv').open()))
N=plan['strategies'];OFF=N[0];BASE=N[1]
SHORT={OFF:'新正式版',BASE:'原 Portfolio',N[2]:'分阶段',N[3]:'快速退出',N[4]:'全天个币保护','BuyAndHold':'持有'}
WINDOW={'ref_bull_2023_2024':'2023–2024 上涨','ref_bull_to_bear_2021':'牛转熊','ref_bear_2022':'2022 熊市','ref_since_last_september':'近期','ref_requested_long':'指定长周期','bull_2024':'2024 上涨（含新币）'}
for r in rows:
 for k in ['return_pct','wallet_drawdown_pct','hold_return_pct','hold_drawdown_pct','ledger_error','risk_trace_error']:
  r[k]=float(r[k]) if r[k] else 0.
lookup={(r['pair'],r['window'],r['strategy']):r for r in rows}
cases=sorted({(r['pair'],r['window']) for r in rows});assert all(all((p,w,n) in lookup for n in N+['BuyAndHold']) for p,w in cases)
progress=json.loads((D/'progress.json').read_text());assert len(cases)==progress['total_cases']==progress['completed_cases']
manifest=json.loads((D/'source_manifest.json').read_text())
assert all(hashlib.sha256((D/'strategies'/f).read_bytes()).hexdigest()==h for f,h in manifest.items())
verification={'completed_cases':len(cases),'native_backtests':len(cases)*len(N),'hold_cases':len(cases),'max_cash_ledger_error':max(abs(r['ledger_error']) for r in rows),'max_daily_risk_equity_error':max(abs(r['risk_trace_error']) for r in rows),'frozen_sources_unchanged':True,'single_coin_one_slot':True,'fee_per_side':.001,'initial_capital':1000,'skipped_cases':len(json.loads((D/'skipped.json').read_text()))}
assert verification['max_cash_ledger_error']<.05 and verification['max_daily_risk_equity_error']<.05
anchors=list(csv.DictReader((ROOT/'single_coin_comparison/summary.csv').open()))+list(csv.DictReader((ROOT/'portfolio_coin_guard/single_coin/summary.csv').open()))
anchor_count=0
seen=set()
for old in anchors:
    key=(old['pair'],'ref_requested_long',old['strategy'])
    if key not in lookup or key in seen: continue
    seen.add(key);current=lookup[key]
    for metric in ['return_pct','wallet_drawdown_pct']:
        assert abs(float(old[metric])-current[metric])<1e-5,(key,metric,'historical baseline changed')
    anchor_count+=1
verification['historical_long_window_anchor_rows']=anchor_count
(D/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
lines=['# 代表性标的 × 周期：正式版和主要策略验证','',f'固定规则，不搜索或修改参数。{len(plan["pairs"])} 个预先选择的现存 Binance 标的，{len(plan["windows"])} 个时间窗口；实际完成 {len(cases)} 个币/窗口案例、{len(cases)*len(N)} 次原生策略回测及 {len(cases)} 次持有估值。','', '每个案例独立投入 1000 USDT，只交易一个币、一个槽位；其他币的 BTC 仅作为趋势信号。单边手续费 0.1%，现货、市场成交，无额外滑点。每日收盘权益口径，终点仍持仓按收盘估值；另有清仓手续费估值列。所有策略和持有使用完全相同日期。','', '标的性质为选择用途的粗分类，不代表持仓相关性。当前上市币池存在幸存者偏差；部分历史已被观察，本研究不声称严格样本外验证。单币风控结果不能直接等同多币账户的组合风控表现。各窗口存在重叠，不把收益相加、不将案例数当作独立统计样本。上涨/熊市是市场区间标签，不表示每个币在该段都同方向涨跌。正式版 25%/35% 是减仓触发阈值，并非最大回撤上限：减仓后仍有风险敞口，新周期可恢复仓位并重置内部风控峰值，报告回撤始终使用账户全历史峰值。','', '## 标的选择','', '| 标的 | 性质 |','|---|---|']
lines += [f'| {p} | {plan["asset_types"][p]} |' for p in plan['pairs']]
lines += ['','## 分周期横截面汇总','', '收益中位数和回撤中位数分别描述同一组标的的分布，可能对应不同币，并非一个可交易组合的收益/回撤。胜出指相对原 Portfolio；联合改善指收益更高且回撤更低。正收益持有目标只在该币该窗口持有收益 >0 时计入。','', '| 周期 | 策略 | 币数 | 收益中位数 | 回撤中位数 | 收益胜原版 | 回撤胜原版 | 联合改善 | 持有正收益下 2/3+更低回撤 |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
aggregates=[]
for w in plan['windows']:
 label=w['label'];ps=[p for p in plan['pairs'] if (p,label,OFF) in lookup]
 if not ps:continue
 for n in N+['BuyAndHold']:
  rs=[lookup[p,label,n] for p in ps];bs=[lookup[p,label,BASE] for p in ps]
  rw=sum(x['return_pct']>b['return_pct']+1e-6 for x,b in zip(rs,bs));dw=sum(x['wallet_drawdown_pct']<b['wallet_drawdown_pct']-1e-6 for x,b in zip(rs,bs));both=sum(x['return_pct']>b['return_pct']+1e-6 and x['wallet_drawdown_pct']<b['wallet_drawdown_pct']-1e-6 for x,b in zip(rs,bs));eligible=sum(x['hold_return_pct']>0 for x in rs);hit=sum(x['hold_return_pct']>0 and x['return_pct']>=x['hold_return_pct']*2/3 and x['wallet_drawdown_pct']<x['hold_drawdown_pct'] for x in rs)
  agg={'window':label,'strategy':n,'coins':len(ps),'median_return_pct':statistics.median(x['return_pct'] for x in rs),'median_drawdown_pct':statistics.median(x['wallet_drawdown_pct'] for x in rs),'return_wins_vs_portfolio':rw,'drawdown_wins_vs_portfolio':dw,'joint_improvements_vs_portfolio':both,'positive_hold_target_hits':hit,'positive_hold_cases':eligible};aggregates.append(agg)
  lines.append(f'| {WINDOW[label]} | {SHORT[n]} | {len(ps)} | {agg["median_return_pct"]:+.2f}% | {agg["median_drawdown_pct"]:.2f}% | {rw}/{len(ps)} | {dw}/{len(ps)} | {both}/{len(ps)} | {hit}/{eligible} |')
lines += ['','## 本轮结论','', '按用户接受折中的标准，正式版有真实改进，但优势有明确适用边界：上涨和两类熊市的收益/回撤中位数优于原 Portfolio；长周期收益中位数提高，代价是回撤中位数也增加；近期原 Portfolio 明显更稳。','', '长周期正式版 280.66% / 57.45%，原 Portfolio 204.23% / 50.04%，分阶段 212.48% / 63.32%，快速退出 249.25% / 60.79%。正式版在长周期横截面同时改善了分阶段和快速退出的两项中位数，但这不意味着每个币都胜出。长周期逐币同时达到持有约 2/3 收益且回撤更低：正式版 3/10，原 Portfolio 5/10；不能用两个中位数之比替代逐币达标率。','', 'BTC 六段中五段同时提高收益并降低回撤；ETH、SOL、XRP 各四段联合改善，AAVE 五段改善但仍严重落后持有上涨收益。LINK 五段联合退步、AVAX 四段、ADA 三段，不宜将三币正式组合的结论直接推广给它们。','', 'PEPE 两个可测窗口均相对原版联合改善，但只有两段、缺少 2022 熊市；SUI 没有联合改善窗口。2024 PEPE 正式版 974.93% / 46.96%，接近持有收益 2/3 且回撤更低；分阶段收益 2478.35% / 50.60%，此币上涨收益仍明显更强。不同资产性质本身不能代替实际走势与策略验证。','', '本轮仅验证，不更改参数、正式选择或运行服务；正式范围继续限定 BTC/SOL/ETH。该范围的多币账户结果以既有组合报告为准，此处单币风控验证不用于推算一个新 12 币组合。']
lines += ['','## 正式版按标的稳定性','', '| 币 | 可测窗口 | 收益胜原版 | 回撤胜原版 | 同时改善 | 收益更低且回撤更高 |','|---|---:|---:|---:|---:|---:|']
asset_summary=[]
for p in plan['pairs']:
    ws=[w for pp,w in cases if pp==p];xs=[lookup[p,w,OFF] for w in ws];bs=[lookup[p,w,BASE] for w in ws]
    rw=sum(x['return_pct']>b['return_pct']+1e-6 for x,b in zip(xs,bs));dw=sum(x['wallet_drawdown_pct']<b['wallet_drawdown_pct']-1e-6 for x,b in zip(xs,bs))
    both=sum(x['return_pct']>b['return_pct']+1e-6 and x['wallet_drawdown_pct']<b['wallet_drawdown_pct']-1e-6 for x,b in zip(xs,bs));bad=sum(x['return_pct']<b['return_pct']-1e-6 and x['wallet_drawdown_pct']>b['wallet_drawdown_pct']+1e-6 for x,b in zip(xs,bs))
    asset_summary.append({'pair':p,'windows':len(ws),'return_wins':rw,'drawdown_wins':dw,'joint_improvements':both,'joint_regressions':bad})
    lines.append(f'| {p.split("/")[0]} | {len(ws)} | {rw} | {dw} | {both} | {bad} |')
(D/'asset_summary.json').write_text(json.dumps(asset_summary,indent=2)+'\n')
lines += ['','## 新正式版逐币取舍','', '| 周期 | 币 | 正式版收益 / 回撤 | 相对原版收益差 | 相对原版回撤差 | 持有收益 / 回撤 |','|---|---|---:|---:|---:|---:|']
deltas=[]
for w in plan['windows']:
 for p in plan['pairs']:
  if (p,w['label'],OFF) not in lookup:continue
  x=lookup[p,w['label'],OFF];b=lookup[p,w['label'],BASE];h=lookup[p,w['label'],'BuyAndHold'];dr=x['return_pct']-b['return_pct'];dd=x['wallet_drawdown_pct']-b['wallet_drawdown_pct']
  deltas.append({'pair':p,'asset_type':plan['asset_types'][p],'window':w['label'],'official_return_pct':x['return_pct'],'official_drawdown_pct':x['wallet_drawdown_pct'],'return_difference_pp':dr,'drawdown_difference_pp':dd,'hold_return_pct':h['return_pct'],'hold_drawdown_pct':h['wallet_drawdown_pct']})
  lines.append(f'| {WINDOW[w["label"]]} | {p.split("/")[0]} | {x["return_pct"]:+.2f}% / {x["wallet_drawdown_pct"]:.2f}% | {dr:+.2f} pp | {dd:+.2f} pp | {h["return_pct"]:+.2f}% / {h["wallet_drawdown_pct"]:.2f}% |')
lines += ['','回撤差为负表示正式版回撤较小。','', '## 全部逐币对比','', '每格为收益率 / 最大回撤。']
for w in plan['windows']:
 lines += ['',f'### {WINDOW[w["label"]]}：{w["timerange"]}','', '| 币 | '+' | '.join(SHORT[n] for n in N+['BuyAndHold'])+' |','|---|'+'---:|'*6]
 for p in plan['pairs']:
  if (p,w['label'],OFF) not in lookup:continue
  vals=[lookup[p,w['label'],n] for n in N+['BuyAndHold']];lines.append('| '+p.split('/')[0]+' | '+' | '.join(f'{x["return_pct"]:+.2f}% / {x["wallet_drawdown_pct"]:.2f}%' for x in vals)+' |')
lines += ['','## 长周期交易频率与风险控制代价','', '下表用于解释规则差异，不能仅凭交易次数断言全部收益差的原因。正式版继承全天个币保护的入场/退出；风控层调整持仓风险，不会把较宽松的趋势恢复入场变成原 Portfolio 的 EMA20/50 入场过滤。','', '| 币 | 正式版交易数 | 原 Portfolio 交易数 | 正式版平均现金比例 | 个币保护平均现金比例 | 正式版相对个币保护收益差 |','|---|---:|---:|---:|---:|---:|']
for p in plan['pairs']:
    w='ref_requested_long'
    if (p,w,OFF) not in lookup:continue
    x=lookup[p,w,OFF];b=lookup[p,w,BASE];g=lookup[p,w,N[4]]
    lines.append(f'| {p.split("/")[0]} | {x["trades"]} | {b["trades"]} | {float(x["mean_idle_cash_pct"]):.2f}% | {float(g["mean_idle_cash_pct"]):.2f}% | {x["return_pct"]-g["return_pct"]:+.2f} pp |')
lines += ['','## 缺失历史与核对','',f'最大期末现金账本误差 {verification["max_cash_ledger_error"]:.3g} USDT；新正式版每天用于风控的前日权益与独立成交账本最大误差 {verification["max_daily_risk_equity_error"]:.3g} USDT。冻结源码哈希一致。','', '上市前及不足 210 天预热历史的窗口明确跳过，不移动起点；明细见 skipped.json。2024 上涨窗口额外覆盖新币上市后完整自然年，近期统一截至 2026-10-05。原始成交和逐日权益保留在本地 results/，精简指标见 summary.csv。','', '复现：固定镜像下运行 /research/run_representative_assets.py；汇总脚本 make_representative_assets_report.py。正式选择未改变，运行服务未切换。']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n')
for name,data in [('aggregate.csv',aggregates),('official_vs_portfolio.csv',deltas)]:
 with (D/name).open('w') as f:wr=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');wr.writeheader();wr.writerows(data)
print(json.dumps(verification,indent=2))
