import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent;study=root.parent;new='BtcTwoDayExitCycleRiskStrategy';old='BtcCoinGuardCycleRiskStrategy'
coins=list(csv.DictReader((root/'coin_gap.csv').open()));risks=list(csv.DictReader((root/'risk_stage_days.csv').open()));states=list(csv.DictReader((root/'signal_state_gap.csv').open()));months=list(csv.DictReader((root/'monthly_gap.csv').open()));summary=list(csv.DictReader((study/'summary.csv').open()));si={(r['window'],r['strategy']):r for r in summary}
labels=['Main10_full_cycle','Main10_mature11_control','Mature11_full_cycle','Requested12_mature11_cash'];titles=['十币长窗口','十币同日期控制','十一币含PUMP','十二槽位，HYPE预算留现金']
lines=['# 为什么这些组合跑不过持有：持仓数量与实际收益差归因','',
'主要差距集中于 ZEC；近期加入 PUMP 后，它也构成重要差距。两天版在其余币上的合计盈亏多数反而好于持有。两天退出相对原版的改善，不等于解决了相对持有的差距。','',
'以下使用现有成交与冻结日线，不修改策略、不重跑参数。所有收益差以1000 USDT初始账户计算，正值表示持有赚得更多。','',
'## 四组差距来自哪些币','', '|账户|持有减两天版总盈亏差 USDT|ZEC造成差距 USDT|PUMP造成差距 USDT|其他币合计差距 USDT|','|---|---:|---:|---:|---:|']
for label,title in zip(labels,titles):
 cs=[r for r in coins if r['window']==label and r['strategy']==new];gap=sum(float(r['gap']) for r in cs);z=next(float(r['gap']) for r in cs if r['asset']=='ZEC');p=next((float(r['gap']) for r in cs if r['asset']=='PUMP'),0)
 lines.append(f'|{title}|{gap:.2f}|{z:.2f}|{p:.2f}|{gap-z-p:+.2f}|')
lines+=['','负的“其他币差距”表示两天版在这些币合计赚得更多。某一币的差距可以大于账户总差距，因为其他币补回了一部分；这不是百分比分母错误。','',
'十币长窗口，ZEC 持有从初始100 USDT预算产生5385.27 USDT盈利；原版399.07，两天版245.96。持有减两天版净差5139.32，已超过整个组合4632.57的差距。其余九币合计两天版比持有多赚506.75。持有整个组合的净利润中约79.93%来自ZEC，不能把这个样本解释为所有币持续持有都更好。','',
'## 已经持仓，为什么依然漏掉大部分上涨','',
'持有基准的币数保持不变；策略多次卖出、买回，实际币数会变化。卖出后错过上涨，再以更高价格、当时已实现盈亏后的预算买回，往往买到更少的币；之前的亏损、减仓也可能进一步影响预算。账户现金比例不等于每个币持仓数量的比例。','',
'|账户、标的|策略盈利 USDT|持有盈利 USDT|日终有仓位的日期比例|平均持币数/持有币数|期末持币数/持有币数|','|---|---:|---:|---:|---:|---:|']
for label,asset in [('Main10_full_cycle','ZEC'),('Main10_mature11_control','ZEC'),('Mature11_full_cycle','ZEC'),('Mature11_full_cycle','PUMP')]:
 r=next(r for r in coins if r['window']==label and r['strategy']==new and r['asset']==asset);vals=[float(r[k]) for k in ['strategy_profit','hold_profit','held_day_pct','mean_qty_vs_hold_pct','end_qty_vs_hold_pct']]
 lines.append(f'|{label} {asset}|{vals[0]:+.2f}|{vals[1]:+.2f}|{vals[2]:.2f}%|{vals[3]:.2f}%|{vals[4]:.2f}%|')
lines+=['','平均币数比包含空仓日期的零仓位；它不同于资金权重或投资收益率。', '',
'**直接例子：十币长窗口中的 ZEC，2026 年 9 月。** 持有该币的组合盈利贡献为 +2369.31 USDT，两天版为 +149.35，差额 +2219.96。两天版当时已有持仓（2026-08-20 开仓，持有到窗口结束），因此这一段的差距不能说成“完全没有入场”；主要是早期未保留持有基准的币数，最后一波仅用较小的币数参与。','',
'## BTC 过滤、冷却和个币退出分别有什么证据','',
'将每个币的逐日盈利差按当日实际成交/持仓与上一根完成日线的条件分类。成交日单列，避免把卖出当日的盈亏都算成空仓。整天无仓且无成交时，按BTC禁止入场、个币禁止入场、弱BTC14日冷却的顺序归类；条件可能重叠，优先分类不代表唯一原因。','',
'### 两天版 ZEC：十币长窗口','', '|当日状态|日期数|持有减策略的净盈利差 USDT|','|---|---:|---:|']
for r in states:
 if r['window']=='Main10_full_cycle' and r['strategy']==new and r['asset']=='ZEC':lines.append(f"|{r['state']}|{r['days']}|{float(r['gap']):+.2f}|")
lines+=['','持仓日与成交日的差距相当大，说明仅放宽 BTC 入场并不能自动恢复历史上已经失去的币数。与此同时，空仓时BTC过滤与冷却确实也存在明显机会损失。','',
'### 近期十一币：BTC 过滤也避免了一部分跌幅','', '|标的|空仓且BTC禁止入场的净差|空仓且个币禁止入场的净差|空仓且冷却未满14天的净差|','|---|---:|---:|---:|']
for asset in ['ZEC','PUMP']:
 rs=[r for r in states if r['window']=='Mature11_full_cycle' and r['strategy']==new and r['asset']==asset];d={r['state']:float(r['gap']) for r in rs}
 lines.append(f"|{asset}|{d.get('空仓且BTC禁止入场',0):+.2f}|{d.get('空仓且个币禁止入场',0):+.2f}|{d.get('空仓且弱BTC冷却未满14天',0):+.2f}|")
lines+=['','近期BTC禁止入场日期的净差为负，表示这些日期合计持有反而亏得更多，过滤有保护作用。近期漏掉的收益主要落在个币条件、冷却、实际交易时点及较小的持仓数量，不能把所有差距都归咎于BTC过滤。原版和两天版都保留14日冷却；BTC通过EMA10恢复通道允许入场、但还没严格站上MA150时，仍可能因同币刚平仓而等待冷却。','',
'## 现金、账户减仓与费用','', '|账户|原版平均现金占比|两天版平均现金占比|持有平均现金占比|两天版实际成交费用 USDT|','|---|---:|---:|---:|---:|']
for label,title in zip(labels,titles):
 vals=[float(si[label,n]['mean_idle_cash_pct']) for n in [old,new,'BuyAndHold']];fee=float(si[label,new]['normal_fees']);lines.append(f'|{title}|{vals[0]:.2f}%|{vals[1]:.2f}%|{vals[2]:.2f}%|{fee:.2f}|')
lines+=['','现金占比是逐日现金/账户权益的均值，只描述暴露，不等于“如果投出这些现金就能多赚多少”。尤其十二槽位账户的现金比例会随着其他币价值变化，不始终等于8.33%。','',
'近期十币、十一币及十二槽位三个窗口，两天版的240个风控观察日全部处于100%风险档，未触发75%或50%档。因此约55%—58%的平均现金主要与入场/退出/冷却及各币预算未投入有关，不能怪罪于账户回撤减仓。十币长窗口则有360日处于75%档、12日处于50%档，确有额外影响，但这里未做删除减仓规则的反事实回测。','',
'交易费有影响，却解释不了主要差距：十币长窗口两天版实际费用约127.94 USDT，持有约1.00，账户盈利差4632.57；十一币两天版费用约16.47，持有约1.00，盈利差407.13。反复交易的价格时机与错过复利通常比单纯手续费更关键。费用已包含在盈亏中，不能再加减一次当成精确无费反事实。','',
'## 综合理解','',
'这组数据最主要的矛盾是：持有保留了 ZEC、PUMP 的币数并参与大涨；策略在风险过滤、退出、冷却和买回过程中没有保留同样的上涨暴露。两天确认缓解了部分过早退出，所以总体能优于原版，但未改变大部分持仓规则，仍可能大幅落后持有。',
'此前建议采用两天版，结论范围是“相对原版的组合升级”；不是“这套策略在当前币池已综合胜过持有”。十币长窗口两天版回撤44.13%、持有56.75%，但收益210.52%对673.78%，收益代价很大，应如实看待。十一币近期则以53.62%/12.54%对94.34%/32.63%，体现更明显的低回撤取舍。','',
'以上属于实际路径的会计与条件归因，不证明删除BTC过滤、冷却或减仓就能拿回表中的盈利；改变规则会改变后续成交、风险状态、预算和亏损。后续若做优化，应针对关键退出后买回与币数变化验证，不从此次归因直接拼接事后最优规则。','',
'## 核验与文件','']
v=json.loads((root/'verification.json').read_text());lines += [f"重建并核对 {v['coin_pnl_reconstructions']} 条逐币盈亏路径，最大与此前成交账差异 {v['maximum_pnl_error']:.10g} USDT；逐日条件分类的收益差之和与总收益差一致。",'',
'[逐币盈亏差](coin_gap.csv) · [条件分类](signal_state_gap.csv) · [逐月差距](monthly_gap.csv) · [ZEC/PUMP逐日数量与盈亏](zec_pump_daily.csv) · [实际交易](zec_pump_trades.csv) · [风险档位日期数](risk_stage_days.csv) · [核验](verification.json)。','']
(root/'REPORT.md').write_text('\n'.join(lines));print('Written hold-gap report')
