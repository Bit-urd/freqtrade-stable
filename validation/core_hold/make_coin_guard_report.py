"""Summarize frozen bull-participation experiments and cross-coin limitations."""
import csv
import hashlib
import json
import statistics
from pathlib import Path
root=Path(__file__).resolve().parent;folder=root/'portfolio_coin_guard'
read=lambda p:list(csv.DictReader(p.open()))
reference=[r for r in read(root/'start_checks/summary.csv') if r['cohort']=='reference']
measured=read(folder/'summary.csv');assert len(measured)==10
public=read(folder/'public_replay/summary.csv');assert len(public)==10
for r in public:
    old=next(x for x in measured if x['window']==r['window'] and x['strategy']==r['strategy'])
    for key in ['return_pct','wallet_drawdown_pct','ending_equity']:
        assert abs(float(r[key])-float(old[key]))<1e-7,(r['window'],key)
growth=read(root/'portfolio_growth_control/summary.csv')
assert len(growth)==6
historical=[r for r in read(root/'trend_phased/retained_comparison.csv') if r['strategy']=='Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy']
combined=list(reference)
for r in historical:
    rr=dict(r,window='ref_'+r['window'],source='retained_growth_measurement')
    fresh=next((x for x in growth if x['window']==rr['window'] and x['strategy']==r['strategy']),None)
    if fresh:
        for key in ['return_pct','wallet_drawdown_pct']:
            assert abs(float(fresh[key])-float(r[key]))<1e-7
        rr=dict(fresh,source='fresh_growth_replay')
    combined.append(rr)
combined += [dict(r,source='fresh_guard_public_replay') for r in public if r['strategy']!='BuyAndHold']
rows=[]
for r in combined:
    hold=next(x for x in reference if x['window']==r['window'] and x['strategy']=='BuyAndHold')
    baseline=next(x for x in reference if x['window']==r['window'] and x['strategy']=='Ma200BtcRegimeFullCyclePortfolioStrategy')
    row={k:r.get(k) for k in ['window','start','end','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct','trades','ledger_error']}
    row.update(source=r.get('source','previous_frozen_reference'),hold_return_pct=hold['return_pct'],hold_drawdown_pct=hold['wallet_drawdown_pct'],return_fraction_of_hold=float(r['return_pct'])/float(hold['return_pct']) if float(hold['return_pct'])>0 else None,return_gain_vs_portfolio_pp=float(r['return_pct'])-float(baseline['return_pct']),drawdown_change_vs_portfolio_pp=float(r['wallet_drawdown_pct'])-float(baseline['wallet_drawdown_pct']))
    rows.append(row)
with (folder/'regime_comparison.csv').open('w') as out:
    w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
names={'Ma200BtcRegimeFullCyclePortfolioStrategy':'Portfolio（正式）','Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy':'Growth（稳健对照）','BtcTrendCoinGuardStrategy':'个币保护（进攻候选）','BuyAndHold':'持有'}
lines=['# Portfolio 上涨参与度优化：诊断、固定规则试验与风险边界','',
       '用户在停止此前失败试验后，重新授权优化 2023–2024 上涨收益，同时要求回撤可控。Portfolio 仍是正式版，未替换服务。', '',
       '## 原因诊断', '',
       '原版在 2023-01-02 各币首次买入约 66.6 USDT，总投入约 200 USDT；熊市交接不补满，持仓占用币种槽位，BTC/ETH 首单到五月退出时仍没有加仓。2023–2024 平均现金比例 44.22%，Growth 为 34.62%，个币保护版为 19.36%。现金不足利用是已证实的拖累，但并非全部收益差距的归因。', '',
       '## 本轮规则', '',
       '1. 立即交接补仓：只打开原版内置 HANDOVER_TOP_UP=True，不等待周线确认。五阶段已完成，但上涨收益仅从 239.07% 提至 250.96%，回撤从 38.02% 增至 39.42%；不作为主推荐。该方案与已归档的周线确认补仓有明确区别。',
       '2. Growth：复核此前保留规则，交接补仓、关闭周线半仓调节、普通个币回调保留 50% 核心，BTC 连续两天跌破 MA200 清仓。上涨期和长区间重新回放与历史结果一致；其他三阶段复用历史已核对结果。',
       '3. 个币保护版：在快速退出版上加入独立个币判断。BTC MA150/上升 EMA10 允许风险，并且该币自己的 MA150/上升 EMA10 也允许风险，才入场；BTC 弱一天或个币同时失去两个支持两天则退出。满风险仓位、原 14 天冷却和独立币预算不变；不做熊市分档积累。沿用 150/10/2 现有规则，没有参数搜索或分币调参。', '',
       '公开代码增加缺失信号保护；五个阶段已重新回放，收益、回撤和期末权益与冻结试验一致。新增五项检查验证未来价格不影响过去信号、个币入场过滤、BTC/个币退出、缺失值安全。', '',
       '## BTC/SOL/ETH 三币组合', '',
       '初始 1000 USDT、三个槽位、单边费 0.1%、每日收盘权益；持有起点等额买入不调仓。', '',
       '| 区间 | Portfolio 收益 / 回撤 | Growth | 个币保护 | 持有 |','|---|---:|---:|---:|---:|']
for window in json.loads((folder/'windows.json').read_text()):
    cells=[]
    for name in names:
        r=next(r for r in rows if r['window']==window['label'] and r['strategy']==name)
        cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
    lines.append('| '+window['timerange']+' | '+' | '.join(cells)+' |')
lines+=['', '个币保护版上涨收益是持有的 68.72%，回撤 30.00% 低于持有 36.14% 和 Portfolio 38.02%；上涨期达到严格联合目标。长区间收益仅为持有的 55.80%，仍未达到约 2/3；其回撤 44.49% 低于持有 52.50%，但高于 Portfolio 38.02%。近期收益和回撤都差于 Portfolio（-18.65% / 43.68% 对 -6.52% / 36.07%）。因此不声称全面升级。', '',
       '若“回撤可控”指每个阶段都不高于原 Portfolio，个币保护版不合格；Growth 更接近这个要求，但上涨收益只有持有的 35.28%。若允许相对原版增加部分回撤、要求仍好于持有，个币保护版在三币五阶段均满足回撤低于持有，但上涨收益目标仅在 2023–2024 达成。', '',
       '## 十个单币迁移检查', '',
       '每币独立 1000 USDT、一个槽位，20221121–20251007。原三组结果复用冻结测量，并逐币核对持有一致。中位数不是组合收益。', '',
       '| 单币 | Portfolio 收益 / 回撤 | 快速退出版 | 个币保护 | 持有 |','|---|---:|---:|---:|---:|']
single=read(folder/'single_coin/summary.csv');assert len(single)==20
old=read(root/'single_coin_comparison/summary.csv')
for pair in json.loads((folder/'single_coin/plan.json').read_text())['pairs']:
    cells=[]
    for name in ['Ma200BtcRegimeFullCyclePortfolioStrategy','BtcTrendFastExitStrategy','BtcTrendCoinGuardStrategy','BuyAndHold']:
        source=single if name=='BtcTrendCoinGuardStrategy' else old
        r=next(x for x in source if x['pair']==pair and x['strategy']==name)
        cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
    lines.append('| '+pair.split('/')[0]+' | '+' | '.join(cells)+' |')
for h in (r for r in single if r['strategy']=='BuyAndHold'):
    b=next(r for r in old if r['strategy']=='BuyAndHold' and r['pair']==h['pair'])
    assert all(abs(float(h[k])-float(b[k]))<1e-8 for k in ['return_pct','wallet_drawdown_pct'])
guard=[r for r in single if r['strategy']=='BtcTrendCoinGuardStrategy']
stats={'median_return_pct':statistics.median(float(r['return_pct']) for r in guard),'median_drawdown_pct':statistics.median(float(r['wallet_drawdown_pct']) for r in guard),'worst_drawdown_pct':max(float(r['wallet_drawdown_pct']) for r in guard),'joint_passes':sum(r['joint_target_met']=='True' for r in guard)}
lines+=['',f"个币保护版十币收益中位数 {stats['median_return_pct']:.2f}%、回撤中位数 {stats['median_drawdown_pct']:.2f}%、最差回撤 {stats['worst_drawdown_pct']:.2f}%，严格联合达标 {stats['joint_passes']}/10（ETH、BNB、DOGE）；Portfolio 为 5/10。ADA/AVAX 明显退步，不能推广到十币通用策略。", '',
       '## 保留状态与限制', '',
       '原 Portfolio 正式身份不变。Growth 保留为稳健对照；个币保护版仅为 BTC/SOL/ETH 进攻研究候选，模拟配置为 user_data/config_trend_coin_guard_btc_sol_eth.json，不能自动晋升。没有改变运行服务。即时交接试验只作为研究记录，不提供活动策略配置。', '',
       '这仍是已观察历史的试验，没有独立样本外结论；日线收盘回撤不代表盘中回撤，未计额外滑点。不能保证未来收益或更低回撤。', '',
       'regime_comparison.csv 保留六策略完整数值；single_coin/summary.csv 为十币候选与持有；源文件和校验值、成交现金流和权益均保留。']
(folder/'REPORT.md').write_text('\n'.join(lines)+'\n')
manifest=json.loads((folder/'public_replay/source_manifest.json').read_text())
assert all(hashlib.sha256((folder/'public_replay/strategies'/name).read_bytes()).hexdigest()==sha for name,sha in manifest.items())
assert all(hashlib.sha256((root.parent.parent/'user_data/strategies'/name).read_bytes()).hexdigest()==sha for name,sha in manifest.items())
verify={'frozen_guard_regime_runs':5,'public_guard_regime_runs':5,'guard_single_coin_runs':10,'growth_control_engine_runs':4,'handover_trial_engine_runs':10,'new_rule_checks':5,'public_frozen_equity_match':True,'hold_references_match':True,'live_service_changed':False,'candidate_status':'btc_sol_eth_research_only','joint_target_bull_met':True,'joint_target_long_met':False,'single_coin_aggregate':stats,'max_abs_ledger_error':max(abs(float(r['ledger_error'])) for r in public+single+growth if r['ledger_error'])}
(folder/'verification.json').write_text(json.dumps(verify,indent=2)+'\n');print(json.dumps(verify,indent=2))
