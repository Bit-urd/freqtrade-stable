"""Independently audit fills and compare frozen strategies with spot holding."""
import csv
import gzip
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

D = Path(__file__).resolve().parent
P = json.loads((D/'protocol.json').read_text())
END = datetime(2026, 10, 6).date()
PARTIAL = '--partial' in sys.argv
BASE, NEW = P['strategies']
rows, checks = [], []

def stats(curve):
    peak = 1000.
    dd = 0.
    for r in curve:
        equity = float(r['equity'])
        peak = max(peak, equity)
        dd = max(dd, (1-equity/peak)*100)
    equity = float(curve[-1]['equity'])
    cagr = ((equity/1000)**(365.25/len(curve))-1)*100
    return {'return_pct':(equity/1000-1)*100,'dd_pct':dd,'cagr_pct':cagr,
            'calmar':cagr/dd if dd>1e-10 else None,'ending_equity':equity,
            'exposure_pct':statistics.mean((1-float(r['cash'])/float(r['equity']))*100 for r in curve)}

def hold(history, start, warmup=False):
    available = history[61:] if warmup else history
    valid = [r for r in available if start<=r[0]<=END]
    buy = valid[0] if valid else None
    quantity = 1000/1.001/buy[1] if buy else 0.
    close = {r[0]:r[4] for r in history}
    day = start
    curve = []
    while day<=END:
        active = buy is not None and day>=buy[0]
        curve.append({'date':str(day),'cash':0. if active else 1000.,
                      'equity':quantity*close[day] if active else 1000.})
        day += timedelta(days=1)
    return stats(curve), str(buy[0]) if buy else None, curve

def audit(asset, window, strategy, prices, start):
    folder = D/asset/'results'/window
    trades = json.load(gzip.open(folder/(strategy+'_trades.json.gz'),'rt'))
    curve = list(csv.DictReader((folder/(strategy+'_equity.csv')).open()))
    assert curve[0][''][:10]==str(start) and curve[-1][''][:10]==str(END)
    assert len(curve)==(END-start).days+1
    flows = defaultdict(list)
    buys, extra = [], []
    for t in trades:
        assert t['pair']==asset+'/USDT'
        orders = [o for o in t['orders'] if o['order_filled_timestamp'] is not None]
        for i,o in enumerate(orders):
            day = datetime.fromtimestamp(o['order_filled_timestamp']/1000,timezone.utc).date()
            assert start<=day<=END
            if t['exit_reason']=='force_exit' and i==len(orders)-1:
                continue
            q=float(o['amount']);v=q*float(o['safe_price']);buy=o['ft_is_entry']
            change=-v*(1+float(t['fee_open'])) if buy else v*(1-float(t['fee_close']))
            flows[day].append((q if buy else -q,change))
            if buy:
                buys.append(day)
                if str(o.get('ft_order_tag','')).startswith('idle_cash:'):
                    extra.append(v)
    cash=1000.;quantity=0.;error=0.
    for r in curve:
        day=datetime.fromisoformat(r[''][:10]).date()
        for q,c in flows[day]:quantity+=q;cash+=c
        value=cash+(quantity*prices[day] if abs(quantity)>1e-9 else 0.)
        error=max(error,abs(value-float(r['equity'])),abs(cash-float(r['cash'])))
        assert quantity>=-1e-8
    assert error<.05,(asset,window,strategy,error)
    m=stats(curve)
    m.update({'trades':len(trades),'supplemental_orders':len(extra),
              'supplemental_stake_usdt':sum(extra),'first_entry':str(min(buys)) if buys else None})
    checks.append({'asset':asset,'window':window,'strategy':strategy,
                   'max_error_usdt':error,'trades':len(trades)})
    return m

for asset in P['assets']:
    actual={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (D/asset/'strategies').glob('*.py')}
    assert actual==P['source_sha256']
    raw=json.loads((D/'raw'/(asset+'.json')).read_text())
    history=[(datetime.fromtimestamp(r[0]/1000,timezone.utc).date(),*[float(v) for v in r[1:6]]) for r in raw]
    prices={r[0]:r[4] for r in history}
    for year in [2024,2025]:
        window='start_'+str(year)
        if not all((D/asset/'results'/window/(name+'_trades.json.gz')).exists() for name in P['strategies']):
            if PARTIAL:continue
            raise AssertionError((asset,window,'Incomplete case'))
        start=datetime(year,1,1).date()
        native={name:audit(asset,window,name,prices,start) for name in P['strategies']}
        h,buy,curve=hold(history,start)
        w,wb,_=hold(history,start,True)
        if not PARTIAL:
            with (D/asset/'results'/window/'ImmediateHold_equity.csv').open('w') as f:
                writer=csv.DictWriter(f,fieldnames=list(curve[0]));writer.writeheader();writer.writerows(curve)
        eligible=max(start,history[61][0]) if len(history)>61 else None
        r={'asset':asset,'year':year,'raw_first':str(history[0][0]),
           'full_history_at_start':history[0][0]<=start-timedelta(days=61),
           'eligible_start':str(eligible) if eligible else None,
           'eligible_days':max(0,(END-eligible).days+1) if eligible else 0,
           'hold_purchase':buy,'warmup_hold_purchase':wb,
           'same_listing_after_both_starts':history[0][0]>datetime(2025,1,1).date()}
        for prefix,m in [('base',native[BASE]),('current',native[NEW]),('hold',h),('warmup_hold',w)]:
            r.update({prefix+'_'+k:v for k,v in m.items()})
        r['return_delta_pp']=r['current_return_pct']-r['base_return_pct']
        r['dd_delta_pp']=r['current_dd_pct']-r['base_dd_pct']
        r['profit_retention']=r['current_return_pct']/r['base_return_pct'] if r['base_return_pct']>0 else None
        rows.append(r)

assert rows
if not PARTIAL:
    assert len(rows)==60 and len(checks)==120
    assert json.loads((D/'COMPLETED.json').read_text())['complete']
    assert 'Traceback' not in (D/'run.log').read_text()

def counts(rr):
    if not rr:return {'cases':0}
    return {'cases':len(rr),
            'base_positive_return_cases':sum(r['base_return_pct']>0 for r in rr),
            'current_positive_return_cases':sum(r['current_return_pct']>0 for r in rr),
            'hold_positive_return_cases':sum(r['hold_return_pct']>0 for r in rr),
            'current_return_wins_vs_base':sum(r['return_delta_pp']>1e-6 for r in rr),
            'current_return_losses_vs_base':sum(r['return_delta_pp']<-1e-6 for r in rr),
            'current_return_ties_vs_base':sum(abs(r['return_delta_pp'])<=1e-6 for r in rr),
            'current_calmar_wins_vs_base':sum(r['current_calmar'] is not None and r['base_calmar'] is not None and r['current_calmar']>r['base_calmar'] for r in rr),
            'dd_same_within_0_01pp':sum(abs(r['dd_delta_pp'])<=.01 for r in rr),
            'current_dd_worse_over_1pp':sum(r['dd_delta_pp']>1 for r in rr),
            'base_return_wins_vs_hold':sum(r['base_return_pct']>r['hold_return_pct']+1e-6 for r in rr),
            'current_return_wins_vs_hold':sum(r['current_return_pct']>r['hold_return_pct']+1e-6 for r in rr),
            'current_dd_lower_vs_hold':sum(r['current_dd_pct']<r['hold_dd_pct']-1e-6 for r in rr),
            'median_return_delta_pp':statistics.median(r['return_delta_pp'] for r in rr),
            'median_dd_delta_pp':statistics.median(r['dd_delta_pp'] for r in rr),
            'base_profitable_but_profit_retention_below_0_75':sum(r['profit_retention'] is not None and r['profit_retention']<.75 for r in rr),
            'extra_supplemental_orders':sum(r['current_supplemental_orders'] for r in rr)}

summary={'all':counts(rows),'full_history':counts([r for r in rows if r['full_history_at_start']]),
         'late_history':counts([r for r in rows if not r['full_history_at_start']]),
         'eligible_under_180_days':counts([r for r in rows if r['eligible_days']<180]),
         'years':{str(y):counts([r for r in rows if r['year']==y]) for y in [2024,2025]}}
prefix='partial_' if PARTIAL else ''
with (D/(prefix+'comparison.csv')).open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(D/(prefix+'summary.json')).write_text(json.dumps(summary,indent=2))
(D/(prefix+'audit.json')).write_text(json.dumps({'all_passed':True,'native_curves_audited':len(checks),
    'max_error_usdt':max(c['max_error_usdt'] for c in checks),'checks':checks},indent=2))
if PARTIAL:
    print(json.dumps(summary,indent=2))
    sys.exit(0)

def pct(v):return f'{v:+.2f}%'
lines=['# 30币单独运行：MA200原版、当前补仓版与持有','',
       '每币分别独立1000 USDT，2024与2025年1月1日起，到2026-10-06结束；手续费0.1%，日线现货，max_open_trades=1，无充值，不调整策略指标或交易规则。固定30币：'+', '.join(P['assets'])+'。', '',
       'MA200原版为ma200_btc_regime_full_cycle_portfolio_strategy.py；当前版为Ma200CashSupplementStrategy，包括趋势确认交接补仓及闲置现金补仓。120条策略原生回测中24条复用同代码、同配置、同可用行情的已有结果，96条新运行；所有120条成交净值均独立核对。持有按起点首个可用日线开盘买入，计开仓费，上市前留现金，期末按收盘估值、不假定卖出。', '',
       '数据较晚开始的交易对并非完整两年样本：主表明确可交易天数及历史覆盖。数据首日可能受上市或代币迁移影响，本轮不自动拼接其他交易对的历史。数据首日在2025起点之后的币，两次测试往往重复同一交易路径，不能作为两个独立证据。收益和CAGR含数据出现前现金等待时间。另附61日预热后买入的持有口径，便于检查首次可用日买入对比较的影响。', '',
       '## 汇总','',
       '| 样本 | 案例数 | 当前版收益赢/输/平原版 | 原版收益跑赢持有 | 当前版收益跑赢持有 | 当前版回撤低于持有 | 收益差中位数pp |','|---|---:|---:|---:|---:|---:|---:|']
for label,key in [('全部','all'),('起点已有完整预热历史','full_history'),('起点历史不足或尚未上市','late_history'),('有效交易期不足180天','eligible_under_180_days')]:
    s=summary[key]
    if not s['cases']:continue
    lines.append(f"| {label} | {s['cases']} | {s['current_return_wins_vs_base']}/{s['current_return_losses_vs_base']}/{s['current_return_ties_vs_base']} | {s['base_return_wins_vs_hold']} | {s['current_return_wins_vs_hold']} | {s['current_dd_lower_vs_hold']} | {s['median_return_delta_pp']:+.2f} |")
lines+=['','| 起点 | 原版正收益案例 | 当前版正收益案例 | 持有正收益案例 | 当前版收益赢/输/平原版 |','|---|---:|---:|---:|---:|']
for year in [2024,2025]:
    s=summary['years'][str(year)]
    lines.append(f"| {year} | {s['base_positive_return_cases']}/{s['cases']} | {s['current_positive_return_cases']}/{s['cases']} | {s['hold_positive_return_cases']}/{s['cases']} | {s['current_return_wins_vs_base']}/{s['current_return_losses_vs_base']}/{s['current_return_ties_vs_base']} |")
for year in [2024,2025]:
    lines+=['','## '+str(year)+'起点','',
            '| 标的 | 原版收益 | 当前版收益 | 持有收益 | 原版回撤 | 当前版回撤 | 持有回撤 | 起点完整历史 | 可交易天数 |','|---|---:|---:|---:|---:|---:|---:|---|---:|']
    for r in rows:
        if r['year']!=year:continue
        lines.append(f"| {r['asset']} | {pct(r['base_return_pct'])} | {pct(r['current_return_pct'])} | {pct(r['hold_return_pct'])} | {r['base_dd_pct']:.2f}% | {r['current_dd_pct']:.2f}% | {r['hold_dd_pct']:.2f}% | {'是' if r['full_history_at_start'] else '否'} | {r['eligible_days']} |")
lines+=['','## 反例：当前版收益下降','',
        '| 标的 | 起点 | 原版收益 | 当前版收益 | 少赚U | 回撤变化pp | 正利润保留比例 |','|---|---:|---:|---:|---:|---:|---:|']
for r in sorted((r for r in rows if r['return_delta_pp']<-1e-6),key=lambda r:r['return_delta_pp']):
    retention=f"{r['profit_retention']*100:.2f}%" if r['profit_retention'] is not None else '原版非正收益'
    lines.append(f"| {r['asset']} | {r['year']} | {pct(r['base_return_pct'])} | {pct(r['current_return_pct'])} | {-r['return_delta_pp']*10:.2f} | {r['dd_delta_pp']:+.3f} | {retention} |")
lines+=['','## 回撤恶化超过1个百分点','',
        '| 标的 | 起点 | 原版回撤 | 当前版回撤 | 当前版收益差pp |','|---|---:|---:|---:|---:|']
for r in rows:
    if r['dd_delta_pp']>1:lines.append(f"| {r['asset']} | {r['year']} | {r['base_dd_pct']:.2f}% | {r['current_dd_pct']:.2f}% | {r['return_delta_pp']:+.2f} |")
lines+=['','## 新币历史及持有口径','',
        '| 标的 | 起点 | 数据首日 | 策略最早可交易日 | 持有买入日 | 直接持有收益 | 预热后持有收益 |','|---|---:|---|---|---|---:|---:|']
for r in rows:
    if not r['full_history_at_start']:
        lines.append(f"| {r['asset']} | {r['year']} | {r['raw_first']} | {r['eligible_start']} | {r['hold_purchase']} | {pct(r['hold_return_pct'])} | {pct(r['warmup_hold_return_pct'])} |")
lines+=['','## 验证边界','',
        f"所有策略源文件与冻结哈希一致，120条成交净值重建最大误差{max(c['max_error_usdt'] for c in checks):.3g} U。日线净值回撤不包含日内最差价格，不能当作实盘可保证的回撤上限。原生引擎手续费及成交模型与交易所实际扣费、滑点、最低订单限制存在差异。", '',
        f"当前版额外闲置现金补仓成交总数为{summary['all']['extra_supplemental_orders']}。为零的案例主要反映交接改动，不证明闲置补仓或新增充值创造收益。统计为单币独立账户，不是30币组合，不能平均单币收益代替组合回测。", '',
        '固定当前存活币名单存在幸存者及事后选择偏差。两个窗口重叠，新币路径可能重复，不能把胜率当成独立统计检验。不根据结果删除币或增加币种特例。无充值，候选未部署。']
(D/'REPORT.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(summary,indent=2))
print('All 120 native curves audited and 60 holding cases compared.',flush=True)
