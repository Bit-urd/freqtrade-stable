import csv,json,gzip,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).parent
NAMES=['BtcCoinGuardCycleRiskStrategy','Ma200BtcRegimeFullCyclePortfolioStrategy','IndependentHoldCycleRiskStrategy','IndependentProbeCycleRiskStrategy','IndependentPromoteCycleRiskStrategy','IndependentFastGuardCycleRiskStrategy','BuyAndHold']
LABELS=dict(zip(NAMES,['原CycleRisk','原Portfolio','仅改退出','加25%试仓','确认后升50%','例外加EMA10保护','持有']))
rows=list(csv.DictReader((ROOT/'summary.csv').open()));windows=json.loads((ROOT/'windows.json').read_text())
extra=list(csv.DictReader((ROOT/'fast_guard_study/summary.csv').open()))
for r in extra:
 if r['strategy']=='BuyAndHold':
  old=next(x for x in rows if x['window']==r['window'] and x['strategy']=='BuyAndHold')
  for key in ['return_pct','wallet_drawdown_pct']:
   assert abs(float(old[key])-float(r[key]))<1e-6
rows += [r for r in extra if r['strategy']=='IndependentFastGuardCycleRiskStrategy']
assert len(rows)==len(windows)*len(NAMES)
with (ROOT/'combined_summary.csv').open('w') as output:
 writer=csv.DictWriter(output,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
groups={w['label']:{r['strategy']:r for r in rows if r['window']==w['label']} for w in windows}
comparisons=[]
for w in windows:
 g=groups[w['label']];assert set(g)==set(NAMES)
 for name,r in g.items():
  assert r['start']==w['start'] and r['end']==w['end']
  if name!='BuyAndHold':assert abs(float(r['ledger_error']))<.05
  if w['pair']=='BTC/USDT' and name.startswith('Independent'):
   for k in ['return_pct','wallet_drawdown_pct','ending_equity','trades','normal_fills']:
    assert abs(float(r[k])-float(g[NAMES[0]][k]))<1e-6
 for name in NAMES[2:-1]:
  r=g[name];b=g[NAMES[0]]
  comparisons.append(dict(pair=w['pair'],window=w['label'],strategy=name,
   wealth_ratio=float(r['ending_equity'])/float(b['ending_equity']),
   return_change_pp=float(r['return_pct'])-float(b['return_pct']),
   drawdown_change_pp=float(r['wallet_drawdown_pct'])-float(b['wallet_drawdown_pct']),
   quick_loss_change=int(r['quick_loss_positions'])-int(b['quick_loss_positions']),
   fills_change=int(r['normal_fills'])-int(b['normal_fills']),
   probe_positions=int(r['independent_probe_positions'])))
with (ROOT/'comparison.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
aggregates=[]
for cohort,predicate in [('all_non_btc',lambda x:x['pair']!='BTC/USDT'),('original_altcoins',lambda x:x['pair'] in ['SUI/USDT','ZEC/USDT']),('additional_coins',lambda x:x['pair'] in ['ADA/USDT','DOGE/USDT','AVAX/USDT']),('portfolio',lambda x:x['pair']=='PORTFOLIO')]:
 for name in NAMES[2:-1]:
  sub=[r for r in comparisons if r['strategy']==name and predicate(r)]
  aggregates.append(dict(cohort=cohort,strategy=name,windows=len(sub),
   return_better=sum(r['return_change_pp']>1e-6 for r in sub),
   drawdown_better=sum(r['drawdown_change_pp']<-1e-6 for r in sub),
   jointly_better=sum(r['return_change_pp']>1e-6 and r['drawdown_change_pp']<-1e-6 for r in sub),
   median_wealth_ratio=statistics.median(r['wealth_ratio'] for r in sub),
   median_drawdown_change_pp=statistics.median(r['drawdown_change_pp'] for r in sub),
   worst_wealth_ratio=min(r['wealth_ratio'] for r in sub),
   max_drawdown_increase_pp=max(r['drawdown_change_pp'] for r in sub),
   total_probe_positions=sum(r['probe_positions'] for r in sub)))
with (ROOT/'aggregate.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(aggregates[0]));writer.writeheader();writer.writerows(aggregates)
text=['# 独立行情优化测试','',f'共{len(windows)}个区间，每区间6个策略及持有，{len(windows)*(len(NAMES)-1)}次策略回测。BTC/SUI/ZEC沿用上轮数据；ADA/DOGE/AVAX来自Binance公共行情；原组合为BTC/SOL/ETH。统一1000 USDT、现货、每侧手续费0.1%、无额外滑点，截至2026-10-06。单币一个槽位，组合三个槽位。每个区间独立开户；日线收盘权益包含浮亏，终点不计人为强平。', '', '## 本轮结论', '', '本轮没有找到跨币稳健的统一替换方案，正式CycleRisk及运行服务保持原样。仅改退出对SUI早期和ZEC近期收益有效，但ADA/DOGE的部分区间恶化，原三币组合收益也未提升。36个非BTC区间中，只有10个收益提高，4个收益与回撤同时改善；期末资金比中位数为1.00，最大回撤恶化8.84个百分点。', '', '新增25%独立试仓没有带来增量收益：实际新增的是同一笔DOGE 2022-08-17至08-20亏损交易，在两个重叠窗口分别出现一次，单笔净亏损约22%。确认后加仓没有改善这一结果。EMA10保护虽然消除了大部分DOGE额外损失，也削弱了SUI/ZEC的趋势捕获，不支持进一步加严短期过滤作为统一方案。', '', '只保留仅改退出作为研究候选，不启用弱市独立入场，不替换正式策略。下一步研究若继续，应单独检验独立例外持仓的失败退出及急跌保护，不能继续只围绕ZEC收益调参。本报告没有证明这些未测试方向有效。', '', '## 冻结的候选规则','', '四个候选都继承原CycleRisk，BTC账户完全维持原行为。独立强势需价格高于EMA20、EMA20高于EMA50且两线向上；个币/BTC比值高于EMA20、EMA20高于EMA50且两线向上；前一天收盘突破此前20日最高价，当前收盘仍在该突破位以上。突破确认后的独立标记只要绝对/相对趋势仍强就持续，不要求每日再创新高。趋势失效即撤销。仅使用完整历史的因果滚动指标，下一根开盘执行。', '', '1. 仅改退出：入场、14日冷却、账户回撤机制不变。BTC弱势且个币独立强势时降到50%目标档位继续持有；独立强势失效则恢复原BTC退出。个币退出保护始终保留。', '2. 加25%试仓：新增BTC弱势时独立强势币25%入场，原冷却仍保留。弱市试仓仓位保持25%；BTC恢复正常时恢复原账户风险目标。', '3. 确认后升50%：在第二版基础上，试仓后连续3根完整日线独立强势，可提升至50%。', '4. 例外加EMA10保护：在仅改退出版基础上，个币还需收盘高于上升的EMA10，才允许保留BTC弱势例外。入场不变。', '', '候选调仓目标档位=min(账户风险档位,市场允许档位)，不会绕过账户风控。延续原策略只在档位变化时调仓；50%是调仓时的目标，不是每日严格再平衡的市值上限，价格上涨后实际持仓市值比例可能高于50%。按照真实order_filled记录档位；未成交不提前更新。没有加入新的急跌阈值或改变风险峰值重置规则，便于隔离本次改动效果。第一轮三个候选在回测前固定；EMA10保护版是在观察第一轮失败后追加的回溯实验，不能视作样本外。全部币种共用规则，没有分别调参。', '', '## 相对原CycleRisk的总体变化','', '| 范围 | 候选 | 收益提高窗口 | 回撤更浅窗口 | 同时改善 | 期末资金比中位数 | 最大回撤恶化(pp) |','|---|---|---:|---:|---:|---:|---:|']
for r in aggregates:
 text.append(f"| {r['cohort']} | {LABELS[r['strategy']]} | {r['return_better']}/{r['windows']} | {r['drawdown_better']}/{r['windows']} | {r['jointly_better']}/{r['windows']} | {r['median_wealth_ratio']:.4f} | {r['max_drawdown_increase_pp']:+.2f} |")
text+=['', '期末资金比=候选期末权益/原CycleRisk期末权益。窗口相互重叠，胜率仅为描述统计，不是独立样本显著性。', '', '## 全部区间','', '每格为累计收益 / 最大回撤。']
for pair in ['BTC/USDT','SUI/USDT','ZEC/USDT','ADA/USDT','DOGE/USDT','AVAX/USDT','PORTFOLIO']:
 text+=['',f'### {pair}','', '| 区间 | '+' | '.join(LABELS[n] for n in NAMES)+' |','|---|'+'---:|'*len(NAMES)]
 for w in windows:
  if w['pair']!=pair:continue
  g=groups[w['label']]
  cells=[f"{float(g[n]['return_pct']):+.2f}% / {float(g[n]['wallet_drawdown_pct']):.2f}%" for n in NAMES]
  text.append(f"| {w['start']}～{w['end']} | "+' | '.join(cells)+' |')
text+=['', '## 检查与限制','', '41项行为/历史截断及独立入场分支检查通过，指标在未来数据追加后保持历史值不变；BTC入场信号与原策略一致；BTC全部回测逐项与原策略相同；账户账本逐次核对；风险控制前日权益逐日核对；原CycleRisk和Portfolio在上轮对应区间的收益与回撤复现。所有策略、数据保留哈希。', '', 'quick_loss_positions定义为正常退出中持有不超过10日且净亏损的交易，用来观察快速失败交易，不等同于严格识别的假突破。未把终点人为强平作为失败交易。汇总也保存真实成交次数和手续费。', '', '本次历史已被查看，不属于严格样本外。增加币种用于跨币稳健性检查，不能消除选币偏差。候选只放在validation隔离目录，未修改正式策略或运行服务。']
(ROOT/'REPORT.md').write_text('\n'.join(text)+'\n')
(ROOT/'verification.json').write_text(json.dumps(dict(windows=len(windows),strategy_runs=len(windows)*(len(NAMES)-1),max_ledger_error=max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error']),btc_backtest_identity=True,indicator_checks_passed=json.loads((ROOT/'indicator_verification.json').read_text())['passed'],entry_checks_passed=json.loads((ROOT/'entry_verification.json').read_text())['passed'],fast_guard_checks_passed=json.loads((ROOT/'fast_verification.json').read_text())['passed']),indent=2))
print(json.dumps(aggregates,indent=2))
