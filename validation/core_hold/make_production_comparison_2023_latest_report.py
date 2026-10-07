"""连续账户年度收益及真实交易频率；终点强平独立统计。"""
from pathlib import Path
import csv,gzip,json,hashlib,datetime,math
R=Path(__file__).parent;D=R/'production_comparison_2023_latest';RESULT=D/'results/continuous_2023_latest'
plan=json.loads((D/'plan.json').read_text());names=plan['strategies']+['BuyAndHold']
labels={'BtcCoinGuardCycleRiskStrategy':'CycleRisk 正式版','Ma200BtcRegimeFullCyclePortfolioStrategy':'原 Portfolio','BtcTrendPhasedStrategy':'分阶段','BtcTrendFastExitStrategy':'快速退出','Ma200BtcRegimeFullCycleCoreHoldStrategy':'温和 CoreHold','BtcCoinGuardTrendRecoveryRiskStrategy':'趋势恢复','BtcCoinGuardRisingMediumExitStrategy':'EMA50 上升改进','BuyAndHold':'持有'}
summary=list(csv.DictReader((D/'summary.csv').open()));assert len(summary)==8 and {x['strategy'] for x in summary}==set(names)
annual=[];frequency=[];totals=[]
years=range(2023,2027)
for name in names:
 curve=list(csv.DictReader((RESULT/('equity_'+name+'.csv')).open()))
 for row in curve:
  row['date']=row.get('date') or row['']
 assert len(curve)==1375,(name,len(curve))
 assert curve[0]['date'][:10]==plan['start'] and curve[-1]['date'][:10]==plan['end']
 counters={y:dict(opens=0,closes=0,add_buys=0,partial_sells=0,buy_fills=0,sell_fills=0,total_fills=0,terminal_force_fills=0,turnover_usdt=0.,fees_usdt=0.) for y in years}
 if name!='BuyAndHold':
  payload=json.load(gzip.open(RESULT/(name+'.json.gz'),'rt'));trades=payload['trades']
  for t in trades:
   orders=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
   assert orders and orders[0]['ft_is_entry']
   for i,o in enumerate(orders):
    year=datetime.datetime.fromtimestamp(o['order_filled_timestamp']/1000,datetime.timezone.utc).year
    c=counters[year]
    if t['exit_reason']=='force_exit' and i==len(orders)-1:
     assert not o['ft_is_entry'];c['terminal_force_fills']+=1;continue
    entry=bool(o['ft_is_entry']);category=('opens' if i==0 else 'add_buys') if entry else ('closes' if i==len(orders)-1 else 'partial_sells')
    c[category]+=1;c['buy_fills' if entry else 'sell_fills']+=1;c['total_fills']+=1
    notional=float(o['amount'])*float(o['safe_price']);c['turnover_usdt']+=notional;c['fees_usdt']+=notional*float(t['fee_open'] if entry else t['fee_close'])
 else:
  counters[2023].update(opens=3,buy_fills=3,total_fills=3,turnover_usdt=1000/1.001,fees_usdt=1000-1000/1.001)
 previous=1000.
 for year in years:
  rows=[x for x in curve if int(x['date'][:4])==year];assert rows
  end=float(rows[-1]['equity']);peak=previous;dd=0.
  for x in rows:
   value=float(x['equity']);peak=max(peak,value);dd=max(dd,1-value/peak)
  annual.append({'strategy':name,'year':year,'start':rows[0]['date'][:10],'end':rows[-1]['date'][:10],'starting_equity':previous,'ending_equity':end,'return_pct':(end/previous-1)*100,'within_year_drawdown_pct':dd*100,**counters[year]})
  previous=end
  c=counters[year];assert c['buy_fills']==c['opens']+c['add_buys'] and c['sell_fills']==c['closes']+c['partial_sells']
  frequency.append({'strategy':name,'year':year,**c})
 s=next(x for x in summary if x['strategy']==name);assert abs(float(s['ending_equity'])-previous)<1e-7
 compound=math.prod(1+x['return_pct']/100 for x in annual if x['strategy']==name)
 assert abs(compound-previous/1000)<1e-10
 totals.append({'strategy':name,'opens':sum(c['opens'] for c in counters.values()),'closes':sum(c['closes'] for c in counters.values()),'filled_orders':sum(c['total_fills'] for c in counters.values()),'terminal_force_fills':sum(c['terminal_force_fills'] for c in counters.values())})
for filename,rows in [('annual_metrics.csv',annual),('annual_trade_counts.csv',frequency),('total_trade_counts.csv',totals)]:
 with (D/filename).open('w') as out:
  w=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
for f,sha in json.loads((D/'source_manifest.json').read_text()).items():assert hashlib.sha256((D/'strategies'/f).read_bytes()).hexdigest()==sha
lines=['# 2023 至最新完整日线：连续三币账户对比','','区间 **2023-01-01～2026-10-06**，UTC 日线，2026 年非全年。BTC/SOL/ETH 现货、共享账户、初始 1000 USDT、三个槽位、每侧手续费 0.1%；不加额外滑点。持有在起点等权买入、不再平衡。2026-10-06 完整日线从 Binance 公共行情接口下载至隔离快照，10月7日未完成日线在生成快照前过滤，不进入引擎、不参与估值和信号。未修改运行服务数据。','', '连续账户从 2023 年开始，不按年重置本金、交易或风控。收益和最大回撤按日线收盘权益；终点实际强平费用另见 summary.csv 的 liquidated_return_pct。年度回撤使用年初权益和该年峰值，不能直接相加或替代全区间回撤。','', '## 全区间','','| 策略 | 收益率 | 最大回撤 | 期末权益 USDT | 开仓次数 | 正常平仓次数 | 实际成交笔数 |','|---|---:|---:|---:|---:|---:|---:|']
for name in names:
 x=next(t for t in summary if t['strategy']==name);c=next(t for t in totals if t['strategy']==name)
 lines.append(f"| {labels[name]} | {float(x['return_pct']):+.2f}% | {float(x['wallet_drawdown_pct']):.2f}% | {float(x['ending_equity']):.2f} | {c['opens']} | {c['closes']} | {c['filled_orders']} |")
lines+=['','## 连续账户年度收益','','| 策略 | 2023 | 2024 | 2025 | 2026 至10月6日 |','|---|---:|---:|---:|---:|']
for name in names:
 values=[next(x for x in annual if x['strategy']==name and x['year']==y)['return_pct'] for y in years]
 lines.append('| '+labels[name]+' | '+' | '.join(f'{v:+.2f}%' for v in values)+' |')
lines+=['','## 每年开仓 / 正常平仓次数','','每个币的一次新持仓算一次开仓；该持仓全部退出算一次平仓。跨年持仓会使同一年开仓数和平仓数不同。部分加减仓不算新持仓。终点强制平仓不算策略正常交易。','', '| 策略 | 2023 | 2024 | 2025 | 2026 至10月6日 |','|---|---:|---:|---:|---:|']
for name in names:
 values=[next(x for x in frequency if x['strategy']==name and x['year']==y) for y in years]
 lines.append('| '+labels[name]+' | '+' | '.join(f"{v['opens']} / {v['closes']}" for v in values)+' |')
lines+=['','## CycleRisk 每年成交细分','','| 年份 | 新开仓 | 全部平仓 | 加仓买入 | 部分减仓 | 正常成交总笔数 | 年度收益 | 年内最大回撤 |','|---|---:|---:|---:|---:|---:|---:|---:|']
for x in annual:
 if x['strategy']=='BtcCoinGuardCycleRiskStrategy':lines.append(f"| {x['year']} | {x['opens']} | {x['closes']} | {x['add_buys']} | {x['partial_sells']} | {x['total_fills']} | {x['return_pct']:+.2f}% | {x['within_year_drawdown_pct']:.2f}% |")
lines+=['','## 逐年风险及成交明细','','各策略的年度回撤、成交次数、名义成交金额、手续费及强制平仓数详见 annual_metrics.csv / annual_trade_counts.csv。没有把期末强制卖出的三笔等同于信号退出；持有也不在终点人为卖出。策略开仓交易数不是所有订单数。','', '## 验证','','各策略使用完全相同的 1375 个交易日；原生成交重建账本与引擎余额核对，所有权益风控版本的前一日权益逐日核对；年度收益复利连接等于全区间收益，成交分类和计数一致，冻结策略哈希未变。历史区间已被观察，本次新增起止组合并不构成严格样本外验证。','']
verification={'passed':True,'native_runs':7,'days':len(curve),'start':plan['start'],'end':plan['end'],'max_cash_ledger_error_usdt':max(abs(float(x['ledger_error'] or 0)) for x in summary),'annual_compounding_reconciles':True,'trade_count_categories_reconcile':True,'source_hashes_match':True,'daily_risk_equity_reconciled_in_runner':True,'terminal_force_exits_excluded_from_frequency':True}
(D/'verification.json').write_text(json.dumps(verification,indent=2)+'\n');(D/'REPORT.md').write_text('\n'.join(lines))
print(json.dumps(verification));print('\n'.join(lines[6:29]))
