"""Build the requested 96-cell comparison, including explicit unavailable cells."""
import csv,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
old='BtcCoinGuardCycleRiskStrategy';new='BtcTwoDayExitCycleRiskStrategy';hold='BuyAndHold'
names=[old,new,hold];labels={old:'原版',new:'BTC两天退出',hold:'持有'}
coverage=list(csv.DictReader((root/'coverage.csv').open()));summary=list(csv.DictReader((root/'summary.csv').open()))
idx={(r['window'],r['strategy']):r for r in summary};periods=json.loads((root/'periods.json').read_text());assets=json.loads((root/'plan.json').read_text())['assets']
assert len(summary)==249 and len(coverage)==96
cases=[]
for c in coverage:
 d=dict(c)
 for name,prefix in [(old,'original'),(new,'two_day'),(hold,'hold')]:
  r=idx.get((c['asset']+'_'+c['phase'],name))
  for key in ['return_pct','wallet_drawdown_pct','normal_fills','quick_loss_positions','mean_idle_cash_pct','normal_fees']:
   d[prefix+'_'+key]=float(r[key]) if r and r[key] not in ['',None] else None
 if c['status']!='unavailable':
  d['return_change_pp']=d['two_day_return_pct']-d['original_return_pct']
  d['relative_ending_wealth_change_pct']=((100+d['two_day_return_pct'])/(100+d['original_return_pct'])-1)*100
  d['drawdown_change_pp']=d['two_day_wallet_drawdown_pct']-d['original_wallet_drawdown_pct']
 else:
  d.update(return_change_pp=None,relative_ending_wealth_change_pct=None,drawdown_change_pp=None)
 cases.append(d)
with (root/'comparison_matrix.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
eligible=[c for c in cases if c['status']!='unavailable'];mature=[c for c in eligible if c['status']=='full' and c['ma150_ready_at_start']=='True']
def tally(cs,a='two_day',b='original'):
 dr=[c[a+'_return_pct']-c[b+'_return_pct'] for c in cs];dd=[c[a+'_wallet_drawdown_pct']-c[b+'_wallet_drawdown_pct'] for c in cs]
 return dict(n=len(cs),return_better=sum(x>1e-6 for x in dr),return_worse=sum(x< -1e-6 for x in dr),return_equal=sum(abs(x)<=1e-6 for x in dr),dd_better=sum(x< -1e-6 for x in dd),dd_worse=sum(x>1e-6 for x in dd),dd_equal=sum(abs(x)<=1e-6 for x in dd),joint_better=sum(r>1e-6 and d< -1e-6 for r,d in zip(dr,dd)),median_return_change_pp=statistics.median(dr),median_dd_change_pp=statistics.median(dd))
stats={'all_two_day_vs_original':tally(eligible),'mature_full_two_day_vs_original':tally(mature),'all_original_vs_hold':tally(eligible,'original','hold'),'all_two_day_vs_hold':tally(eligible,'two_day','hold'),'by_phase':{},'by_asset':{}}
for p in periods:stats['by_phase'][p['id']]=tally([c for c in eligible if c['phase']==p['id']])
for asset in assets:stats['by_asset'][asset]=tally([c for c in mature if c['asset']==asset])
(root/'aggregate.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False)+'\n')
lines=['# P1–P8 × 12 标的：原版、BTC 两天退出与持有','',
'用户指定的 96 个组合中，83 个可运行：77 个覆盖完整阶段、6 个为明确缩短的有效区间；13 个因本交易所尚无历史或暖机不足不可用。完成 166 次新原生策略回测及 83 条持有基准，共 249 条权益曲线。正式策略未修改。','',
'## 比较口径','',
'- 每个标的、每个阶段独立从 1000 USDT 现金开始，单币、单仓位，现货只做多。不同阶段的现金、仓位、风控峰值与冷却状态不继承；这是独立阶段测试，不能将 P1–P8 收益相加或复利成连续账户。P6 与 P7 在 2024 年 3 月重叠，不能当作独立统计样本。',
'- 原版为冻结的 cycle_risk_strategy.py。候选仅将 BTC 弱势退出从 1 根完成日线改为连续 2 根，个币两天退出、入场、14 天冷却及账户风控全部保留。',
'- 使用 Binance USDT 现货日线，按 UTC 日期包含起止日。每边手续费 0.1%，滑点为 0；相同区间相同价格。策略信号使用完成日线、下一交易日执行。',
'- 主表收益为期末现金与持仓按收盘价计价的权益收益；回撤为整个账户日线收盘权益（含现金）的历史峰值回撤，初始 1000 也计入峰值。主表三组均不额外强制卖出期末仓位，避免仅策略多算结束交易费用；summary.csv 另列 liquidated_return_pct，可比较统一假定清仓的收益。',
'- 持有在有效测试起点的开盘价一次买入，扣买入费，不择时、不风控；末日持仓仍按收盘价计价。回撤为日线收盘口径，不是日内最高价至最低价的跌幅。',
'- 6 个部分区间三组均从同一有效起点开始。另有 APT P5 区间完整但 MA150 尚未形成；这些共 7 个暖机案例单列，不纳入“完整且 MA150 已就绪”的 76 个核心比较。',
'- 不设置“回撤最多扩大 5 个百分点”等硬筛选，综合观察收益、回撤、熊市损失及跨标的一致性。未针对这些阶段搜索参数，也没有将既有研究后的复核称为样本外测试。','',
'## 总体结果','']
for title,key in [('全部83个可运行案例','all_two_day_vs_original'),('76个完整且MA150就绪案例','mature_full_two_day_vs_original')]:
 s=stats[key];lines.append(f"- {title}，两天退出相对原版：收益改善 {s['return_better']}、下降 {s['return_worse']}、相同 {s['return_equal']}；回撤改善 {s['dd_better']}、扩大 {s['dd_worse']}、相同 {s['dd_equal']}；收益提高且回撤降低 {s['joint_better']}。收益变化中位数 {s['median_return_change_pp']:+.2f} 个百分点，回撤变化中位数 {s['median_dd_change_pp']:+.2f} 个百分点。")
for title,key in [('原版','all_original_vs_hold'),('两天退出','all_two_day_vs_hold')]:
 s=stats[key];lines.append(f"- {title}相对持有：收益更高 {s['return_better']}/{s['n']}，回撤更低 {s['dd_better']}/{s['n']}；二者同时改善 {s['joint_better']}/{s['n']}。暖机阶段的参与时间不同，需结合下方完整表解释。")
lines+=['','|阶段|案例数|收益改善/下降/相同|回撤改善/扩大/相同|两项同时改善|收益变化中位数 pp|回撤变化中位数 pp|','|---|---:|---|---|---:|---:|---:|']
for p in periods:
 s=stats['by_phase'][p['id']];lines.append(f"|{p['id']} {p['type']}|{s['n']}|{s['return_better']}/{s['return_worse']}/{s['return_equal']}|{s['dd_better']}/{s['dd_worse']}/{s['dd_equal']}|{s['joint_better']}|{s['median_return_change_pp']:+.2f}|{s['median_dd_change_pp']:+.2f}|")
lines+=['','各阶段按标的等权统计的中位数与次数用于描述一致性，不是实际多币组合收益；本轮是单币测试，账户风控和预算行为也不同于此前多币组合。','',
'## 每个标的的稳定性','', '|标的|完整且MA150就绪案例|收益改善/下降/相同|回撤改善/扩大/相同|同时改善|', '|---|---:|---|---|---:|']
for a in assets:
 s=stats['by_asset'][a];lines.append(f"|{a}|{s['n']}|{s['return_better']}/{s['return_worse']}/{s['return_equal']}|{s['dd_better']}/{s['dd_worse']}/{s['dd_equal']}|{s['joint_better']}|")
lines+=['','## 96 个组合完整结果','', '**数值全部为百分比；每组均列收益 / 最大回撤。** 两天版收益变化与回撤变化单位为百分点。正回撤变化表示回撤扩大。`*` 为部分区间，`†` 为有效起点 MA150 未形成。','']
for p in periods:
 lines += [f"### {p['id']} {p['start']}—{p['end']}：{p['type']}",'', '|标的|原版收益 / 回撤|两天退出收益 / 回撤|持有收益 / 回撤|收益变化 pp|回撤变化 pp|实际覆盖与说明|','|---|---:|---:|---:|---:|---:|---|']
 for c in [c for c in cases if c['phase']==p['id']]:
  a=c['asset'];status=c['status']
  if status=='unavailable':lines.append(f"|{a}|不可用|不可用|不可用|—|—|{c['reason']}|");continue
  a+=('*' if status=='partial' else '')+('†' if c['ma150_ready_at_start']=='False' else '')
  vals=[f"{c[n+'_return_pct']:+.2f}% / {c[n+'_wallet_drawdown_pct']:.2f}%" for n in ['original','two_day','hold']]
  note=f"{c['effective_start']}—{c['effective_end']}" if status=='partial' else '完整'
  if c['ma150_ready_at_start']=='False':note+='；先等待MA150'
  lines.append(f"|{a}|{'|'.join(vals)}|{c['return_change_pp']:+.2f}|{c['drawdown_change_pp']:+.2f}|{note}|")
lines+=['','## 差异最大的案例','', '收益差按“候选期末权益 / 原版期末权益 − 1”排序，避免极高牛市收益下百分点差异误导。以下只看完整且 MA150 已就绪案例。','', '|方向|标的阶段|两天/原版期末权益变化|收益变化 pp|回撤变化 pp|','|---|---|---:|---:|---:|']
for direction,cs in [('改善',sorted(mature,key=lambda c:c['relative_ending_wealth_change_pct'],reverse=True)[:6]),('下降',sorted(mature,key=lambda c:c['relative_ending_wealth_change_pct'])[:6])]:
 for c in cs:lines.append(f"|{direction}|{c['asset']} {c['phase']}|{c['relative_ending_wealth_change_pct']:+.2f}%|{c['return_change_pp']:+.2f}|{c['drawdown_change_pp']:+.2f}|")
lines+=['','## 交易与现金参与','', '十天内亏损平仓数只是短期亏损交易的描述，不等同于所有假突破；未结束的期末交易不计入此数。换手次数包含风险减仓/恢复的实际成交，主表权益已计入手续费。','', '|阶段|原版实际成交数|两天版实际成交数|原版十天内亏损笔数|两天版十天内亏损笔数|原版平均现金占比中位数|两天版平均现金占比中位数|','|---|---:|---:|---:|---:|---:|---:|']
for p in periods:
 cs=[c for c in eligible if c['phase']==p['id']]
 vals=[sum(c[n+'_'+key] for c in cs) for key in ['normal_fills','quick_loss_positions'] for n in ['original','two_day']]
 med=[statistics.median(c[n+'_mean_idle_cash_pct'] for c in cs) for n in ['original','two_day']]
 lines.append(f"|{p['id']}|{vals[0]:.0f}|{vals[1]:.0f}|{vals[2]:.0f}|{vals[3]:.0f}|{med[0]:.2f}%|{med[1]:.2f}%|")
lines+=['','## 验证与文件','']
verification=json.loads((root/'verification.json').read_text());audit=json.loads((root/'audit_verification.json').read_text())
lines += [f"- {verification['count']} 项规则及截断历史检查通过：两版除 BTC 退出条件外一致，指标只依赖当时及以前数据。",
 f"- 重建 {audit['curve_checks']} 条持仓权益曲线，核对 {audit['summary_metric_checks']} 项汇总指标、{audit['actual_btc_exit_checks']} 次实际 BTC 退出、{audit['actual_weak_btc_entry_cooldown_checks']} 次弱 BTC 入场冷却、{audit['daily_risk_equity_checks']} 个日线风控权益记录。最大权益重建误差 {audit['max_equity_error']:.10g} USDT，最大原生现金误差 {audit['max_cash_error']:.10g} USDT。",
 '- 冻结行情、研究策略及正式策略哈希全部一致；数据连续性、实际起止日期及每次独立开户已检查。',
 '- [96组合CSV](comparison_matrix.csv)、[原始249行指标](summary.csv)、[覆盖清单](coverage.csv)、[汇总统计](aggregate.json)、[规则检查](verification.json)、[成交与权益核验](audit_verification.json)。',
 '- 单笔成交与每日曲线保存在 results/；源数据 SHA256 保存在 data_audit.json；新增 DOT、ARB、APT 的 Binance 请求记录在 download_sources.json。','']
(root/'REPORT.md').write_text('\n'.join(lines))
print(json.dumps(stats,ensure_ascii=False,indent=2))
