"""Summarize paired return/drawdown performance across independent cash starts."""
import csv
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parent;FOLDER=ROOT/'start_checks'
NAMES=['BtcTrendPhasedStrategy','BtcTrendFastExitStrategy','Ma200BtcRegimeFullCyclePortfolioStrategy','BuyAndHold']
LABELS={'BtcTrendPhasedStrategy':'原分阶段版','BtcTrendFastExitStrategy':'快速退出版','Ma200BtcRegimeFullCyclePortfolioStrategy':'原 Portfolio','BuyAndHold':'等权持有'}
COHORTS={'rolling_12_month':'月度起点、固定 12 个月','common_end':'季度起点、统一终点','reference':'原有五区间复核'}
rows=list(csv.DictReader((FOLDER/'summary.csv').open()))
lookup={(r['window'],r['strategy']):r for r in rows}
windows=json.loads((FOLDER/'windows.json').read_text())
complete=[w for w in windows if all((w['label'],n) in lookup for n in NAMES)]
aggregate=[];paired=[]
for w in complete:
    hold=lookup[w['label'],'BuyAndHold'];hr=float(hold['return_pct']);hd=float(hold['wallet_drawdown_pct'])
    for name in NAMES[:-1]:
        x=lookup[w['label'],name];ret=float(x['return_pct']);dd=float(x['wallet_drawdown_pct'])
        v1=lookup[w['label'],'BtcTrendPhasedStrategy']
        paired.append({'window':w['label'],'cohort':w['cohort'],'start':x['start'],'end':x['end'],'strategy':name,'return_pct':ret,'hold_return_pct':hr,'return_fraction_of_hold':ret/hr if hr>0 else None,'drawdown_pct':dd,'hold_drawdown_pct':hd,'drawdown_improvement_pp':hd-dd,'drawdown_better_than_hold':dd<hd,'return_better_than_hold':ret>hr,'positive_hold_window':hr>0,'two_thirds_return_met':ret>=hr*2/3 if hr>0 else None,'joint_two_thirds_and_lower_drawdown':ret>=hr*2/3 and dd<hd if hr>0 else None,'negative_hold_joint_improvement':ret>hr and dd<hd if hr<0 else None,'return_change_vs_v1_pp':ret-float(v1['return_pct']),'drawdown_change_vs_v1_pp':dd-float(v1['wallet_drawdown_pct'])})
for cohort in COHORTS:
    cohort_windows=[w for w in complete if w['cohort']==cohort]
    if not cohort_windows:continue
    for name in NAMES:
        xs=[lookup[w['label'],name] for w in cohort_windows]
        rs=[float(x['return_pct']) for x in xs];ds=[float(x['wallet_drawdown_pct']) for x in xs]
        qs=[x for x in paired if x['cohort']==cohort and x['strategy']==name]
        positive=[x for x in qs if x['positive_hold_window']];negative=[x for x in qs if x['hold_return_pct']<0]
        d={'cohort':cohort,'strategy':name,'windows':len(xs),'median_return_pct':statistics.median(rs),'mean_return_pct':statistics.mean(rs),'worst_return_pct':min(rs),'best_return_pct':max(rs),'median_drawdown_pct':statistics.median(ds),'worst_drawdown_pct':max(ds),'profitable_windows':sum(r>0 for r in rs),'drawdown_better_than_hold_windows':sum(x['drawdown_better_than_hold'] for x in qs) if qs else None,'return_better_than_hold_windows':sum(x['return_better_than_hold'] for x in qs) if qs else None,'positive_hold_windows':len(positive) if qs else None,'two_thirds_return_windows':sum(x['two_thirds_return_met'] for x in positive) if qs else None,'joint_sixty_percent_and_lower_drawdown_windows':sum(x['return_pct']>=.6*x['hold_return_pct'] and x['drawdown_better_than_hold'] for x in positive) if qs else None,'median_paired_drawdown_improvement_pp':statistics.median(x['drawdown_improvement_pp'] for x in qs) if qs else None,'drawdown_at_least_five_pp_better_windows':sum(x['drawdown_improvement_pp']>=5 for x in qs) if qs else None,'joint_two_thirds_and_lower_drawdown_windows':sum(x['joint_two_thirds_and_lower_drawdown'] for x in positive) if qs else None,'negative_hold_windows':len(negative) if qs else None,'negative_hold_joint_improvement_windows':sum(x['negative_hold_joint_improvement'] for x in negative) if qs else None,'drawdown_better_than_v1_windows':sum(x['drawdown_change_vs_v1_pp']<0 for x in qs) if qs else None}
        aggregate.append(d)
for filename,records in [('aggregate.csv',aggregate),('paired_comparison.csv',paired)]:
    if records:
        with (FOLDER/filename).open('w') as output:
            writer=csv.DictWriter(output,fieldnames=list(records[0]),lineterminator='\n');writer.writeheader();writer.writerows(records)
(FOLDER/'aggregate.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2)+'\n')
lines=['# 三策略起点检查：收益、回撤与持有','',f'已完成 {len(complete)}/{len(windows)} 个独立出资的回测窗口，每个窗口运行三策略及等权持有。','', '策略冻结，起点检查期间不调参。BTC/USDT、SOL/USDT、ETH/USDT；初始 1000 USDT，3 槽位，单边手续费 0.1%，未额外计滑点。','', '收益采用累计利润率，最大回撤按每日收盘总权益。持有三币各 1/3 买入、不再平衡。双方统一起止日期与估值；策略信号用已完成日线，在下一根执行。起点前日线/周线用于指标预热；起点前交易和持仓不继承。','', '“收益达到持有 2/3”只在持有正收益窗口衡量；持有亏损窗口单独比较亏损和回撤。指标逐窗口配对计算，不能用两个收益中位数的比例代替达标率。','']
for cohort,title in COHORTS.items():
    group=[x for x in aggregate if x['cohort']==cohort]
    if not group:continue
    total=sum(w['cohort']==cohort for w in windows)
    lines+=['## '+title,'',f"完成 {group[0]['windows']}/{total} 个窗口。",'', '| 策略 | 收益中位数 | 最差收益 | 回撤中位数 | 最大回撤 | 回撤低于持有 | 持有上涨时，收益≥2/3且回撤更低 | 持有下跌时，收益及回撤均更好 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for x in group:
        dd='—' if x['strategy']=='BuyAndHold' else f"{x['drawdown_better_than_hold_windows']}/{x['windows']}"
        positive='—' if x['strategy']=='BuyAndHold' else f"{x['joint_two_thirds_and_lower_drawdown_windows']}/{x['positive_hold_windows']}"
        negative='—' if x['strategy']=='BuyAndHold' else f"{x['negative_hold_joint_improvement_windows']}/{x['negative_hold_windows']}"
        lines.append(f"| {LABELS[x['strategy']]} | {x['median_return_pct']:+.2f}% | {x['worst_return_pct']:+.2f}% | {x['median_drawdown_pct']:.2f}% | {x['worst_drawdown_pct']:.2f}% | {dd} | {positive} | {negative} |")
    lines+=['', '宽松参考（收益≥持有的 60% 且回撤更低，仅用于观察接近 2/3 的情况，不替代上面的严格统计）：'+ '；'.join(f"{LABELS[x['strategy']]} {x['joint_sixty_percent_and_lower_drawdown_windows']}/{x['positive_hold_windows']}" for x in group if x['strategy']!='BuyAndHold')+'。','', '回撤改善至少 5 个百分点的窗口：'+ '；'.join(f"{LABELS[x['strategy']]} {x['drawdown_at_least_five_pp_better_windows']}/{x['windows']}" for x in group if x['strategy']!='BuyAndHold')+'。']
    lines+=['','### 各起点：收益 / 最大回撤','', '| 起点 | 终点 | 原分阶段版 | 快速退出版 | 原 Portfolio | 等权持有 |','|---|---|---:|---:|---:|---:|']
    for w in complete:
        if w['cohort']!=cohort:continue
        xs=[lookup[w['label'],n] for n in NAMES]
        lines.append('| '+xs[0]['start']+' | '+xs[0]['end']+' | '+' | '.join(f"{float(x['return_pct']):+.2f}% / {float(x['wallet_drawdown_pct']):.2f}%" for x in xs)+' |')
    lines+=['']
lines+=['## 口径与复现','', '固定 12 个月组：2020-11 至 2025-10，每月 1 日起步，结束于次年该月前一日，共 60 个起点。SOL 数据始于 2020-08-11，最早起点已满足自己的 60 根日线预热。','', '统一终点组：2022-11 至 2025-08，每三个月一个起点，共 12 个，终点均为 2026-10-05。该组持有时长不同，适合比较同一起点下策略与持有，不应把不同起点累计收益当成相同持有期。','', '五个参考区间重跑结果与此前报告逐一核对；所有成交现金流与引擎期末资金误差 <0.05 USDT。末日引擎 force_exit 不计入日线盯市曲线；持仓按终点收盘估值，清算收益另列。','', '冻结源文件位于 strategies/，校验值见 source_manifest.json。复用交易所和回测引擎，但每个窗口每个策略重建策略实例并重置交易、钱包、DataProvider 缓存及 custom data，防止本金缓存或冷却状态跨窗口传播。','', '运行 /research/run_start_checks.py 可断点续跑；/research/make_start_report.py 更新本报告。summary.csv 为所有窗口原始指标，paired_comparison.csv 为逐起点配对结果，aggregate.csv 为汇总。results/ 保留原始订单压缩 JSON 和日线权益 CSV。','', '起点窗口存在重叠，结果不是相互独立的样本，也不是全新样本外验证；本次用于检验是否依赖特定起点。','']
if len(complete)==len(windows):
    interpretation=FOLDER/'INTERPRETATION.md'
    if interpretation.exists():
        lines[2:2]=['[结果解读](INTERPRETATION.md) · [年度起点曲线](rolling_12_month.png) · [统一终点曲线](common_end.png)','']
(FOLDER/'REPORT.md').write_text('\n'.join(lines))
print(f'Report: {len(complete)}/{len(windows)} windows')
for x in aggregate:
    print(x['cohort'],x['strategy'],f"median return {x['median_return_pct']:+.2f}%, DD {x['median_drawdown_pct']:.2f}%, DD below hold {x['drawdown_better_than_hold_windows']}/{x['windows']}, joint 2/3 {x['joint_two_thirds_and_lower_drawdown_windows']}/{x['positive_hold_windows']}")
