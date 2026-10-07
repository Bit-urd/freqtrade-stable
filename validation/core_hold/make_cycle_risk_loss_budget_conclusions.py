"""汇总三个固定亏损预算试验；保留不利阶段与调仓次数。"""
from pathlib import Path
import csv,gzip,json
R=Path(__file__).parent;D=R/'cycle_risk_latched_budget_revision'
folders=['cycle_risk_loss_budget_revision','cycle_risk_latched_budget_revision'];allrows={};counts=[]
for folder in folders:
 for x in csv.DictReader((R/folder/'summary.csv').open()):
  key=(x['window'],x['strategy'])
  if key in allrows:
   for metric in ['return_pct','wallet_drawdown_pct']:assert abs(float(allrows[key][metric])-float(x[metric]))<1e-7
  allrows[key]=x
  p=R/folder/'results'/x['window']/(x['strategy']+'.json.gz')
  if not p.exists():continue
  trades=json.load(gzip.open(p,'rt'))['trades'];adds=cuts=0
  for t in trades:
   filled=[o for o in t['orders'] if o['order_filled_timestamp'] is not None]
   for i,o in enumerate(filled):
    if i==0 or (t['exit_reason']=='force_exit' and i==len(filled)-1):continue
    adds+=int(o['ft_is_entry']);cuts+=int(not o['ft_is_entry'] and i<len(filled)-1)
  counts.append({'folder':folder,'window':x['window'],'strategy':x['strategy'],'adds':adds,'partial_reductions':cuts,'opens':len(trades)})
with (D/'position_adjustment_counts.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(counts[0]),lineterminator='\n');w.writeheader();w.writerows(counts)
names={'BtcCoinGuardCycleRiskStrategy':'正式版','BtcCoinGuardLossBudgetStrategy':'亏损预算','BtcCoinGuardTrendRestoreBudgetStrategy':'预算＋动态趋势恢复','BtcCoinGuardLatchedBudgetStrategy':'预算＋恢复保持至该笔结束','BuyAndHold':'持有'}
labels={'ref_bull_2023_2024':'2023–2024上涨','ref_bull_to_bear_2021':'牛转熊2021-07-01～2022-11-21','ref_bear_2022':'2022熊市至11-21','ref_since_last_september':'2025-09-01～2026-10-06','ref_requested_long':'2022-11-21～2025-10-07','continuous_2023_latest':'2023-01-01～2026-10-06'}
lines=['# 个币亏损预算：综合结论','','本轮三项结构试验没有达到保留大部分收益且明显降低完整周期回撤的综合要求。正式版和运行策略未修改；三个候选均只保留研究记录，不升级正式版，不作为新的通用优先版本。','','## 固定规则','','一笔亏损后个币预算75%，连续两笔或更多亏损后50%，盈利平仓解除；第二版允许close>EMA20>EMA50且EMA50上升时动态解除；第三版将该笔交易已经观察到的趋势确认保存在交易自定义字段，不因后续普通回调重新限制。所有个币预算与账户目标取较小值，BTC账户峰值重置不能绕过个币约束。沿用已有档位和均线，不搜索参数。','','第三版增加一项可持久化的每交易趋势确认标记；它不代表加仓已成交。实际风险档位仍只在order_filled中更新。原正式版账户风控的重启持久化缺口未解决。','','## 完整六窗口','','以下每格为收益率 / 日线权益最大回撤，均含费用。1000 USDT，BTC/SOL/ETH共享账户，每侧手续费0.1%；持有初始等额、不再平衡。','', '| 时间段 | 正式版 | 亏损预算 | 动态恢复 | 恢复保持 | 持有 |','|---|---:|---:|---:|---:|---:|']
for label in labels:
 values=[]
 for name in names:
  x=allrows[(label,name)];values.append(f"{float(x['return_pct']):+.2f}% / {float(x['wallet_drawdown_pct']):.2f}%")
 lines.append('| '+labels[label]+' | '+' | '.join(values)+' |')
lines += ['', '## 是否值得采用','','恢复保持版在连续2023至今收益368.56%，约为持有收益的66.95%，符合这个窗口约2/3的目标；相比正式版少赚48.57个百分点，收益率相对下降11.64%，终值约少9.39%。回撤降低约4.00个百分点，仍有45.71%。','','但指定长周期少赚123.35个百分点，回撤仅降低3.27个百分点；上涨期少赚87.18个百分点，回撤仅降低0.30个百分点。相比之下，2022熊市和近期均降低亏损与回撤，属于防守折中，不是通用显著改进。不能仅按最近窗口或一个收益占比选正式版。','','动态恢复版在指定长周期产生95次加仓、93次部分减仓，正式版为9次、11次；恢复保持版降至24次、8次，长周期收益从322.55%恢复到374.08%，但上涨期收益反而从465.65%降至440.61%。交易减少并不自动代表收益改善，也不能将所有差额归因于手续费。','','恢复保持版自身最大回撤的峰值日期仍为2025-01-18，峰值权益6707.78，谷底2026-08-19为3641.48；正式版峰值7888.61、谷底2026-08-11为3967.34。峰值和谷底均降低，回撤改善伴随放弃上涨收益，不是毫无代价。两个谷底日期不同；不把各自峰谷损益差当作同一时间边界下的独立因果贡献。','','## 验证与停止条件','','第一组18次原生回测，第二组12次，共30次调用；两组分别27和36项规则检查通过（含重复的原风控测试）。各自复现10条正式/持有基准，逐笔账本与每日风控权益误差低于0.000001 USDT；数据与冻结源码哈希核对通过。第三版每币归因合计也与账户曲线核对通过。详细频率、年度收益和核对信息见两个REPORT.md及verification.json。','','本轮不继续调亏损次数、预算比例、均线天数以追求这个历史样本的更好结果。已验证上一笔盈亏是过于粗糙的风险状态代理；单靠它无法同时保护老仓回吐、减少弱势再入场并保留主要趋势收益。后续如研究其他结构，应先解释为何能区分趋势恢复和反弹，而非仅叠加更多限制。已看过的历史不作为独立样本外证据。','']
(D/'CONCLUSIONS.md').write_text('\n'.join(lines))
selection={'status':'research_not_adopted','formal_unchanged':True,'reason':'熊市与近期改善，但上涨/指定长周期收益代价过大；连续窗口回撤45.71%仍高，仅降约4个百分点，不满足通用显著改进要求。','profiles':[n for n in names if n not in ['BtcCoinGuardCycleRiskStrategy','BuyAndHold']]}
(D/'SELECTION.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
(R/'cycle_risk_loss_budget_revision/SELECTION.json').write_text(json.dumps({'status':'rejected','reason':'亏损预算和动态恢复完整周期收益损失过大，第三版也未达通用显著改进要求，全部保留记录。'},ensure_ascii=False,indent=2)+'\n')
print('Saved combined conclusions and adjustment audit.')
