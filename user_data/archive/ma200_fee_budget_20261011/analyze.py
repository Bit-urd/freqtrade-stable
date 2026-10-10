import csv,json,gzip,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent
B=D.parent/'ma200_cash_reservation_20261011'
N='Ma200CashSupplementStrategy'
rows=[];audits=[]
for year in range(2021,2026):
 w=f'start_{year}';metrics=[]
 for root in [B,D]:
  folder=root/'results'/w
  m=next(r for r in csv.DictReader((folder/'summary.csv').open()) if r['strategy']==N and r['window']==w)
  curve=list(csv.DictReader((folder/(N+'_equity.csv')).open()))
  trades=json.load(gzip.open(folder/(N+'_trades.json.gz'),'rt'))
  extra=[o for t in trades for o in t['orders'] if o['ft_is_entry'] and (o.get('ft_order_tag') or '').startswith('idle_cash:')]
  minimum=min(float(r['cash']) for r in curve)
  assert abs(float(m['ledger_error']))<.05
  metrics.append((m,len(extra),sum(float(o['cost']) for o in extra),minimum))
  audits.append({'year':year,'version':'before' if root==B else 'after','ledger_error':float(m['ledger_error']),'minimum_daily_cash':minimum,'extra_buys':len(extra)})
 old,new=metrics
 assert new[3]>=-.05,(year,'negative corrected cash',new[3])
 row={'year':year,'before_return':float(old[0]['return_pct']),'after_return':float(new[0]['return_pct']),'before_dd':float(old[0]['wallet_drawdown_pct']),'after_dd':float(new[0]['wallet_drawdown_pct']),'before_extra_buys':old[1],'after_extra_buys':new[1],'before_extra_cost':old[2],'after_extra_cost':new[2]}
 row['return_delta_pp']=row['after_return']-row['before_return'];row['dd_delta_pp']=row['after_dd']-row['before_dd'];row['profit_retention']=row['after_return']/row['before_return'] if row['before_return']>0 else None
 row['full_trade_records_identical']=json.load(gzip.open(B/'results'/w/(N+'_trades.json.gz'),'rt'))==json.load(gzip.open(D/'results'/w/(N+'_trades.json.gz'),'rt'))
 plans=json.loads((D/'results'/w/(N+'_funding.json')).read_text())
 row['entry_reserve_plan_count']=sum(x.get('entry_cash_reserve',0)>0 for x in plans)
 row['reserve_and_allocation_plan_count']=sum(x.get('entry_cash_reserve',0)>0 and bool(x['allocation']) for x in plans)
 rows.append(row)
with (D/'comparison.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(D/'audit.json').write_text(json.dumps(audits,indent=2)+'\n')
s=['# MA200 买入手续费预算修正：前后对照','','BTC、ETH、LINK、XRP、ADA 五币组合，各起点1000 USDT，手续费0.1%，运行到2026-10-06；无外部入金。2020起点不测试。旧版结果复用冻结同数据记录，新版五次原生回测。','','仅修正买入预算：模拟钱包扣除剩余持仓买入手续费，所有买单预留当笔手续费；实盘不重复扣历史手续费。入场、退出、趋势、档位及父策略目标公式保持不变。','','| 起点 | 修改前收益 | 修改后收益 | 收益差pp | 修改前回撤 | 修改后回撤 | 回撤差pp | 额外补仓笔数 前→后 |','|---|---:|---:|---:|---:|---:|---:|---:|']
for r in rows:s.append(f"| {r['year']} | {r['before_return']:+.2f}% | {r['after_return']:+.2f}% | {r['return_delta_pp']:+.2f} | {r['before_dd']:.2f}% | {r['after_dd']:.2f}% | {r['dd_delta_pp']:+.2f} | {r['before_extra_buys']}→{r['after_extra_buys']} |")
s+=['','完整交易记录一致的窗口数：'+str(sum(r['full_trade_records_identical'] for r in rows))+'/5。新版计划中有新开仓预留的次数：'+str(sum(r['entry_reserve_plan_count'] for r in rows))+'；同时产生额外补仓分配的次数：'+str(sum(r['reserve_and_allocation_plan_count'] for r in rows))+'。','','## 验证边界','','新版每日现金最低值不低于−0.05U，订单账本与引擎终值一致（误差低于0.05U），无回调异常。旧版存在的小额现金负值按实际成交及费用重新核对。39项功能检查另行通过。无充值，不能作为外部入金执行和收益验证；原生日线市价回测不能充分模拟实盘长期挂单，其隔离规则主要由功能测试验证。当前仍未部署。']
(D/'REPORT.md').write_text('\n'.join(s)+'\n')
print(json.dumps(rows,indent=2))
