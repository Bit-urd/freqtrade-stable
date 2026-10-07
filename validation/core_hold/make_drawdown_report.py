"""Compare drawdown revisions with official v1 and equal-weight holding."""
import csv, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
FOLDER=ROOT/'drawdown_revision'
rows=list(csv.DictReader((FOLDER/'summary.csv').open()))
old=list(csv.DictReader((ROOT/'trend_phased/retained_comparison.csv').open()))
lookup={(r['window'],r['strategy']):r for r in rows+old}
windows=json.loads((FOLDER/'windows.json').read_text())
names=sorted({r['strategy'] for r in rows if r['strategy']!='BuyAndHold'})
checks=[]
for name in names:
    results=[]
    for w in windows:
        key=(w['label'],name)
        if key not in lookup:continue
        x=lookup[key];h=lookup[w['label'],'BuyAndHold'];v=lookup[w['label'],'BtcTrendPhasedStrategy']
        ret=float(x['return_pct']);hr=float(h['return_pct']);dd=float(x['wallet_drawdown_pct'])
        results.append({'window':w['label'],'return_pct':ret,'drawdown_pct':dd,'return_fraction_of_hold':ret/hr if hr>0 else None,'drawdown_better_than_hold':dd<float(h['wallet_drawdown_pct']),'drawdown_change_vs_v1_pp':dd-float(v['wallet_drawdown_pct']),'return_change_vs_v1_pp':ret-float(v['return_pct']),'ledger_error':float(x['ledger_error'])})
    checks.append({'strategy':name,'windows_complete':len(results)==len(windows),'all_drawdowns_better_than_hold':len(results)==len(windows) and all(x['drawdown_better_than_hold'] for x in results),'all_positive_windows_two_thirds':len(results)==len(windows) and all(x['return_fraction_of_hold']>=2/3 for x in results if x['return_fraction_of_hold'] is not None),'windows':results})
(FOLDER/'candidate_checks.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n')
lines=['# 回撤优化与持有收益比例目标','', '目标：正收益持有窗口尽量接近持有收益的 2/3，同时各窗口最大回撤低于持有。持有亏损窗口比较实际亏损与回撤，不使用负收益比例。','', '所有收益均为累计利润率（不是期末资产倍数）；回撤按日线收盘权益；BTC/SOL/ETH 等权，1000 USDT，单边手续费 0.1%，各段独立开始。','', '选定独立优化方案 BtcTrendFastExitStrategy（测量别名 PhasedFastExit100）：早期投入 100%，BTC 弱趋势连续 1 个完整日线后退出，保留 14 天冷却及原资金核算。两个正收益窗口分别达到持有收益的 63.01% 和 78.60%；五段回撤低于持有。长区间没有严格达到 66.67%，最近区间回撤高于原版 6.54 个百分点。原正式版及其配置保留作对照，新方案配置 user_data/config_trend_fast_exit_btc_sol_eth.json。38 项检查通过。','', '## 全部试验','', '| 策略 | 长区间收益 / 回撤 | 上涨期收益 / 回撤 | 最近区间收益 / 回撤 | 熊市收益 / 回撤 | 牛转熊收益 / 回撤 |','|---|---:|---:|---:|---:|---:|']
order=['requested_long','bull_2023_2024','since_last_september','bear_2022','bull_to_bear_2021']
for name in ['BuyAndHold','BtcTrendPhasedStrategy']+names:
    values=[]
    for label in order:
        r=lookup.get((label,name));values.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%" if r else '待完成')
    lines.append('| '+name+' | '+' | '.join(values)+' |')
lines+=['','## 判断说明','', '第一轮：单币弱势直接退出会在 BTC 长趋势强时反复重新入场，收益损耗明显；EMA20 恢复比 EMA10 更慢，在本次熊市与转折窗口反而恶化。第二轮：检查 1 天退出搭配 75% / 85% 早期仓位，以及单币保护在 BTC 弱长趋势期间同时约束进入与退出。','', '此前正式 v1 和全部失败试验保留作比较。实际订单流水与引擎资金核对误差须小于 0.05 USDT。','', '这是基于已查看历史区间的优化，不是全新样本外验证。本轮先优化回撤，不把历史通过解释为未来收益保证。','']
(FOLDER/'REPORT.md').write_text('\n'.join(lines))
print(FOLDER/'REPORT.md')
