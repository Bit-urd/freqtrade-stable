import csv,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';hold='BuyAndHold';names=[old,new,hold]
windows=json.loads((root/'windows.json').read_text());plan=json.loads((root/'plan.json').read_text());coverage=list(csv.DictReader((root/'coverage.csv').open()));raw=list(csv.DictReader((root/'summary.csv').open()));idx={(r['window'],r['strategy']):r for r in raw}
assert len(raw)==len(windows)*3
comparisons=[]
for w in windows:
 c=dict(window=w['label'],scope=w['scope'],phase=w['phase'],start=w['start'],end=w['end'],active_pair_count=len(w['pairs']),slot_count=w['slots'],active_pairs=','.join(w['pairs']))
 for n,p in [(old,'original'),(new,'two_day'),(hold,'hold')]:
  r=idx[w['label'],n]
  for key in ['return_pct','wallet_drawdown_pct','ending_equity','mean_idle_cash_pct','normal_fills','normal_fees','quick_loss_positions']:
   c[p+'_'+key]=float(r[key]) if r[key] not in ['',None] else None
 c['return_change_pp']=c['two_day_return_pct']-c['original_return_pct'];c['drawdown_change_pp']=c['two_day_wallet_drawdown_pct']-c['original_wallet_drawdown_pct'];c['relative_ending_wealth_change_pct']=(c['two_day_ending_equity']/c['original_ending_equity']-1)*100
 comparisons.append(c)
ci={c['window']:c for c in comparisons}
def save(file,rows):
 with (root/file).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
save('all_comparisons.csv',comparisons)
matrix=[]
for c in coverage:
 r=ci.get(c['asset']+'_'+c['phase']);d=dict(c)
 for p in ['original','two_day','hold']:
  for key in ['return_pct','wallet_drawdown_pct']:d[p+'_'+key]=r[p+'_'+key] if r else None
 d['return_change_pp']=r['return_change_pp'] if r else None;d['drawdown_change_pp']=r['drawdown_change_pp'] if r else None
 matrix.append(d)
save('single_phase_matrix.csv',matrix)
def tally(cs,a='two_day',b='original'):
 dr=[c[a+'_return_pct']-c[b+'_return_pct'] for c in cs];dd=[c[a+'_wallet_drawdown_pct']-c[b+'_wallet_drawdown_pct'] for c in cs]
 return dict(n=len(cs),return_better=sum(x>1e-6 for x in dr),return_worse=sum(x< -1e-6 for x in dr),return_equal=sum(abs(x)<=1e-6 for x in dr),dd_better=sum(x< -1e-6 for x in dd),dd_worse=sum(x>1e-6 for x in dd),dd_equal=sum(abs(x)<=1e-6 for x in dd),joint_better=sum(r>1e-6 and d< -1e-6 for r,d in zip(dr,dd)),median_return_change_pp=statistics.median(dr),median_dd_change_pp=statistics.median(dd))
aggregate={}
for scope in dict.fromkeys(c['scope'] for c in comparisons):
 cs=[c for c in comparisons if c['scope']==scope];aggregate[scope]={'two_day_vs_original':tally(cs),'original_vs_hold':tally(cs,'original','hold'),'two_day_vs_hold':tally(cs,'two_day','hold')}
(root/'aggregate.json').write_text(json.dumps(aggregate,indent=2)+'\n')
lines=['# 指定十二标的：原版、BTC 两天退出与持有','',
'币池：BTC、ETH、BNB、LINK、XRP、UNI、ZEC、DOGE、SOL、ARB、PUMP、HYPE。用户确认沿用现货口径，因此永续代码统一对应 Binance USDT 现货；本轮没有杠杆、资金费率或做空。','',
f"完成 {len(windows)*2} 次新原生策略回测和 {len(windows)} 条持有基准，共 {len(raw)} 条权益曲线。正式策略和运行服务未修改。研究重点是这组实际币池的连续组合，不以单币阶段胜率决定正式升级。",'',
'## 数据与比较口径','',
'- 资金 1000 USDT，每边手续费 0.1%，滑点 0，日线、只做多；冻结完整历史至 2026-10-06。两版除 BTC 弱势退出从一天改为连续两天外，入场、个币两天退出、14日冷却、各币独立预算复利和账户风控均相同。',
'- 收益按期末现金与持仓的收盘价权益计算；最大回撤是包含现金的日线收盘账户峰值回撤。三组均不额外强制卖出末日仓位；summary.csv 另列统一假定清仓收益 liquidated_return_pct。',
'- 持有按各币等预算，在窗口开始的开盘价买入、扣买入费；历史尚未完成60日暖机的币，按与此前研究相同口径，预算先留现金、完成暖机后买入。持有不等待 MA150、不择时、不减仓；这会使上市初期参与时间与策略不同，相关案例单列。',
'- 每个窗口独立开户，窗口内持仓、复利和风险峰值连续继承；不同窗口不继承。P6与P7重叠，窗口次数不是独立样本概率，阶段收益不能相加或连乘。',
'- 历史可交易池只包含阶段内有足够暖机历史的币，资金按当期可测币数划分；固定十二槽位版本始终每币预留1/12预算，尚未上市或不能暖机的预算留现金。两类账户分别报告，现金预留导致的风险差异不归因于新币收益。',
'- 连续组合均尽量从该固定币池所有成员已形成 MA150 后开始，以减少上市初期等待的干扰。PUMP 另列60日暖机后和MA150就绪后两个单币窗口。HYPE仅13根日线，无法进行策略暖机；十二槽位近期账户实质为十一币加8.33%初始现金预算，不能当成已验证完整十二币。',
'- 按用户要求综合关键行情收益、最终复利、最差阶段损失和回撤，不设置固定回撤门槛，也不按阶段胜率直接淘汰候选。这是事后指定币池的历史研究，未称为样本外验证。','',
'## 历史覆盖','', '|标的|Binance现货首日|日线数|60日暖机后可执行起点|MA150就绪后可执行起点|','|---|---|---:|---|---|']
for d in json.loads((root/'data_audit.json').read_text()):lines.append(f"|{d['asset']}|{d['first']}|{d['rows']}|{d['warm_start'] or '尚未完成'}|{d['ma150_start'] or '尚未完成'}|")
lines+=['',f"P1–P8 共96个单币请求：{plan['eligible_single_phase_cases']}个可测，{plan['unavailable_phase_cells']}个不可用，{plan['partial_single_phase_cases']}个部分区间。PUMP、HYPE都没有P1–P8的现货历史。",'',
'## 连续组合：正式升级的主要依据','', '**下表每组均为收益 / 最大回撤，单位 %；变化列单位为百分点。** `Legacy9` 为前九币（不含 ARB/PUMP/HYPE），`Main10` 加 ARB，`Mature11` 再加 PUMP。十二槽位版额外保留 HYPE 的1/12初始预算为现金。','']
header=['|窗口与实际币数 / 槽位|日期|原版收益 / 回撤|两天退出收益 / 回撤|持有收益 / 回撤|收益变化 pp|回撤变化 pp|','|---|---|---:|---:|---:|---:|---:|']
def table_rows(cs):
 out=[]
 for c in cs:
  vals=[f"{c[p+'_return_pct']:+.2f}% / {c[p+'_wallet_drawdown_pct']:.2f}%" for p in ['original','two_day','hold']]
  out.append(f"|{c['window']}（{c['active_pair_count']}/{c['slot_count']}）|{c['start']}—{c['end']}|{'|'.join(vals)}|{c['return_change_pp']:+.2f}|{c['drawdown_change_pp']:+.2f}|")
 return out
continuous=[c for c in comparisons if c['scope'].startswith('continuous_pool')]
lines+=header+table_rows(continuous)
lines+=['','## 加入 PUMP 与 HYPE 现金预留的同日期控制','',
'以下起止日期相同，区别仅为币池与预算槽位。加入PUMP会改变其他币预算及组合风险路径，因此差异是整体配置效果，不等于PUMP单币收益的直接贡献。逐币盈亏见 profit_attribution.csv。','']
control=[ci[label] for label in ['Main10_mature11_control','Mature11_full_cycle','Requested12_mature11_cash']]
lines+=header+table_rows(control)
lines+=['','### PUMP 单币','']+header+table_rows([c for c in comparisons if c['scope'].startswith('new_asset')])
h=json.loads((root/'hype_listing_hold_only.json').read_text())
lines+=['','### HYPE：目前只能描述持有，不能评估策略','',f"本交易所现货仅有 {h['start']}—{h['end']} 的 {h['days']} 根日线。上市首日开盘买入、扣0.1%买入费后的持有收益 {h['return_pct']:+.2f}%，日线收盘回撤 {h['wallet_drawdown_pct']:.2f}%。原版和两天版均不满足暖机/MA150，不能把等待期零交易当作策略优势；不参与两版胜率或升级判断。",'',
'## P1–P8 组合','',
'同一阶段分别给出历史可交易池（资金投入当期可测币）和固定十二槽位账户（缺历史的预算留现金）。持有也使用相同预算与买入资格。','']
for scope,title in [('phase_pool','历史可交易池'),('phase_pool_reserved','固定十二槽位，缺历史预算留现金')]:
 lines+=['### '+title,'']+header+table_rows([c for c in comparisons if c['scope']==scope])+['']
lines+=['## 分组统计','', '|窗口类型|案例数|两天版收益改善/下降/相同|回撤改善/扩大/相同|收益和回撤同时改善|原版收益胜持有|两天版收益胜持有|','|---|---:|---|---|---:|---:|---:|']
for scope,g in aggregate.items():
 s=g['two_day_vs_original'];lines.append(f"|{scope}|{s['n']}|{s['return_better']}/{s['return_worse']}/{s['return_equal']}|{s['dd_better']}/{s['dd_worse']}/{s['dd_equal']}|{s['joint_better']}|{g['original_vs_hold']['return_better']}|{g['two_day_vs_hold']['return_better']}|")
lines+=['','这些是描述性次数，窗口有重叠，不能当作独立验证票数；同日期控制窗口也不与其他连续窗口重复累计成实际账户。','',
'## 图表','', '![组合收益与回撤](portfolio_return_drawdown.png)','', '![连续权益曲线](continuous_equity.png)','',
'## 十二币 P1–P8 完整单币结果','', '每组三列均为收益 / 最大回撤；`*` 为部分区间，`†` 为有效起点MA150未形成。','']
for p in json.loads((root/'periods.json').read_text()):
 lines += [f"### {p['id']} {p['start']}—{p['end']}：{p['type']}",'','|标的|原版收益 / 回撤|两天版收益 / 回撤|持有收益 / 回撤|实际覆盖 / 原因|','|---|---:|---:|---:|---|']
 for r in [r for r in matrix if r['phase']==p['id']]:
  if r['status']=='unavailable':lines.append(f"|{r['asset']}|不可用|不可用|不可用|{r['reason']}|");continue
  asset=r['asset']+('*' if r['status']=='partial' else '')+('†' if r['ma150_ready_at_start']=='False' else '')
  vals=[f"{r[n+'_return_pct']:+.2f}% / {r[n+'_wallet_drawdown_pct']:.2f}%" for n in ['original','two_day','hold']]
  note=r['effective_start']+'—'+r['effective_end'] if r['status']=='partial' else '完整'
  if r['ma150_ready_at_start']=='False':note+='；等待MA150'
  lines.append(f"|{asset}|{'|'.join(vals)}|{note}|")
lines+=['','## 验证与可复现文件','']
v=json.loads((root/'verification.json').read_text());a=json.loads((root/'audit_verification.json').read_text())
lines += [f"- {v['count']}项规则/截断历史检查通过；除BTC退出确认外指标与规则一致，增加2026-09-30截断覆盖PUMP/HYPE最近历史。",
 f"- 从成交重建{a['curve_checks']}条权益曲线、核对{a['summary_metric_checks']}项汇总指标、{a['actual_btc_exit_checks']}次实际BTC退出、{a['actual_weak_btc_entry_cooldown_checks']}次弱BTC入场冷却、{a['daily_risk_equity_checks']}日风险权益。最大权益误差{a['max_equity_error']:.10g} USDT，最大原生现金误差{a['max_cash_error']:.10g} USDT。",
 '- 冻结行情及原版/候选/正式策略哈希一致，日线连续性、各窗口实际起止日期及初始钱包均检查。',
 '- [全部105窗口三组CSV](all_comparisons.csv)、[96组合单币矩阵](single_phase_matrix.csv)、[原始指标](summary.csv)、[逐币盈亏](profit_attribution.csv)、[规则检查](verification.json)、[权益审计](audit_verification.json)。',
 '- 原始成交和每日权益在 results/；现货冻结数据与 SHA256 在 data_audit.json；API下载来源在 download_sources.json；raw/futures 是口径确认前探查数据，未用于本轮回测。','']
(root/'REPORT.md').write_text('\n'.join(lines))
print(json.dumps(aggregate,indent=2))
