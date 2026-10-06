"""Compare total portfolio equity using consistent daily closing valuations."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import analyze as a

ROOT=Path('/research');FOLDER=ROOT/'regime_comparison'
LABELS={'BuyAndHold':'等权持有',
        'Ma200BtcRegimeFullCyclePortfolioStrategy':'原 Portfolio',
        'Ma200BtcRegimeFullCycleCoreHoldStrategy':'旧 CoreHold',
        'Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy':'Growth（当前默认）',
        'Ma200BtcRegimeFullCycleCoreHoldRecoveryStrategy':'Recovery（实验）'}
parser=argparse.ArgumentParser();parser.add_argument('--available',action='store_true');args=parser.parse_args()
windows=json.loads((FOLDER/'windows.json').read_text())
a.PAIRS=['BTC/USDT','SOL/USDT','ETH/USDT'];a.HISTORY={p:a.HISTORY[p] for p in a.PAIRS}
rows=[];market=[]
for window in windows:
    folder=FOLDER/'results'/window['label']
    archives=sorted(folder.glob('*.zip'))
    if not archives:
        if args.available:
            continue
        raise FileNotFoundError(f'Missing backtest {window["label"]}')
    with ZipFile(archives[-1]) as z:
        name=next(n for n in z.namelist() if n.endswith('.json')
                  and not n.endswith('_config.json') and 'strategy' not in n)
        strategies=json.loads(z.read(name))['strategy']
    example=next(iter(strategies.values()))
    start=pd.to_datetime(example['backtest_start_ts'],unit='ms',utc=True).floor('D')
    end=pd.to_datetime(example['backtest_end_ts'],unit='ms',utc=True).floor('D')
    required_start=pd.Timestamp(window['timerange'].split('-')[0],tz='UTC')
    required_end=pd.Timestamp(window['timerange'].split('-')[1],tz='UTC')
    assert start==required_start,(window,start)
    assert end==min(required_end,a.HISTORY['BTC/USDT'].index.max()),(window,end)
    dates=pd.date_range(start,end,freq='D')
    bench=a.benchmark(dates);bench.to_csv(folder/'equity_BuyAndHold.csv')
    common={'window':window['label'],'title':window['title'],
            'start':str(start.date()),'end':str(end.date()),'days':len(dates)}
    rows.append({**common,'strategy':'BuyAndHold',**a.stats(bench)})
    for name,result in strategies.items():
        assert name in LABELS,name
        curve,terminal_cash,_=a.ledger(result['trades'],dates)
        delta=terminal_cash-result['final_balance'];assert abs(delta)<.05,(window,name,delta)
        curve.to_csv(folder/f'equity_{name}.csv')
        rows.append({**common,'strategy':name,**a.stats(curve),
                     'engine_final_balance':result['final_balance'],
                     'ledger_reconciliation_error':delta,'trades':result['total_trades']})
    btc=a.HISTORY['BTC/USDT'];span=btc.loc[dates]
    ma200=btc.close.rolling(200).mean().reindex(dates)
    opening=float(span.open.iloc[0]);closing=float(span.close.iloc[-1]);peak=float(span.close.max())
    equity=span.close/opening
    dd=float((1-equity/equity.cummax().clip(lower=1)).max()*100)
    market.append({**common,'btc_first_open':opening,'btc_last_close':closing,
                   'btc_return_pct':(closing/opening-1)*100,
                   'btc_peak_close':peak,'btc_peak_date':str(span.close.idxmax().date()),
                   'btc_max_close_drawdown_pct':dd,
                   'btc_above_ma200_days_pct':float((span.close>ma200).mean()*100)})
frame=pd.DataFrame(rows);frame.to_csv(FOLDER/'summary.csv',index=False)
pd.DataFrame(market).to_csv(FOLDER/'market_regimes.csv',index=False)
lines=['# BTC / SOL / ETH：多市场区间对比', '',
       '初始资金 1,000 USDT，3 个槽位，100% 可用资金，单边手续费 0.1%。'
       '区间边界使用 UTC 日线。去年 9 月为 2025-09-01，最新完整日线为 2026-10-05。', '',
       '每段都独立从现金开始；期初没有继承上一段持仓。等权基准在期初开盘各买 1/3，'
       '随后不再平衡。三个币在所有起点前均有足够历史。', '',
       '## 收益率比较', '',
       '| 区间 | 实际日期 | 等权持有 | 原 Portfolio | 旧 CoreHold | Growth（当前默认） | Recovery（实验） |',
       '|---|---|---:|---:|---:|---:|---:|']
for window in windows:
    selected=frame[frame.window==window['label']]
    if selected.empty:
        continue
    by_name=selected.set_index('strategy')
    dates=f"{selected.iloc[0].start}～{selected.iloc[0].end}"
    numbers=[f"{float(by_name.loc[name,'return_pct']):+.2f}%" for name in LABELS]
    lines.append('| '+window['title']+' | '+dates+' | '+' | '.join(numbers)+' |')
lines+=['', '## 最大组合回撤', '',
        '| 区间 | 等权持有 | 原 Portfolio | 旧 CoreHold | Growth（当前默认） | Recovery（实验） |',
        '|---|---:|---:|---:|---:|---:|']
for window in windows:
    selected=frame[frame.window==window['label']]
    if selected.empty:
        continue
    by_name=selected.set_index('strategy')
    numbers=[f"{float(by_name.loc[name,'wallet_drawdown_pct']):.2f}%" for name in LABELS]
    lines.append('| '+window['title']+' | '+' | '.join(numbers)+' |')
lines+=['', '## 区间标签核对', '',
        '熊市指总体下跌阶段，期间仍有反弹，并非每天单调下跌。'
        '牛转熊区间包含 2021 年后半年的上涨与 2022 年下跌；'
        '2023–2024 为整体上涨周期，也包含回调。', '',
        '| 区间 | BTC 起点开盘 | BTC 终点收盘 | BTC 涨跌 | 最高收盘日期 | BTC 日线最大回撤 | BTC 高于 MA200 的天数占比 |',
        '|---|---:|---:|---:|---|---:|---:|']
for m in market:
    lines.append(f"| {m['title']} | {m['btc_first_open']:.2f} | {m['btc_last_close']:.2f} | "
                 f"{m['btc_return_pct']:+.2f}% | {m['btc_peak_date']} | "
                 f"{m['btc_max_close_drawdown_pct']:.2f}% | {m['btc_above_ma200_days_pct']:.2f}% |")
if len(market)==len(windows):
    lines+=['', '## 本轮结论', '',
            'Growth 相比旧 CoreHold 在最近区间、牛转熊、上涨周期的收益均改善，'
            '纯熊市结果完全相同。Recovery 在纯熊市和牛转熊区间与 Growth 相同，'
            '在最近区间与上涨周期反而更差且回撤更大，因此保留 Growth 为当前默认。', '',
            '纯熊市四策略均亏 51.43%，最大组合回撤 54.12%。'
            'BTC 在该区间没有一根日线收盘高于 MA200；所有版本使用相同熊市分档累积，'
            '所以牛市仓位优化不能改变该区间结果。下一步改进重点应是熊市买入资金规则。', '',
            '牛转熊中 Growth 期末亏损仅 1.84%，但中途最大回撤达 63.53%。'
            '期末收益较好并不意味着过程回撤较小。上涨周期中持有收益明显更高，'
            'Growth 平均现金占比仍有 34.62%，和全程持有的暴露程度不同。', '']
lines+=['', '## 策略定义及会计口径', '',
        '- 原 Portfolio：此前未经修改的 Ma200BtcRegimeFullCyclePortfolioStrategy。',
        '- 旧 CoreHold：研究快照中 HANDOVER_TOP_UP=False、BULL_WEEKLY_SIZING=True 的旧默认。',
        '- Growth：HANDOVER_TOP_UP=True、BULL_WEEKLY_SIZING=False，和当前用户核心策略默认相同；'
        '原入场规则、50% 核心、BTC 两天转熊退出保留。',
        '- Recovery：Growth 再开启 CORE_RESTORE_ON_RECOVERY 与 HANDOVER_CORE_HOLD。', '',
        '收益基于现金加剩余代币乘终点日线收盘价，包含未平仓浮盈亏。'
        '期末引擎强制平仓订单从盯市曲线剔除；另提供清算收益字段，统一扣剩余持仓的卖出费。'
        '已实现利润已进入现金，不重复相加。', '',
        '全部订单现金流与引擎 final_balance 核对，误差小于 0.05 USDT。'
        '回撤使用逐日总权益及其历史最高值，包含起始 1,000 USDT。', '',
        '这是固定三币的历史回放。部分区间与先前研究重叠，不能全部称为全新样本外验证。'
        '使用日线开盘成交模拟，未计额外滑点。', '',
        '复现：使用父目录 README.md 的镜像与挂载，运行 /research/run_regime_comparison.py，'
        '随后运行 /research/analyze_regime_comparison.py。完整统计见 summary.csv，'
        '市场核对见 market_regimes.csv，逐日权益和实际回测参数见 results/*。', '']
(FOLDER/'REPORT.md').write_text('\n'.join(lines))
print(frame[['title','strategy','return_pct','wallet_drawdown_pct','mean_idle_cash_pct']].to_string(index=False))
print('Checked',len(frame),'portfolio curves. Finished windows:',len(market),flush=True)
