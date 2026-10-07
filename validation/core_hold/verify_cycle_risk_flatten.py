"""核对单文件迁移的六窗口、逐日权益及全部成交。"""
from pathlib import Path
import csv,gzip,json,math,hashlib
R=Path(__file__).parent;D=R/'cycle_risk_flatten_verification';OLD=R/'cycle_risk_coin_momentum_revision';NAME='BtcCoinGuardCycleRiskStrategy'
new=list(csv.DictReader((D/'summary.csv').open()));old=list(csv.DictReader((OLD/'summary.csv').open()));max_error=0.;days=trades=orders=0
# 容许浮点序列化误差；交易方向、标签、时间和笔数必须相同。
def compare(a,b,path):
 global max_error
 if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)):
  if math.isnan(a) and math.isnan(b):return
  error=abs(a-b);max_error=max(max_error,error);assert error<1e-7,(path,a,b)
 elif isinstance(a,dict):
  assert set(a)==set(b),(path,'keys')
  for key in a:
   if key in {'trade_id','id'}:continue
   compare(a[key],b[key],path+'/'+key)
 elif isinstance(a,list):
  assert len(a)==len(b),(path,'length')
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
 else:assert a==b,(path,a,b)
for row in new:
 match=[x for x in old if x['window']==row['window'] and x['strategy']==row['strategy']];assert len(match)==1
 for key in ['start','end','days','strategy']:assert row[key]==match[0][key]
 for key in ['return_pct','wallet_drawdown_pct','ending_equity','mean_idle_cash_pct']:compare(float(row[key]),float(match[0][key]),row['window']+'/'+key)
 label=row['window'];strategy=row['strategy'];filename='equity_'+strategy+'.csv'
 a=list(csv.DictReader((D/'results'/label/filename).open()));b=list(csv.DictReader((OLD/'results'/label/filename).open()));assert len(a)==len(b)
 for left,right in zip(a,b):
  assert left['']==right['']
  for key in left:
   if key=='':continue
   compare(float(left[key]),float(right[key]),label+'/'+key)
 if strategy==NAME:
  days+=len(a);a=json.load(gzip.open(D/'results'/label/(NAME+'.json.gz'),'rt'));b=json.load(gzip.open(OLD/'results'/label/(NAME+'.json.gz'),'rt'));compare(a['trades'],b['trades'],label+'/trades');trades+=len(a['trades']);orders+=sum(len(t['orders']) for t in a['trades'])
  a=json.loads((D/'results'/label/('risk_trace_'+NAME+'.json')).read_text());b=json.loads((OLD/'results'/label/('risk_trace_'+NAME+'.json')).read_text());compare(a,b,label+'/risk_trace')
for name,expected in json.loads((D/'source_manifest.json').read_text()).items():
 assert hashlib.sha256((D/'strategies'/name).read_bytes()).hexdigest()==expected
 assert hashlib.sha256((R.parent.parent/'user_data/strategies'/name).read_bytes()).hexdigest()==expected
archive=R.parent.parent/'user_data/archive/cycle_risk_flatten_20261007';manifest=json.loads((archive/'manifest.json').read_text())
for name,expected in manifest['frozen_sources'].items():assert hashlib.sha256((archive/'strategies'/name).read_bytes()).hexdigest()==expected
checks=json.loads((D/'rule_checks.json').read_text());assert checks['passed']
loading=json.loads((D/'loading_checks.json').read_text());assert loading['passed']
archived=json.loads((D/'archived_entrypoint_checks.json').read_text());assert archived['passed']
report={'passed':True,'native_runs':6,'matching_summary_rows':len(new),'compared_strategy_days':days,'compared_trades_including_terminal_force_exit':trades,'compared_orders_including_terminal_force_exit':orders,'max_numeric_difference':max_error,'daily_equity_matches':True,'all_fills_match':True,'risk_traces_match':True,'rule_checks':checks,'loading_checks':loading,'archived_entrypoint_checks':archived,'archive_hashes_match':True,'active_source_matches_replayed_source':True,'custom_files_before':4,'custom_files_after':1,'custom_classes_before':8,'custom_classes_after':1}
(D/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
lines=['# CycleRisk 正式版单文件迁移','','正式类保持BtcCoinGuardCycleRiskStrategy，依赖从4个自定义Python文件、8个策略类缩短至1个文件、1个策略类，直接继承IStrategy。正式参数、进退出、冷却、独立复利预算、账户降仓及BTC风险重启不变；删去未参与正式决策的周线和熊市/核心仓指标计算。','','历史实现与研究配置归档至user_data/archive/cycle_risk_flatten_20261007。原Portfolio/FastTest和Compose引用的周线策略继续保留；运行服务未切换、未重启。原有账户风险状态重启持久化缺口仍存在，本次仅整理结构。','','## 六窗口与旧版一致','','| 区间 | 收益 | 最大回撤 |','|---|---:|---:|']
for x in new:
 if x['strategy']==NAME:lines.append(f"| {x['start']}～{x['end']} | {float(x['return_pct']):+.2f}% | {float(x['wallet_drawdown_pct']):.2f}% |")
lines += ['','不仅最终指标相同：逐日权益、完整交易记录、全部订单及每日风险轨迹均核对。已完成边界与因果性检查；额外信号列删除是有意的，使用这些历史列的第三方扩展需继续使用归档父类或显式迁移。','',json.dumps(report,ensure_ascii=False),'','复现：以原研究容器挂载方式运行run_cycle_risk_flatten_verification.py，再运行test_cycle_risk_flatten.py，宿主机运行verify_cycle_risk_flatten.py。使用同一冻结行情、手续费和1000 USDT账户，不引入新的参数选择。','']
(D/'REPORT.md').write_text('\n'.join(lines))
