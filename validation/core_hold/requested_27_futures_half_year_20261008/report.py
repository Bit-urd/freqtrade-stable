import csv,gzip,json
from pathlib import Path
root=Path(__file__).resolve().parent
rows=list(csv.DictReader((root/'summary.csv').open()));windows=json.loads((root/'windows.json').read_text());audit=json.loads((root/'audit_verification.json').read_text());coverage=json.loads((root/'data_audit.json').read_text())
old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';hold='BuyAndHold';idx={(r['window'],r['strategy']):r for r in rows}
comparisons=[]
for window in windows:
 row=dict(window=window['label'],start=window['start'],end=window['end'],pair_count=len(window['pairs']),slot_count=window['slots'])
 for name,prefix in [(old,'original'),(new,'official_two_day'),(hold,'hold')]:
  r=idx[window['label'],name]
  for metric in ['return_pct','wallet_drawdown_pct','ending_equity','trades']:row[prefix+'_'+metric]=r[metric]
  import pandas as pd
  curve=pd.read_csv(root/'results'/window['label']/('equity_'+name+'.csv'));row[prefix+'_funding_pnl_usdt']=float(curve.funding_pnl.iloc[-1])
 comparisons.append(row)
with (root/'comparison.csv').open('w') as f:writer=csv.DictWriter(f,fieldnames=list(comparisons[0]));writer.writeheader();writer.writerows(comparisons)
lines=['# 指定27币近半年：1倍USDT永续合约','', '测试区间2026-04-08—2026-10-07，日线，USDT永续合约、逐仓、仅做多、1倍杠杆，10000USDT初始资金、各币等预算、独立复利。单边手续费假设0.05%，滑点0，按交易所历史实际资金费率与结算标记价计资金费。每日持仓用合约成交日线收盘价估值，资金费使用结算时标记价；未逐小时模拟保证金变化。收益和最大回撤均为日线收盘账户权益，包含手续费与资金费，不把阶段回撤相加。','',
'原版BTC弱势一天退出，正式两天版连续弱势两天退出；个币两天退出、14天冷却和账户风险规则相同。研究专用合约适配修正保证金账户权益，强制杠杆1倍；现货正式策略和运行服务未修改。','',
'27个代码均有对应永续合约，1000BONK和MON使用原代码；没有用BONK现货替代1000BONK合约。GRAM仅有2026-07-02起98根日线，60天暖机后单币窗口为2026-09-01—2026-10-07，仍无MA150，因此两策略不应入场。27币组合保留其预算现金；26币组合去掉GRAM重新分配。其他26币覆盖完整半年且MA150就绪。','',
'## 组合收益与回撤','', '|币池|原版收益 / 回撤|正式两天版收益 / 回撤|1倍持有收益 / 回撤|','|---|---:|---:|---:|']
def values(c):return '|'.join(f"{float(c[p+'_return_pct']):+.2f}% / {float(c[p+'_wallet_drawdown_pct']):.2f}%" for p in ['original','official_two_day','hold'])
for c in [r for r in comparisons if r['window'] in ['Requested27','Mature26','Official9']]:lines.append('|'+c['window']+'|'+values(c)+'|')
lines+=['','## 逐币结果','', '|合约|原版收益 / 回撤|正式两天版收益 / 回撤|1倍持有收益 / 回撤|','|---|---:|---:|---:|']
for c in [r for r in comparisons if r['window'] not in ['Requested27','Mature26','Official9']]:lines.append('|'+c['window']+('（仅暖机后部分区间）' if c['window']=='GRAM' else '')+'|'+values(c)+'|')
lines+=['','## 组合资金费盈亏','', '|币池|原版资金费|正式两天版资金费|持有资金费|','|---|---:|---:|---:|']
for c in [r for r in comparisons if r['window'] in ['Requested27','Mature26','Official9']]:lines.append('|'+c['window']+'|'+'|'.join(f"{c[p+'_funding_pnl_usdt']:+.2f} USDT" for p in ['original','official_two_day','hold'])+'|')
lines+=['','正值表示收取资金费，负值表示支付。按结算时点之前持有的数量计费，开仓时刻不补付已结算资金费，平仓时刻先结算原持仓，防止调整仓位时重复计费。研究回测在Freqtrade原生撮合及仓位规则上替换了该边界资金费计算，并以独立逐事件数量求和重新核验。','',
'持有基准按固定等额初始预算买入、持有数量不再平衡，并持续付/收资金费。为与策略可用历史对齐，单币首次入场至少需61根之前历史，因此GRAM持有从9月1日开始；这不是完整半年持有。现金列使用1倍复制持仓的现金账本，可能因资金费而为负，不等同于交易所可用保证金；权益列才用于收益/回撤比较。','',
'最末日强制平仓订单从每日权益曲线移除，组合以当日收盘持仓加现金估值，包含当日收盘前资金费。原生最终余额另按引擎强制退出时点核对，二者时点不能直接混用。回撤是日收盘口径，不能代表盘中最大损失；滑点0的假设对低流动性合约可能乐观。','',
'## 核验','',f"完成{len(windows)*2}次原生策略回测、{len(windows)}条持有基准；{audit['curve_checks']}条独立权益重建、{audit['summary_metric_checks']}项指标核验、{audit['actual_btc_exit_checks']}次BTC退出核验和{audit['daily_risk_equity_checks']}日风险权益核对通过。最大原生现金误差{audit['max_cash_error']:.8g}USDT，最大每日权益重建误差{audit['max_equity_error']:.8g}USDT。",'',
'[完整CSV](comparison.csv) · [逐币盈亏归因](profit_attribution.csv) · [数据覆盖](data_audit.json) · [权益审计](audit_verification.json) · [策略规则核验](verification.json)。','']
if (root/'DECISION.md').exists():lines+=[(root/'DECISION.md').read_text()]
(root/'REPORT.md').write_text('\n'.join(lines));print('\n'.join(lines[:16]),flush=True)
import os;os._exit(0)
