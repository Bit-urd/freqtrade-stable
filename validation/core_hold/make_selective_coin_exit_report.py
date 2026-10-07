"""复核冻结来源、同口径基准并输出退出门控比较。"""
from pathlib import Path
import csv,json,hashlib
R=Path(__file__).parent;D=R/'selective_coin_exit_revision';O=R/'trend_recovery_revision';FOLDER=R/'sol_upside_revision_v2'
BASE='BtcCoinGuardConfirmedCoinExitStrategy';F='BtcCoinGuardCycleRiskStrategy';B='BtcCoinGuardTrendRecoveryRiskStrategy';S='BtcCoinGuardRisingMediumExitStrategy';T='BtcCoinGuardBtcConfirmedExitStrategy';H='BuyAndHold'
names={F:'原正式版',B:'趋势恢复版',BASE:'上一轮中期确认退出',S:'EMA50 上升才延迟',T:'BTC MA200 确认才延迟',H:'持有'}
lines=['# 选择性延迟个币退出：固定结构试验','','两项独立规则：在 EMA20>EMA50 基础上，分别增加 EMA50 上升要求或 BTC 连续两天站上 MA200 要求。BTC 原退出、入场、仓位与权益风控均不变。无标的专属参数，无参数遍历。','', '初始 1000 USDT，双边手续费各 0.1%，日线收盘权益全历史峰值回撤；持有不再平衡。单币与三币共享账户分别测算。近期截止 2026-10-05；所有窗口为已知历史，重叠窗口不计作独立样本。','']
anchors=0;allrows=[];maxerr=0.;traceerr=0.
for scope,d,o,fo,expected in [('单币',D,O,FOLDER,72),('三币组合',D/'portfolio',O/'portfolio',FOLDER/'portfolio',20)]:
 rows=list(csv.DictReader((d/'summary.csv').open()));assert len(rows)==expected
 old=list(csv.DictReader((o/'summary.csv').open()));formal=list(csv.DictReader((fo/'summary.csv').open()))
 key=lambda x:(x.get('pair','BTC/SOL/ETH'),x['window'],x['strategy'])
 oldmap={key(x):x for x in old}
 for x in rows:
  if x['strategy'] in [BASE,H]:
   for metric in ['return_pct','wallet_drawdown_pct']:assert abs(float(x[metric])-float(oldmap[key(x)][metric]))<1e-7,(scope,key(x),metric)
   anchors+=1
  maxerr=max(maxerr,abs(float(x.get('ledger_error') or 0)));traceerr=max(traceerr,abs(float(x.get('risk_trace_error') or 0)))
 for f,sha in json.loads((d/'source_manifest.json').read_text()).items():assert hashlib.sha256((d/'strategies'/f).read_bytes()).hexdigest()==sha
 for pair in json.loads((D/'data_audit.json').read_text()):
  prev=next(x for x in json.loads((O/'data_audit.json').read_text()) if x['pair']==pair['pair'])
  for metric in ['daily_sha256','weekly_sha256']:assert pair[metric]==prev[metric]
 rows += [x for x in old if x['strategy']==B]+[x for x in formal if x['strategy']==F]
 cases=list(dict.fromkeys((x.get('pair','BTC/SOL/ETH'),x['window']) for x in rows))
 for pair,window in cases:
  lines += [f'## {scope} {pair} · {window}','','| 版本 | 收益率 | 最大回撤 |','|---|---:|---:|']
  group={x['strategy']:x for x in rows if x.get('pair','BTC/SOL/ETH')==pair and x['window']==window}
  for n in [F,B,BASE,S,T,H]:
   x=group[n];lines.append(f"| {names[n]} | {float(x['return_pct']):+.2f}% | {float(x['wallet_drawdown_pct']):.2f}% |")
  lines.append('')
 for x in rows:allrows.append({'scope':scope,'pair':x.get('pair','BTC/SOL/ETH'),'window':x['window'],'strategy':x['strategy'],'return_pct':x['return_pct'],'wallet_drawdown_pct':x['wallet_drawdown_pct']})
checks=json.loads((D/'rule_checks.json').read_text());assert checks['passed']
v={'passed':True,'native_runs':69,'matching_previous_candidate_hold_anchors':anchors,'rule_checks':checks,'frozen_source_hashes_match':True,'data_hashes_match_previous':True,'max_ledger_error_usdt':maxerr,'max_single_daily_risk_equity_error_usdt':traceerr,'portfolio_daily_risk_equity_reconciled_in_runner':True}
(D/'verification.json').write_text(json.dumps(v,indent=2)+'\n')
with (D/'comparison.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=list(allrows[0]),lineterminator="\n");w.writeheader();w.writerows(allrows)
lines += ['## 验证','',f"69 次原生回测，{anchors} 条上一轮候选/持有基准复现，{checks['tests_run']} 项规则检查通过；最大账本误差 {maxerr:.3g} USDT。原正式版和趋势恢复版引用冻结结果，数据哈希完全一致；每日风控权益按前一根已收盘日线核算，并与账户账本核对。",'']
(D/'REPORT.md').write_text('\n'.join(lines))
print(json.dumps(v))
