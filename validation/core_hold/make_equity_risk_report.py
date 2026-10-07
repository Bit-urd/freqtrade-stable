"""Compare corrected drawdown controllers, previous profiles and holding."""
import collections
import csv
import datetime
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent;folder=root/'archive/portfolio_cycle_risk_v2'
checks=json.loads((folder/'rule_checks.json').read_text())
assert checks['passed'] and checks['tests_run']==13
read=lambda p:list(csv.DictReader(p.open()))
reference=[r for r in read(root/'start_checks/summary.csv') if r['cohort']=='reference']
guard=read(root/'portfolio_coin_guard/public_replay/summary.csv')
switch=read(root/'portfolio_regime_switch/summary.csv')
equity=read(root/'archive/portfolio_equity_risk_v2/summary.csv');cycle=read(folder/'summary.csv')
assert len(equity)==10 and len(cycle)==10
names={'Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio（正式）',
       'BtcTrendCoinGuardStrategy':'全天个币保护',
       'BtcPortfolioRegimeSwitchStrategy':'旧切换版',
       'BtcCoinGuardEquityRiskStrategy':'权益风控',
       'BtcCoinGuardCycleRiskStrategy':'新周期恢复风控',
       'BuyAndHold':'持有'}
source={n:reference for n in ['Ma200BtcRegimeFullCyclePortfolioStrategy','BuyAndHold']}
source.update(BtcTrendCoinGuardStrategy=guard,BtcPortfolioRegimeSwitchStrategy=switch,
              BtcCoinGuardEquityRiskStrategy=equity,BtcCoinGuardCycleRiskStrategy=cycle)
rows=[];assessment=[]
lines=['# 账户权益回撤控制与新周期恢复：策略、持有对比','',
       '用户要求继续改善收益/回撤平衡，并明确要求与持有比较。正式 Portfolio 与现有交易服务未改变。', '',
       '## 两项固定试验', '',
       '权益风控：保留全天个币保护的全部入场/退出、14 天冷却、独立币预算；账户历史峰值回撤达 25% 时降至 75% 风险仓位，达 35% 时降至 50%；回撤收窄至 30% 时从半仓恢复至 75%，至 20% 时恢复满仓。通过不同降仓/恢复阈值减少边界反复交易，不做参数网格搜索。', '',
       '新周期恢复风控：只追加 BTC 连续两天收盘站上 MA200 的新确认事件。若此前处于减仓状态，在事件出现时允许恢复满风险仓位并将内部风控峰值重设为当时权益；重设至少相隔 14 天。回测报告仍按初始本金和原账户历史最高权益计算回撤，不用重设峰值美化结果。重设内部峰值也意味着没有账户全历史硬回撤上限。', '',
       '## 数据时点修正与独立核对', '',
       '初次两版中间结果不计入最终结论：回测 bot_loop_start 在各币分析缓存刷新之前执行，用缓存读取价格会滞后一根日线。修正版按执行日期从原始历史过滤前一天及更早的已收盘数据；BTC MA200 确认同样只用已收盘历史。模拟钱包在持仓时尚未结算的开仓费从内部权益扣除。', '',
       '每个执行日的风控权益都与独立成交重建的前一天收盘权益核对，要求误差 <0.05 USDT。不是只检查期末资金。修正后的两个方案各五个阶段完整重跑；六项权益控制检查与七项周期恢复检查通过，包含未收盘价格不能触发 BTC 确认。', '',
       '## 五阶段：收益 / 最大回撤', '',
       'BTC/SOL/ETH 等本金三币组合，初始 1000 USDT、三个槽位、现货、单边手续费 0.1%。持有同一起点等额买入三币、不调仓；每日收盘总权益、同一终点估值。未计额外滑点和额外盘中回撤。', '',
       '| 区间 | Portfolio | 全天个币保护 | 旧切换 | 权益风控 | 新周期恢复 | 持有 |','|---|---:|---:|---:|---:|---:|---:|']
for window in json.loads((folder/'windows.json').read_text()):
    label=window['label'];cells=[]
    hold=next(r for r in reference if r['window']==label and r['strategy']=='BuyAndHold')
    for name in names:
        r=next(r for r in source[name] if r['window']==label and r['strategy']==name)
        row={k:r.get(k) for k in ['window','start','end','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct','trades','ledger_error']}
        positive=float(hold['return_pct'])>0
        ratio=float(r['return_pct'])/float(hold['return_pct']) if positive else None
        better=float(r['wallet_drawdown_pct'])<float(hold['wallet_drawdown_pct'])
        row.update(hold_return_pct=hold['return_pct'],hold_drawdown_pct=hold['wallet_drawdown_pct'],return_fraction_of_hold=ratio,return_gain_vs_hold_pp=float(r['return_pct'])-float(hold['return_pct']),drawdown_improvement_vs_hold_pp=float(hold['wallet_drawdown_pct'])-float(r['wallet_drawdown_pct']),strict_joint_target=(ratio>=2/3 and better) if positive else None)
        rows.append(row);cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
        if name in ['BtcCoinGuardEquityRiskStrategy','BtcCoinGuardCycleRiskStrategy']:
            assessment.append({'window':label,'strategy':name,'return_fraction_of_hold':ratio,'drawdown_better_than_hold':better,'strict_joint_target':row['strict_joint_target']})
    lines.append('| '+window['timerange']+' | '+' | '.join(cells)+' |')
    for measured in [equity,cycle]:
        h=next(r for r in measured if r['window']==label and r['strategy']=='BuyAndHold')
        assert all(abs(float(h[k])-float(hold[k]))<1e-8 for k in ['return_pct','wallet_drawdown_pct'])
with (folder/'comparison.csv').open('w') as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines+=['','## 收益相对持有与仓位轨迹','',
        '| 区间 | 权益风控收益 / 持有收益 | 新周期恢复收益 / 持有收益 |','|---|---:|---:|']
for w in ['ref_bull_2023_2024','ref_requested_long']:
    a=next(x for x in assessment if x['window']==w and x['strategy']=='BtcCoinGuardEquityRiskStrategy')
    b=next(x for x in assessment if x['window']==w and x['strategy']=='BtcCoinGuardCycleRiskStrategy')
    lines.append(f"| {w} | {a['return_fraction_of_hold']*100:.2f}% | {b['return_fraction_of_hold']*100:.2f}% |")
trace_summary=[];max_trace_error=0.0
for dirname,strategy in [('archive/portfolio_equity_risk_v2','BtcCoinGuardEquityRiskStrategy'),('archive/portfolio_cycle_risk_v2','BtcCoinGuardCycleRiskStrategy')]:
    f=root/dirname
    manifest=json.loads((f/'source_manifest.json').read_text())
    assert all(hashlib.sha256((f/'strategies'/n).read_bytes()).hexdigest()==sha for n,sha in manifest.items())
    for window in json.loads((f/'windows.json').read_text()):
        result=f/'results'/window['label'];trace=json.loads((result/'risk_trace.json').read_text())
        curve=read(result/('equity_'+strategy+'.csv'));datekey=list(curve[0])[0]
        by={r[datekey][:10]:float(r['equity']) for r in curve}
        for row in trace:
            prior=(datetime.date.fromisoformat(row['execution_date'][:10])-datetime.timedelta(days=1)).isoformat()
            if prior in by:
                error=abs(row['prior_closed_equity']-by[prior]);assert error<.05
                max_trace_error=max(max_trace_error,error)
        counters=collections.Counter(x['risk_fraction'] for x in trace)
        trace_summary.append({'window':window['label'],'strategy':strategy,'days':len(trace),'full_days':counters[1.0],'three_quarters_days':counters[.75],'half_days':counters[.5],'risk_epoch_resets':sum(bool(r.get('risk_epoch_reset')) for r in trace)})
(folder/'risk_stage_summary.json').write_text(json.dumps(trace_summary,indent=2)+'\n')
lines+=['', '完整权益开关轨迹见各 results/*/risk_trace.json；各阶段满仓/75%/半仓天数和峰值重设次数见 risk_stage_summary.json。', '',
        '## 保留状态与目标边界', '',
        '降低风险敞口会损失部分反弹收益；全历史峰值规则还会延长减仓状态。新周期恢复能重新增加敞口，也可能在假突破后增加损失。不能仅因为一次上涨段接近持有 2/3，就认定全周期目标达成；严格目标逐窗口列在 comparison.csv。', '',
        '两方案仅为研究记录，没有上线或切换正式 Portfolio。本轮没有十币或新增起点验证；历史样本已经被反复观察，因此不声明样本外有效。账户高水位、阶段与待成交状态未实现实盘重启持久化，此研究代码不提供部署配置。', '',
        '复现：run_portfolio_equity_risk_v2.py、run_portfolio_cycle_risk_v2.py；汇总：make_equity_risk_report.py。修正前中间源码与结果归档，最终结果仅采用 v2 完整回放。']
lines += ['', '## 本轮最终结论', '', '新周期恢复版上涨收益 527.79%，为持有的 64.87%，接近约 2/3；回撤 30.31% 低于持有 36.14%。牛转熊 +69.40%/44.55%，纯熊市 -29.14%/31.54%，均明显好于持有。近期 -18.65%/43.68% 虽好于持有 -33.02%/63.57%，但差于正式 Portfolio -6.52%/36.07%。', '', '长区间 +497.43%/40.83%，只有持有收益的 56.83%；相比旧切换版 +557.45%/41.15%，少赚约 60.02 个百分点，只降低约 0.32 个百分点回撤，交换不划算。相比全天个币保护 +488.41%/44.49%，长区间略有改善，但上涨收益低于全天个币保护 +559.13%/30.00%。', '', '两版未取得全面更优的收益与风险组合，停止本轮试验并归档；原正式 Portfolio、旧切换版和全天个币保护的既有保留状态不变。没有通过不断搜索阈值来追求这几个已知窗口的最佳数字。']
(folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
verification={'final_engine_runs':10,'windows_per_candidate':5,'rule_checks_passed':13,'sources_match':True,'hold_references_match':True,'max_abs_fill_ledger_error':max(abs(float(r['ledger_error'])) for r in equity+cycle if r['ledger_error']),'max_abs_prior_closed_equity_error':max_trace_error,'intermediate_results_excluded':True,'reported_drawdown_uses_original_account_peak':True,'official_portfolio_changed':False,'live_service_changed':False,'target_assessment':assessment}
(folder/'verification.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(verification,indent=2))
