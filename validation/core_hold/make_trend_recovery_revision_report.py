"""汇总两项固定改动，复核趋势恢复基准、原正式版与持有。"""
from pathlib import Path
import csv,json,hashlib
R=Path(__file__).parent;D=R/'trend_recovery_revision';O=R/'sol_upside_revision_v2'
BASE='BtcCoinGuardTrendRecoveryRiskStrategy';F='BtcCoinGuardCycleRiskStrategy';P='BtcCoinGuardPendingRecoveryStrategy';C='BtcCoinGuardConfirmedCoinExitStrategy';H='BuyAndHold'
names={F:'原正式版',BASE:'趋势恢复版',P:'冷却补恢复',C:'中期确认退出',H:'持有'}
checks=[];lines=['# 趋势恢复版继续优化','', '固定测试两个独立改动：冷却期间出现的恢复事件，在趋势持续有效且冷却结束时补执行；个币弱势退出增加 EMA20≤EMA50 确认。BTC 退出、入场、原回撤阈值不变，未做参数搜索。','', '口径：初始 1000 USDT，双边手续费各 0.1%，日线收盘权益最大回撤；持有不再平衡。单币账户与三币共享账户分别测算。近期截止 2026-10-05。所有窗口均是已知历史，重叠窗口不视为独立验证。','']
combined=[];maxerr=0
for scope,d,o in [('单币',D,O),('三币组合',D/'portfolio',O/'portfolio')]:
 rows=list(csv.DictReader((d/'summary.csv').open()));old=list(csv.DictReader((o/'summary.csv').open()))
 expected=72 if scope=='单币' else 20
 assert len(rows)==expected,(scope,len(rows))
 key=lambda x:(x.get('pair','BTC/SOL/ETH'),x['window'],x['strategy'])
 anchors={key(x):x for x in old}
 for x in rows:
  if x['strategy'] in [BASE,H]:
   prev=anchors[key(x)]
   for metric in ['return_pct','wallet_drawdown_pct']:assert abs(float(x[metric])-float(prev[metric]))<1e-7,(scope,key(x),metric)
   checks.append(key(x))
  maxerr=max(maxerr,abs(float(x.get('ledger_error') or 0)))
 for f,sha in json.loads((d/'source_manifest.json').read_text()).items():assert hashlib.sha256((d/'strategies'/f).read_bytes()).hexdigest()==sha
 rows += [x for x in old if x['strategy']==F]
 for x in rows:combined.append({'scope':scope,'pair':x.get('pair','BTC/SOL/ETH'),'window':x['window'],'strategy':x['strategy'],'return_pct':x['return_pct'],'wallet_drawdown_pct':x['wallet_drawdown_pct']})
 cases=list(dict.fromkeys((x.get('pair','BTC/SOL/ETH'),x['window']) for x in rows))
 for pair,window in cases:
  lines += [f'## {scope} {pair} · {window}','','| 版本 | 收益率 | 最大回撤 |','|---|---:|---:|']
  group={x['strategy']:x for x in rows if x.get('pair','BTC/SOL/ETH')==pair and x['window']==window}
  for n in [F,BASE,P,C,H]:
   x=group[n];lines.append(f"| {names[n]} | {float(x['return_pct']):+.2f}% | {float(x['wallet_drawdown_pct']):.2f}% |")
  lines.append('')
checksfile=json.loads((D/'rule_checks.json').read_text());assert checksfile['passed']
verification={'passed':True,'native_runs':69,'single_coin_cases':18,'portfolio_cases':5,'matching_recovery_hold_anchor_rows':len(checks),'max_final_ledger_error_usdt':maxerr,'rule_checks':checksfile,'frozen_source_hashes_match':True}
(D/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
with (D/'comparison.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=list(combined[0]),lineterminator="\n");w.writeheader();w.writerows(combined)
lines += ['## 验证','',f"69 次原生回测；{len(checks)} 条趋势恢复版/持有基准复现；{checksfile['tests_run']} 项新规则检查通过；最大现金账本误差 {maxerr:.3g} USDT。原正式版复用上轮冻结结果。风控内部峰值重置不会重置报告最大回撤。",'']
(D/'REPORT.md').write_text('\n'.join(lines))
print(json.dumps(verification,ensure_ascii=False))
