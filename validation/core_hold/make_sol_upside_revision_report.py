"""形成固定规则的单币/组合优化对照，核对旧正式版与持有基准。"""
import csv,json,hashlib,statistics
from pathlib import Path
R=Path(__file__).resolve().parent;D=R/'sol_upside_revision_v2';BASE='BtcCoinGuardCycleRiskStrategy';B='BtcCoinGuardTrendRecoveryRiskStrategy';C='BtcCoinGuardTrendPriorityRiskStrategy';names=[BASE,B,C,'BuyAndHold'];short={BASE:'原正式版',B:'趋势恢复版',C:'强趋势优先版','BuyAndHold':'持有'}
single=list(csv.DictReader((D/'summary.csv').open()));combo=list(csv.DictReader((D/'portfolio/summary.csv').open()));old=list(csv.DictReader((R/'representative_assets/summary.csv').open()));oldcombo=list(csv.DictReader((R/'archive/portfolio_cycle_risk_v2/summary.csv').open()));plan=json.loads((D/'plan.json').read_text());checks=json.loads((D/'rule_checks.json').read_text());assert checks['passed']
assert len(single)==72 and len(combo)==20
oldix={(r['pair'],r['window'],r['strategy']):r for r in old};ix={(r['pair'],r['window'],r['strategy']):r for r in single};ci={(r['window'],r['strategy']):r for r in combo};oldci={(r['window'],r['strategy']):r for r in oldcombo}
for row in single:
 if row['strategy'] not in [BASE,'BuyAndHold']:continue
 o=oldix[row['pair'],row['window'],row['strategy']]
 assert (row['start'],row['end'])==(o['start'],o['end'])
 for k in ['return_pct','wallet_drawdown_pct']:assert abs(float(row[k])-float(o[k]))<1e-5,(row['pair'],row['window'],k)
for row in combo:
 if row['strategy'] not in [BASE,'BuyAndHold']:continue
 o=oldci[row['window'],row['strategy']]
 assert (row['start'],row['end'])==(o['start'],o['end'])
 for k in ['return_pct','wallet_drawdown_pct']:assert abs(float(row[k])-float(o[k]))<1e-5,(row['window'],k)
for folder in [D,D/'portfolio']:
 m=json.loads((folder/'source_manifest.json').read_text());assert all(hashlib.sha256((folder/'strategies'/f).read_bytes()).hexdigest()==h for f,h in m.items())
lag=json.loads((D/'entry_lag_diagnosis.json').read_text());gap=json.loads((D/'return_gap_diagnosis.json').read_text())
labels={'ref_bull_2023_2024':'2023–2024 上涨','ref_bull_to_bear_2021':'牛转熊','ref_bear_2022':'2022 熊市','ref_since_last_september':'近期','ref_requested_long':'指定长周期','bull_2024':'2024 单年'}
lines=['# SOL 上涨收益差距：诊断与固定结构优化','', '以现有正式版为基线，只比较三个结构假设：长期趋势支持时延后额外减仓；趋势重新确认时恢复风险；强趋势连续确认时优先满风险仓位。未搜索均线长度、回撤阈值、冷却天数，不针对 SOL 设置特殊参数。正式版与运行服务不变。','', '## 为什么差距大','',f'持有于 2023-01-01 开盘以 {lag["hold_initial_open"]:.2f} 买入；策略首次于 2023-01-05 以 {lag["strategy_initial_open"]:.2f} 买入，期间已经上涨 {lag["price_rise_before_first_entry_pct"]:.2f}%。到 2024 年末，从同一首次进场日开始持有收益为 {lag["hold_from_first_strategy_entry_return_pct"]:.2f}%，原起点持有为 {lag["initial_hold_return_pct"]:.2f}%。延迟起点只用于诊断，正式比较仍保留原起点。','',f'逐层对照差额：首次进场延迟约 {gap["first_entry_lag_pp"]:.2f} 个百分点；同起点持有与快速退出差 {gap["fast_exit_vs_same_entry_hold_pp"]:.2f}；增加个币保护差 {gap["coin_guard_delta_pp"]:.2f}；增加权益风控再差 {gap["equity_risk_delta_pp"]:.2f}。合计 {gap["total_return_gap_pp"]:.2f} 个百分点。这是有复利相互作用的算术对照分解，不是四个互不影响的独立收益来源，也不能承诺调早进场就能补回全部差额。','', '原正式版权益风控让 SOL 上涨收益从全天个币保护的 1105.18% 降到 817.73%，但回撤仅从 42.04% 降到 39.06%。730 个执行日中 201 天维持 75% 风险、142 天维持 50%，只有 387 天为满风险。账户历史回撤状态会拖慢恢复，BTC 新周期确认又不能覆盖每一次 SOL 自身恢复。','', '## 优化规则','', '共同长期支持：BTC 连续两根已收盘日线站上 MA200；交易币收盘高于自身 MA150 且 EMA20 > EMA50，账户至少三分之二的币符合；该条件连续两天成立。单币要求该币自身成立。原 BTC/个币退出、入场、手续费、独立币预算、14 天冷却不改。','', '趋势恢复版：长期支持有效时不追加权益减仓；长期支持由弱重新确认后，可恢复满风险并重置内部风控峰值，沿用 14 天重置间隔。','', '强趋势优先版：长期支持有效时目标为满风险，其他时候沿用原 25%/35% 减仓和 20%/30% 恢复；不因长期支持额外重置峰值，原 BTC 新周期重置仍保留。此规则会在长期支持丢失且旧账户回撤较深时再减仓；放宽持仓需要承担更大回撤的可能。','', '所有报告最大回撤仍以账户原全历史最高权益计算，25%/35% 不是硬回撤上限。使用过去已收盘数据，不根据窗口标签或未来牛熊状态切换。','', '## SOL 单币：收益 / 最大回撤','', '| 周期 | 原正式版 | 趋势恢复版 | 强趋势优先版 | 快速退出 | 全天个币保护 | 持有 |','|---|---:|---:|---:|---:|---:|---:|']
for w in plan['windows']:
 label=w['label'];values=[ix['SOL/USDT',label,n] for n in [BASE,B,C]]+[oldix['SOL/USDT',label,n] for n in ['BtcTrendFastExitStrategy','BtcTrendCoinGuardStrategy']]+[ix['SOL/USDT',label,'BuyAndHold']]
 lines.append('| '+labels[label]+' | '+' | '.join(f'{float(x["return_pct"]):+.2f}% / {float(x["wallet_drawdown_pct"]):.2f}%' for x in values)+' |')
lines += ['','## BTC / ETH 迁移检查','']
for p in ['BTC/USDT','ETH/USDT']:
 lines += [f'### {p}','', '| 周期 | '+' | '.join(short[n] for n in names)+' |','|---|'+'---:|'*4]
 for w in plan['windows']:
  values=[ix[p,w['label'],n] for n in names];lines.append('| '+labels[w['label']]+' | '+' | '.join(f'{float(x["return_pct"]):+.2f}% / {float(x["wallet_drawdown_pct"]):.2f}%' for x in values)+' |')
lines += ['','## BTC / ETH / SOL 三币组合检查','', '同一个 1000 USDT 钱包，三个槽位，各币独立预算，账户权益共同触发风控。此处为真实组合原生回测，不由单币结果相加估算。','', '| 周期 | '+' | '.join(short[n] for n in names)+' |','|---|'+'---:|'*4]
for w in plan['windows'][:5]:
 values=[ci[w['label'],n] for n in names];lines.append('| '+labels[w['label']]+' | '+' | '.join(f'{float(x["return_pct"]):+.2f}% / {float(x["wallet_drawdown_pct"]):.2f}%' for x in values)+' |')
comparisons=[]
for scope,source in [('single_coin',single),('three_coin_portfolio',combo)]:
 for x in source:
  row={'scope':scope,'pair':x.get('pair','BTC/ETH/SOL'),'window':x['window'],'start':x['start'],'end':x['end'],'strategy':x['strategy'],'return_pct':float(x['return_pct']),'drawdown_pct':float(x['wallet_drawdown_pct']),'trades':x['trades']}
  hold=ix[x['pair'],x['window'],'BuyAndHold'] if scope=='single_coin' else ci[x['window'],'BuyAndHold']
  base=ix[x['pair'],x['window'],BASE] if scope=='single_coin' else ci[x['window'],BASE]
  row.update(hold_return_pct=float(hold['return_pct']),hold_drawdown_pct=float(hold['wallet_drawdown_pct']),return_fraction_of_hold=float(x['return_pct'])/float(hold['return_pct']) if float(hold['return_pct'])>0 else None,return_difference_vs_formal_pp=float(x['return_pct'])-float(base['return_pct']),drawdown_difference_vs_formal_pp=float(x['wallet_drawdown_pct'])-float(base['wallet_drawdown_pct']))
  comparisons.append(row)
with (D/'comparison.csv').open('w') as f:wr=csv.DictWriter(f,fieldnames=list(comparisons[0]),lineterminator='\n');wr.writeheader();wr.writerows(comparisons)
verification={'preliminary_native_runs':12,'final_single_coin_native_runs':54,'final_portfolio_native_runs':15,'rule_tests':checks['tests_run'],'all_checks_passed':True,'formal_and_hold_anchor_rows':46,'sources_match_frozen_manifests':True,'max_cash_ledger_error':max(abs(float(x['ledger_error'] or 0)) for x in single+combo),'max_single_daily_risk_equity_error':max(float(x['risk_trace_error'] or 0) for x in single),'reported_drawdown_uses_original_peak':True}
assert verification['max_cash_ledger_error']<.05 and verification['max_single_daily_risk_equity_error']<.05
(D/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
lines += ['','## 保留结论','', '保留 BtcCoinGuardTrendRecoveryRiskStrategy 作为 SOL 单币的改进研究候选，不替换当前正式三币版本，不增加活动策略目录中的独立研究分支。强趋势优先版在 SOL 上涨、长周期和近期相对趋势恢复版取舍较弱，未选为下一优化主线；趋势感知版只保留为机制对照与继承基础。全部源码和失败/未采用记录保留在研究目录供复现。','', 'SOL 上涨收益从 817.73% 增至 1029.45%，多 211.72 个百分点，回撤从 39.06% 增至 43.92%，多约 4.86 个百分点；长周期从 541.81%/57.99% 增至 736.56%/57.22%，收益增加 194.75 个百分点且回撤略降。纯熊市不变，牛转熊改善，近期收益少约 0.98 个百分点、回撤多约 0.56 个百分点。上涨收益仍只有持有约 57.29%，长周期约 43.52%，未达到持有约 2/3 的单币目标。','', '上涨段全天个币保护 1105.18%/42.04%，仍优于趋势恢复版的 1029.45%/43.92%；保留恢复版看的是相对现正式版的跨周期收益/风险折中，不宣称该段最优。','', '三币组合上涨原正式版 527.79%/30.31%，两优化版 527.51%/30.00%，基本持平；长周期从 497.43%/40.83% 增至 512.01%/40.93%，只有约 14.58 个百分点收益改善、约 0.10 个百分点回撤增加。牛转熊、纯熊市、近期均不变。这个组合增益不足以支持宣称明显升级。','', '原正式版上涨期单币 SOL 有 343 个执行日风险目标降至 75%/50%，而三币组合只有 60 天为 75%，没有 50% 阶段，其余 670 天为满风险目标。这些是目标阶段天数，不代表每一天都实际持仓。组合中权益风控的拖累远小于单币，解释了为何 SOL 单币改进较大、组合只微调。']
lines += ['','## 复现与限制','', f'12 次初步回测、54 次最终单币回测、15 次组合回测，{checks["tests_run"]} 项检查通过；原正式版与持有 46 条锚点复现。逐日风控权益及期末现金与独立成交账本核对。正式配置和运行服务未切换。','', '规则只用了既有均线和固定确认，不做参数网格搜索；但历史已被反复观察，不能声明样本外有效。两种优化均没有实盘重启状态持久化。入口：run_sol_upside_revision_v2.py、run_sol_upside_portfolio.py、check_sol_upside_revision.py；账本、风险轨迹和成交原始记录在各 results/。']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(verification,indent=2))
