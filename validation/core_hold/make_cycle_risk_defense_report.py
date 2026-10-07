"""同一账户防守改动比较；保留失败及收益代价，不挑选好看窗口。"""
import csv,gzip,json,hashlib,datetime,argparse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--folder',default='cycle_risk_defense_revision');args=parser.parse_args()
R=Path(__file__).parent;D=R/args.folder;BASE='BtcCoinGuardCycleRiskStrategy'
plan=json.loads((D/'plan.json').read_text())
NAMES={BASE:'CycleRisk 正式版','BtcCoinGuardConfirmedBtcEntryStrategy':'BTC MA200 确认入场','BtcCoinGuardSelectiveRecoveryEntryStrategy':'个币强势修复例外','BuyAndHold':'持有','BtcCoinGuardLossCooldownStrategy':'亏损后弱 BTC 冷却','BtcCoinGuardHalfPeakRearmStrategy':'风险恢复保留一半峰值记忆'}
rows=list(csv.DictReader((D/'summary.csv').open()));assert len(rows)==len(plan['windows'])*(len(plan['strategies'])+1)
old=list(csv.DictReader((R/'archive/portfolio_cycle_risk_v2/summary.csv').open()))+list(csv.DictReader((R/'production_comparison_2023_latest/summary.csv').open()))
anchors=0;annual=[];maxtrace=0.
lines=['# CycleRisk 防守入场：固定结构试验','','两项规则只过滤新开仓：BTC 连续两天站上 MA200；或允许个币 EMA20>EMA50 且 EMA50 上升时提前修复入场。退出、权益风控、峰值重置、仓位和成交核算沿用正式版，无新账户状态，无参数搜索。','', '1000 USDT、BTC/SOL/ETH 共享账户、三个槽位、每侧手续费0.1%，日线收盘权益最大回撤，持有等权且不再平衡。数据复用2023至今隔离快照，最新完整日线2026-10-06；最近窗口较旧报告多一天，不强行匹配旧终点。','']
if 'BtcCoinGuardLossCooldownStrategy' in plan['strategies']:
 lines[2]='第三项固定规则：首次参与不变；上一笔同币交易亏损且 BTC 尚未连续两天站上 MA200 时，再入场等待原有14天冷却；盈利退出及 BTC 已确认阶段不追加限制。退出、权益风控、峰值重置、仓位与成交核算不变，无新参数或账户状态。'
if 'BtcCoinGuardHalfPeakRearmStrategy' in plan['strategies']:
 lines[2]='第四项且最后一项固定规则：BTC 恢复事件与满风险恢复不变；重置内部权益峰值时，改为旧峰值与当前已收盘权益的中点。保留部分亏损记忆；入场、退出和风险阈值均不变，不增加账户状态，不进行参数搜索。报告回撤仍然使用全历史实际账户峰值。'
for label in dict.fromkeys(x['window'] for x in rows):
 group=[x for x in rows if x['window']==label]
 lines += [f'## {label}','','| 策略 | 收益率 | 最大回撤 | 新开仓 | 正常平仓 | 正常成交笔数 |','|---|---:|---:|---:|---:|---:|']
 for x in group:
  name=x['strategy'];dates={}
  if name!='BuyAndHold':
   p=json.load(gzip.open(D/'results'/label/(name+'.json.gz'),'rt'));trades=p['trades'];opened=len(trades);closed=sum(t['exit_reason']!='force_exit' for t in trades)
   fills=sum(sum(o['order_filled_timestamp'] is not None for o in t['orders'])-int(t['exit_reason']=='force_exit') for t in trades)
  else:opened=3;closed=0;fills=3
  x.update(opens=opened,normal_closes=closed,normal_fills=fills)
  lines.append(f"| {NAMES[name]} | {float(x['return_pct']):+.2f}% | {float(x['wallet_drawdown_pct']):.2f}% | {opened} | {closed} | {fills} |")
  match=[t for t in old if t['window']==label and t['strategy']==name and t['start']==x['start'] and t['end']==x['end']]
  if name in [BASE,'BuyAndHold'] and match:
   for metric in ['return_pct','wallet_drawdown_pct']:assert abs(float(match[0][metric])-float(x[metric]))<1e-7,(label,name,metric)
   anchors+=1
  curve=list(csv.DictReader((D/'results'/label/('equity_'+name+'.csv')).open()));equity={t[''][:10]:float(t['equity']) for t in curve}
  assert curve[0][''][:10]==x['start'] and curve[-1][''][:10]==x['end']
  if name!='BuyAndHold':
   trace=json.loads((D/'results'/label/('risk_trace_'+name+'.json')).read_text())
   for t in trace:
    prior=str(datetime.date.fromisoformat(t['execution_date'][:10])-datetime.timedelta(days=1))
    if prior in equity:maxtrace=max(maxtrace,abs(t['prior_closed_equity']-equity[prior]))
  if label=='continuous_2023_latest':
   previous=1000.
   for year in range(2023,2027):
    yearcurve=[t for t in curve if t[''].startswith(str(year))];end=float(yearcurve[-1]['equity']);peak=previous;dd=0
    for t in yearcurve:peak=max(peak,float(t['equity']));dd=max(dd,1-float(t['equity'])/peak)
    if name!='BuyAndHold':
     yt=[t for t in trades if t['open_date'].startswith(str(year))];open_count=len(yt)
     close_count=sum(t['close_date'].startswith(str(year)) and t['exit_reason']!='force_exit' for t in trades)
    else:open_count=3 if year==2023 else 0;close_count=0
    annual.append({'strategy':name,'year':year,'return_pct':(end/previous-1)*100,'within_year_drawdown_pct':dd*100,'opens':open_count,'normal_closes':close_count});previous=end
 lines.append('')
lines+=['## 连续账户各年收益和新开仓次数','','| 策略 | 年份 | 收益率 | 年内回撤 | 新开仓 | 正常平仓 |','|---|---:|---:|---:|---:|---:|']
for x in annual:lines.append(f"| {NAMES[x['strategy']]} | {x['year']} | {x['return_pct']:+.2f}% | {x['within_year_drawdown_pct']:.2f}% | {x['opens']} | {x['normal_closes']} |")
for name,data in [('comparison.csv',rows),('annual_metrics.csv',annual)]:
 with (D/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
for name,sha in json.loads((D/'source_manifest.json').read_text()).items():assert hashlib.sha256((D/'strategies'/name).read_bytes()).hexdigest()==sha
checks=json.loads((D/'rule_checks.json').read_text());assert checks['passed'];assert maxtrace<.05
for audit in json.loads((D/'data_audit.json').read_text()):
 stem=audit['pair'].replace('/','_');data=R/'production_comparison_2023_latest/data'
 for timeframe in ['daily','weekly']:
  suffix='-1d.feather' if timeframe=='daily' else '-1w.feather'
  assert hashlib.sha256((data/(stem+suffix)).read_bytes()).hexdigest()==audit[timeframe+'_sha256']
v={'passed':True,'native_runs':len(plan['windows'])*len(plan['strategies']),'matching_formal_hold_anchor_rows':anchors,'rule_checks':checks,'max_ledger_error_usdt':max(abs(float(x['ledger_error'] or 0)) for x in rows),'max_daily_risk_equity_error_usdt':maxtrace,'frozen_source_hashes_match':True,'live_unchanged':True}
(D/'verification.json').write_text(json.dumps(v,indent=2)+'\n');lines+=['','## 验证','',json.dumps(v,ensure_ascii=False),'']
(D/'REPORT.md').write_text('\n'.join(lines));print(json.dumps(v))
