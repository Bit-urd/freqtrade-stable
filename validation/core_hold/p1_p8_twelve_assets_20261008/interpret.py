"""Add conclusions supported by fixed-stage results; no extra tuning."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent
stats=json.loads((root/'aggregate.json').read_text());rows=list(csv.DictReader((root/'comparison_matrix.csv').open()));idx={(r['asset'],r['phase']):r for r in rows}
def triplet(asset,phase):
 r=idx[asset,phase]
 return '，'.join(f"{label} {float(r[p+'_return_pct']):+.2f}% / {float(r[p+'_wallet_drawdown_pct']):.2f}%" for p,label in [('original','原版'),('two_day','两天版'),('hold','持有')])
text=['## 如何理解这些阶段','',
 f"1. **P1：保护回撤与捕捉 V 型反弹是两件事。** BTC：{triplet('BTC','P1')}。较低阶段回撤并不保证期末收益胜过持有。原策略使用日线确认，stoploss=-0.99；本次没有加入新的紧止损，日线收盘回撤也不能代表盘中黑天鹅损失。",
 f"2. **P2：强牛市中两天确认没有额外贡献。** {stats['by_phase']['P2']['return_equal']} 个可测标的两版相同。延迟 BTC 退出不会改变入场、个币退出、14 日冷却或 MA150 等待，因此不能解决这些条件造成的上涨参与不足。DOGE：{triplet('DOGE','P2')}。上市初期五币另需考虑 MA150 等待，不能直接用其持有差距评价退出改动。",
 f"3. **P3：暴跌震荡时，额外一天不必然减少假突破损失。** 收益改善 {stats['by_phase']['P3']['return_better']}、下降 {stats['by_phase']['P3']['return_worse']}。LINK：{triplet('LINK','P3')}。SOL、AAVE 的改善也如实保留在完整表中，不能概括所有币都退步。",
 f"4. **P4：熊市代价最一致。** 收益下降 {stats['by_phase']['P4']['return_worse']}/{stats['by_phase']['P4']['n']}，回撤扩大 {stats['by_phase']['P4']['dd_worse']}/{stats['by_phase']['P4']['n']}。SOL：{triplet('SOL','P4')}。虽然两版均能明显缓解持有的长期下跌损失，两天版在这个阶段没有优势。",
 f"5. **P5：修复行情需要分别看币，不能用一项总收益概括。** 两天版收益改善/下降/相同为 {stats['by_phase']['P5']['return_better']}/{stats['by_phase']['P5']['return_worse']}/{stats['by_phase']['P5']['return_equal']}。ARB 从 2023-05-23 起测且尚待 MA150，APT 也有 MA150 等待，两者不纳入成熟完整样本。",
 f"6. **P6：趋势上涨主要由原有入场和个币持仓规则决定。** 两天版收益改善/下降/相同为 {stats['by_phase']['P6']['return_better']}/{stats['by_phase']['P6']['return_worse']}/{stats['by_phase']['P6']['return_equal']}。SOL：{triplet('SOL','P6')}。若两版相同而明显落后持有，差距就不是本轮改动能解决的问题。",
 f"7. **P7：高位震荡要核对收益与回撤是否同步改善。** 收益改善 {stats['by_phase']['P7']['return_better']}/{stats['by_phase']['P7']['n']}，回撤改善 {stats['by_phase']['P7']['dd_better']}/{stats['by_phase']['P7']['n']}，两项同时改善 {stats['by_phase']['P7']['joint_better']}/{stats['by_phase']['P7']['n']}；所有退步币均列在上表。",
 f"8. **P8：资产分化保留单币结果。** XRP：{triplet('XRP','P8')}。ETH：{triplet('ETH','P8')}。两版仍保留相同 BTC 入场过滤，退出延迟不等于新增独立行情通道；只看 BTC 或平均值会掩盖不同标的表现。",'',
'这些日期是用户指定的历史测试框架，阶段标签用于分组，不表示区间内每天处于同一种行情。单币表现也不能直接替代同时持有十二币的组合回测，尤其原版账户回撤风控存在跨持仓影响。ARB/APT 的供应压力、XRP 的事件驱动等已体现在历史价格中，但本次没有单独建立解锁或新闻事件模型。','',
'## 综合取舍口径','',
'按用户最新要求，不因为某些阶段收益稍低或回撤扩大就淘汰候选。重点综合：关键时刻保留的趋势收益、是否避免反复退出或严重账户损失、最差阶段结果，以及跨标的一致性。以下额外列出收益差异最大的实际案例与尾部损失分布，不设置固定回撤门槛。此前多币长周期的改善仍是已有证据，但与本轮“单币、阶段起点现金重置”的条件不同，不能互相替代。正式策略未切换属于本轮测试范围，不等于预先否定两天版。','']
p=root/'REPORT.md';s=p.read_text();s=s.replace('## 验证与文件','\n'.join(text)+'\n## 验证与文件');s=s.replace('## 96 个组合完整结果','## 图表\n\n![两天退出相对原版](exit_comparison_heatmap.png)\n\n![三组收益与回撤](three_way_return_drawdown.png)\n\n## 96 个组合完整结果');p.write_text(s)
print('Added fixed-stage interpretation')
