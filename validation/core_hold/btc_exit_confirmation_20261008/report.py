import csv,gzip,json,hashlib,sys
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
windows=json.loads((root/'windows.json').read_text())
rows=list(csv.DictReader((root/'summary.csv').open()))
assert len(rows)==len(windows)*3
idx={(r['window'],r['strategy']):r for r in rows}
old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy'
prior=list(csv.DictReader((root.parent/'momentum_selection_20261008/summary.csv').open()))
oldidx={(r['window'],r['strategy']):r for r in prior}
for w in windows:
 for n in [old,'BuyAndHold']:
  for key in ['return_pct','wallet_drawdown_pct','ending_equity']:
   assert abs(float(idx[w['label'],n][key])-float(oldidx[w['label'],n][key]))<1e-6,(w['label'],n,key)
manifest=json.loads((root.parent/'momentum_selection_20261008/data_audit.json').read_text())
for record in manifest['files']:
 datafile=root.parent/'independent_trend_optimization_20261008/data'/record['file']
 assert hashlib.sha256(datafile.read_bytes()).hexdigest()==record['sha256']
(root/'data_audit.json').write_text(json.dumps(manifest,indent=2)+'\n')
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p).set_index('date') for p in (root.parent/'independent_trend_optimization_20261008/data').glob('*-1d.feather')}
btc=history['BTC/USDT'].close;ma=btc.rolling(150).mean();ema=btc.ewm(span=10,adjust=False).mean()
weak=ma.notna() & (btc<ma) & ~((btc>ema) & (ema>ema.shift(1)))
exit_checks=0
comparisons=[];events=[]
for w in windows:
 label=w['label'];a=idx[label,old];b=idx[label,new]
 comparisons.append(dict(window=label,return_change_pp=float(b['return_pct'])-float(a['return_pct']),drawdown_change_pp=float(b['wallet_drawdown_pct'])-float(a['wallet_drawdown_pct']),wealth_ratio=float(b['ending_equity'])/float(a['ending_equity']),cash_change_pp=float(b['mean_idle_cash_pct'])-float(a['mean_idle_cash_pct'])))
 for n in [old,new]:
  payload=json.load(gzip.open(root/'results'/label/(n+'.json.gz'),'rt'))
  trades=payload['trades']
  for t in trades:
   if t['exit_reason']!='trend_to_cash':continue
   day=pd.Timestamp(t['close_date']);day=day.tz_localize('UTC') if day.tzinfo is None else day.tz_convert('UTC')
   signalday=day.normalize()-pd.Timedelta(days=1)
   required=1 if n==old else 2
   assert all(bool(weak.loc[signalday-pd.Timedelta(days=i)]) for i in range(required)),(label,n,day)
   exit_checks+=1
   pair=t['pair']; prices=history[pair].close
   buys=[pd.Timestamp(x['open_date']) for x in trades if x['pair']==pair and pd.Timestamp(x['open_date'])>day]
   nextbuy=min(buys) if buys else None
   record=dict(window=label,strategy=n,pair=pair,exit_date=day.isoformat(),trade_profit_abs=t['profit_abs'],reentry_days=(nextbuy-day).days if nextbuy is not None else None)
   for days in [5,10]:
    target=day+pd.Timedelta(days=days)
    record['price_return_'+str(days)+'d_pct']=(float(prices.loc[target])/float(t['close_rate'])-1)*100 if target<=pd.Timestamp(w['end'],tz='UTC') and target in prices.index else None
   events.append(record)
for filename,records in [('comparison.csv',comparisons),('btc_exit_events.csv',events)]:
 with (root/filename).open('w') as f:
  out=csv.DictWriter(f,fieldnames=list(records[0]));out.writeheader();out.writerows(records)
checks=json.loads((root/'verification.json').read_text());assert checks['passed']
errors=[abs(float(r['ledger_error'])) for r in rows if r['ledger_error']]
plan=json.loads((root/'plan.json').read_text());assert hashlib.sha256((root/'strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==plan['baseline_sha256']
bear=[x for x in comparisons if 'bear_2022' in x['window']]
bull=[x for x in comparisons if 'bull_2023_2024' in x['window']]
passed=None
plan.update(status='complete',assessment='comprehensive tradeoff review; no fixed numerical gate');plan.pop('acceptance_passed',None);(root/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
lines=['# BTC 退出确认：1 天与 2 天','', '唯一改动为 TREND_EXIT_DAYS 从 1 改为 2；原 BTC 入场、标的退出、14 天冷却、分币预算、账户降仓和恢复逻辑均继承。初始 1000 USDT，每侧费用 0.1%，无滑点，统一截至 2026-10-06。19 个窗口独立开户；不是各年拼接连续收益。','',f"收益提高 {sum(x['return_change_pp']>1e-6 for x in comparisons)}/19，回撤降低 {sum(x['drawdown_change_pp']<-1e-6 for x in comparisons)}/19，同时改善 {sum(x['return_change_pp']>1e-6 and x['drawdown_change_pp']<-1e-6 for x in comparisons)}/19。按用户最新要求综合评估，无固定回撤扩大门槛。",'', '用户在首批三币结果后取消 5 个百分点硬门槛；本轮综合考虑最终收益、最大回撤、熊市损失、各周期取舍和规则复杂度，不作数值越线自动淘汰，也不自动升级生产策略。','', '| 窗口 | 原版收益/回撤 | 两天版收益/回撤 | 持有收益/回撤 | 收益变化 | 回撤变化 |','|---|---:|---:|---:|---:|---:|']
for w,x in zip(windows,comparisons):
 cells=[f"{float(idx[w['label'],n]['return_pct']):+.2f}% / {float(idx[w['label'],n]['wallet_drawdown_pct']):.2f}%" for n in [old,new,'BuyAndHold']]
 lines.append('| '+w['label']+' | '+' | '.join(cells)+f" | {x['return_change_pp']:+.2f}pp | {x['drawdown_change_pp']:+.2f}pp |")
annual=[]
for label in ['core3_continuous_2023_latest','broad7_continuous_2023_latest','broad8_since_maturity']:
 for n in [old,new,'BuyAndHold']:
  curve=pd.read_csv(root/'results'/label/('equity_'+n+'.csv'),index_col=0,parse_dates=True)
  for year,part in curve.groupby(curve.index.year):
   before=curve.loc[curve.index<part.index[0],'equity']
   start=float(before.iloc[-1]) if len(before) else 1000.
   values=pd.concat([pd.Series([start]),part.equity.reset_index(drop=True)])
   annual.append(dict(window=label,year=year,strategy=n,return_pct=(float(part.equity.iloc[-1])/start-1)*100,drawdown_pct=float((1-values/values.cummax()).max()*100)))
with (root/'continuous_annual.csv').open('w') as f:
 out=csv.DictWriter(f,fieldnames=list(annual[0]));out.writeheader();out.writerows(annual)
lines+=['','## 连续账户年度表现','', '账户不在年初重置；每年收益以前一年度末权益为基准，首段从初始本金开始。年内回撤包含年初基准，不能与独立开户年度回测混为一谈。','', '| 连续窗口 | 年份 | 原版收益/年内回撤 | 两天版收益/年内回撤 | 持有收益/年内回撤 |','|---|---:|---:|---:|---:|']
annualidx={(x['window'],x['year'],x['strategy']):x for x in annual}
for label,year in dict.fromkeys((x['window'],x['year']) for x in annual):
 cells=[]
 for n in [old,new,'BuyAndHold']:
  x=annualidx[label,year,n];cells.append(f"{x['return_pct']:+.2f}% / {x['drawdown_pct']:.2f}%")
 lines.append('| '+label+' | '+str(year)+' | '+' | '.join(cells)+' |')
lines+=['','## 成交与退出统计','', '| 窗口 | 原版/两天版成交次数 | 原版/两天版正常费用 | 原版/两天版 BTC 退出次数 |','|---|---:|---:|---:|']
for w in windows:
 label=w['label'];a=idx[label,old];b=idx[label,new]
 count=lambda n:sum(e['window']==label and e['strategy']==n for e in events)
 lines.append(f"| {label} | {a['normal_fills']} / {b['normal_fills']} | {float(a['normal_fees']):.2f} / {float(b['normal_fees']):.2f} USDT | {count(old)} / {count(new)} |")
lines+=['','## 退出事件诊断','', 'btc_exit_events.csv 记录 BTC 弱势退出后的 5/10 天价格表现及同币再次入场等待天数。期末不足观察天数的事件剔除该项；价格表现是描述，不是可实现的策略收益，不能单凭退出后上涨认定应该不退出。不同窗口事件有重叠。','',f"规则及历史截断检查 {checks['count']} 项通过；{exit_checks} 次实际 BTC 原因退出的前日弱势确认逐项核对通过；19 个窗口原版与持有各 3 项指标复现前轮结果。所有新增回测逐日控制器权益及成交现金账核对通过，余额最大误差 {max(errors):.10g} USDT。",'', '币池是事后选择的存续币，窗口已经查看且有重叠，属于回溯研究；无严格样本外证据。每个候选独立从原版开始，本轮没有叠加集中配置、独立行情或移动止损。生产策略及服务未切换。', '', '延迟 BTC 退出后，个币弱势退出仍然生效。BTC 原因退出次数下降可能包含退出原因改为个币的情况，不能全部当作避免卖出；费用金额还受账户资金规模影响，应结合正常成交次数阅读。长周期的巨大差额包含复利预算与风控路径的累积影响，不代表每次延迟退出都获利。']
(root/'REPORT.md').write_text('\n'.join(lines)+'\n')
(root/'result_verification.json').write_text(json.dumps(dict(passed=True,rule_checks=checks['count'],actual_exit_checks=exit_checks,baseline_and_hold_metric_matches=114,max_ledger_error=max(errors),data_hashes_unchanged=True,windows=19),indent=2)+'\n')
print(json.dumps(dict(comparisons=comparisons),indent=2),flush=True)
sys.stdout.flush()
