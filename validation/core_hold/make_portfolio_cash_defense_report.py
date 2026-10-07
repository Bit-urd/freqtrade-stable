"""Compare fixed cash-defense experiments with prior mode switching."""
import csv
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parent;folder=root/'portfolio_three_regime'
read=lambda p:list(csv.DictReader(p.open()))
reference=[r for r in read(root/'start_checks/summary.csv') if r['cohort']=='reference']
old=read(root/'portfolio_regime_switch/summary.csv')
guard=read(root/'portfolio_coin_guard/public_replay/summary.csv')
new=read(folder/'summary.csv');assert len(new)==15
staged=read(root/'portfolio_half_recovery_v2/summary.csv');assert len(staged)==10
names={'Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio（正式）',
       'BtcPortfolioRegimeSwitchStrategy':'旧切换版',
       'BtcTrendCoinGuardStrategy':'全天个币保护',
       'BtcPortfolioNoBearSwitchStrategy':'关闭抄底切换版',
       'BtcPortfolioThreeRegimeStrategy':'三状态版',
       'BtcPortfolioHalfRecoveryStrategy':'半仓恢复版',
       'BuyAndHold':'持有'}
source={**{n:reference for n in ['Ma200BtcRegimeFullCyclePortfolioStrategy','BuyAndHold']},
    'BtcPortfolioRegimeSwitchStrategy':old,'BtcTrendCoinGuardStrategy':guard,
    'BtcPortfolioNoBearSwitchStrategy':new,'BtcPortfolioThreeRegimeStrategy':new,
    'BtcPortfolioHalfRecoveryStrategy':staged}
rows=[];windowstats=[]
lines=['# 下跌现金防守与阶段切换优化（2026-10-07）','',
       '用户要求改善切换版在牛转熊、纯熊市、近期的回撤，同时保留上涨参与。正式 Portfolio 和运行服务未改变。', '',
       '## 固定规则与对照', '',
       '1. 关闭抄底切换版：仅对此前两模式切换版设置 BEAR_ENABLED=False。BTC 连续两天站上 MA200 用个币保护，其余用原 Portfolio 入场、退出、周线规则；熊市没有新分档买入。',
       '2. 三状态版：BTC/个币沿用 MA150/EMA10 支持。BTC 长短支持同时失效时清仓；连续两天站上 MA200 用个币保护；其余 BTC 恢复/震荡状态要求个币 EMA20/50 原版排列入场、两天排列失效退出、周线调仓。禁止熊市分档积累。',
       '3. 半仓恢复版：BTC 与个币都允许风险时入场；BTC 尚未连续两天站上 MA200 用半槽位，确认后满槽位，失去确认降回半槽位；BTC 弱一天或个币弱两天则清仓。停止熊市分档积累和周线调仓。一个账户、Portfolio 账户权益/槽位预算，手续费计入买入预算，卖出按市场价值转换为成本量，新增仓位状态仅在成交后更新。', '',
       '本轮没有参数网格搜索、没有分币调参。半仓恢复是根据前两项结果追加的固定机制，属于同一历史样本上的适应性研究，不是独立样本外验证。', '',
       '半仓中间版修正跨阶段交易方向约束后，用新目录 portfolio_half_recovery_v2 完整重跑；最终只计修正版结果。旧中间源码、四个已完成阶段和停止说明保留归档。', '',
       '## 五阶段对比', '',
       'BTC/SOL/ETH 三币、初始 1000 USDT、三个槽位、现货、单边费 0.1%，每日收盘总权益。旧版复用冻结历史结果，新版独立重跑，逐阶段核对持有一致。', '',
       '| 区间 | Portfolio 收益 / 回撤 | 旧切换 | 全天个币保护 | 关闭抄底 | 三状态 | 半仓恢复 | 持有 |',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
for window in json.loads((folder/'windows.json').read_text()):
    cells=[]
    hold=next(r for r in reference if r['window']==window['label'] and r['strategy']=='BuyAndHold')
    baseline=next(r for r in old if r['window']==window['label'] and r['strategy']=='BtcPortfolioRegimeSwitchStrategy')
    for name in names:
        r=next(r for r in source[name] if r['window']==window['label'] and r['strategy']==name)
        row={k:r.get(k) for k in ['window','start','end','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct','trades','ledger_error']}
        row.update(hold_return_pct=hold['return_pct'],hold_drawdown_pct=hold['wallet_drawdown_pct'],return_fraction_of_hold=float(r['return_pct'])/float(hold['return_pct']) if float(hold['return_pct'])>0 else None,return_gain_vs_old_switch_pp=float(r['return_pct'])-float(baseline['return_pct']),drawdown_change_vs_old_switch_pp=float(r['wallet_drawdown_pct'])-float(baseline['wallet_drawdown_pct']))
        rows.append(row);cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
    lines.append('| '+window['timerange']+' | '+' | '.join(cells)+' |')
    for measured in [new,staged]:
        h=next(r for r in measured if r['window']==window['label'] and r['strategy']=='BuyAndHold')
        assert all(abs(float(h[k])-float(hold[k]))<1e-8 for k in ['return_pct','wallet_drawdown_pct'])
with (folder/'comparison.csv').open('w') as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines+=['','## 结论', '',
       '关闭抄底版最直接地证明了熊市积累风险：牛转熊从旧版 -5.10%/64.67% 变为 +57.14%/27.25%；2022 熊市全程空仓、0 笔交易，收益与回撤均为零；近期从 -3.54%/41.19% 变为 +5.39%/26.07%。这不代表所有未来熊市都零回撤，而是该历史窗口没有触发入场。', '',
       '代价是上涨期收益降至 366.02%，长区间收益降至 398.55%、回撤 41.86%，略差于正式 Portfolio 的 403.44%/38.02%。因此作为现金防守对照保留，不能称为全周期升级。', '',
       '三状态版在恢复/震荡阶段的额外交易并未稳定改善结果：相对关闭抄底版，纯熊市亏损 10.37%、回撤 18.18%，近期 -5.14%/37.22%；半仓恢复版上涨收益更高且回撤更低。记录为失败研究，不进入活动策略目录。', '',
       '半仓恢复版是进攻与防守折中：上涨 461.85%/29.70%，牛转熊 +36.37%/43.97%，熊市 -22.86%/22.86%，近期 -2.65%/35.60%，上述四阶段的回撤均低于旧切换版。长区间 479.09%/42.78%，收益比旧切换版少 78.36 个百分点、回撤高约 1.63 个百分点；仍无法全面优于旧版。', '',
       '用户收益约为持有 2/3 的目标尚未达成：半仓恢复上涨收益约为持有的 56.77%，长区间约 54.73%；关闭抄底版分别约 44.99%、45.53%。两版的五阶段回撤均低于持有，但这不是收益目标已实现。', '',
       '保留关闭抄底版为防守候选、半仓恢复修正版为折中研究候选；原 Portfolio 保持正式身份。候选代码仅在研究目录，无自动实盘/服务切换。本轮没有扩展十币或其他新起点；不能据此宣称普适性。', '',
       '## 验证与边界', '',
       '完成三方案各五阶段，共 15 次最终引擎回测；三状态/禁抄底七项检查、半仓六项检查均通过。源文件哈希固定，全部成交现金流核对引擎资金误差 <0.05 USDT。旧中间版未纳入最终结果。', '',
       '所有信号使用已收盘数据，下一根日线执行；日线收盘回撤不覆盖额外盘中波动，没有额外滑点。历史窗口反复被观察，当前结果是研究比较。', '',
       '复现：run_portfolio_three_regime.py、run_portfolio_half_recovery_v2.py；汇总：make_portfolio_cash_defense_report.py。comparison.csv 保留七策略全部指标。']
(folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
for f in [folder,root/'portfolio_half_recovery_v2']:
    m=json.loads((f/'source_manifest.json').read_text())
    assert all(hashlib.sha256((f/'strategies'/name).read_bytes()).hexdigest()==sha for name,sha in m.items())
verification={'final_engine_runs':15,'windows_per_candidate':5,'rule_checks_passed':13,'frozen_sources_match':True,'hold_references_match':True,'max_abs_ledger_error':max(abs(float(r['ledger_error'])) for r in new+staged if r['ledger_error']),'intermediate_results_excluded':True,'official_portfolio_changed':False,'live_service_changed':False,'hold_two_thirds_return_target_met':False,'status':'research_candidates_only'}
(folder/'verification.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(verification,indent=2))
