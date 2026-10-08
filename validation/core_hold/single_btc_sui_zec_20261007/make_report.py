import csv,json,gzip,hashlib
from pathlib import Path
root=Path(__file__).parent
rows=list(csv.DictReader((root/'summary.csv').open()));windows=json.loads((root/'windows.json').read_text())
assert len(rows)==len(windows)*3
manifest=json.loads((root/'source_manifest.json').read_text())
for name,digest in manifest.items():assert hashlib.sha256((root/'strategies'/name).read_bytes()).hexdigest()==digest
text=['# BTC、SUI、ZEC 单币账户比较','', '代码：当前两个策略的冻结副本。每个账户只交易一个币，max_open_trades=1，BTC保留为行情判断指标，SUI/ZEC账户不交易BTC。初始1000 USDT、现货、手续费每侧0.1%、不另计滑点。每个窗口从现金重新开始，风控、钱包、交易历史和策略实例全部重置。收益和最大回撤按日线收盘盯市，包含浮亏，排除终点人为强平。持有于窗口首日开盘一次买入，不再平衡；买入计手续费，期末不卖出。', '', 'BTC沿用上一轮截至2026-10-06的冻结行情；SUI、ZEC从Binance公共行情接口下载至同一天。未完成日线和周线被过滤。SUI于2023-05-03上市，本次最早起点2023-07-05（63根此前日线），符合两个策略的60根新币要求。CycleRisk另外要求MA150有效，故最早窗口前段可能持有现金。这是实际策略行为，未把其开始交易日当作整个窗口起点。', '', '每格为累计收益 / 最大回撤（正数）。2026仅截至10月6日；年度行是独立开户结果，不能连乘为连续账户收益。']
labels={'full_cycle':'长周期','bear_2022':'2022熊市','bull_2023_2024':'2023–2024','continuous_2023_latest':'2023至今','since_maturity':'上市成熟后至今','early_bull':'上市成熟后至2024末','year_2024':'2024全年','year_2025':'2025全年','year_2026':'2026至今','recent':'近期'}
counts=[]
for coin in ['BTC','SUI','ZEC']:
 text+=['',f'## 只交易 {coin}','', '| 区间 | Portfolio 收益 / 回撤 | CycleRisk 收益 / 回撤 | 持有该币 收益 / 回撤 |','|---|---:|---:|---:|']
 for w in windows:
  if w['pair']!=coin+'/USDT':continue
  group={r['strategy']:r for r in rows if r['window']==w['label']}
  assert len(group)==3
  cells=[]
  for name in ['Ma200BtcRegimeFullCyclePortfolioStrategy','BtcCoinGuardCycleRiskStrategy','BuyAndHold']:
   r=group[name];assert r['start']==w['start'] and r['end']==w['end']
   cells.append(f"{float(r['return_pct']):+.2f}% / {float(r['wallet_drawdown_pct']):.2f}%")
   if name=='BuyAndHold':continue
   assert abs(float(r['ledger_error']))<.05
   payload=json.loads(gzip.open(root/'results'/w['label']/(name+'.json.gz'),'rt').read())
   assert all(t['pair']==w['pair'] for t in payload['trades'])
   orders=[o for t in payload['trades'] for o in t['orders'] if o['order_filled_timestamp'] is not None]
   force=sum(t['exit_reason']=='force_exit' for t in payload['trades'])
   counts.append(dict(pair=w['pair'],window=w['label'],strategy=name,new_positions=len(payload['trades']),normal_fills=len(orders)-force,terminal_force_exits=force))
  text.append(f"| {w['start']}～{w['end']} | "+' | '.join(cells)+' |')
text+=['', '## 本次结果解读', '', 'BTC：CycleRisk在长周期、2022熊市和2023–2024上涨期的收益与回撤都优于Portfolio；但2025全年及近期Portfolio占优，2026两者接近。2023至今CycleRisk收益363.41%，约为持有BTC收益416.66%的87.22%，回撤34.86%低于持有52.97%。', '', 'SUI：2023-07-05至今两个策略收益均高于持有，但最大回撤都约67%。Portfolio在2024和2025更好，CycleRisk在2026收益55.53%对Portfolio5.91%更强，近期则收益近似而Portfolio回撤较浅。不能把CycleRisk视为普遍低风险版本。', '', 'ZEC：2025、2026及近期Portfolio的收益与回撤都优于CycleRisk，长周期仍有89.28%最大回撤。近期CycleRisk19次开仓、18次正常全平仓全部由BTC弱势触发；Portfolio3次开仓、2次正常全平仓，终点强平不计正常退出。这支持BTC快速退出条件频繁切断ZEC持仓的解释，但未做消融实验，不能量化各条规则对全部收益差的贡献。', '', '这些结果不支持一个策略在三个币上统一占优。BTC上的CycleRisk折中较强，SUI优劣随年度改变，ZEC近期Portfolio表现更强但长周期两者都承受极深回撤。']
text+=['', '## 解读边界','', '固定单币账户剔除了原三币组合中独立复利和资金分配的跨币影响，但SUI/ZEC仍受BTC行情开关约束。若个币行情与BTC错位，趋势策略可能错过该币独立上涨，也可能因BTC恢复而在弱币上增加风险。Portfolio熊市积累依据BTC偏离MA200，而非标的自身估值。', '', '这些区间相互重叠，且历史已用于研究，不能当作独立样本外结果。最大回撤是日线收盘口径，不能代表最差日内损失。默认99%止损不是账户风险上限；CycleRisk的25/35%减仓阈值也不保证最大回撤不超过35%。CycleRisk重启状态尚未完整持久化。未运行专门前视偏差分析。', '', '本次检查：所有20个窗口各有两个策略及持有基准，交易仅限指定标的，各策略起止日一致；现金账本与引擎余额误差均小于0.05 USDT；CycleRisk风控前日权益逐日核对。保存逐日权益、原始成交、风险轨迹、数据审计和策略代码哈希。']
(root/'REPORT.md').write_text('\n'.join(text)+'\n')
with (root/'trade_counts.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(counts[0]));w.writeheader();w.writerows(counts)
(root/'verification.json').write_text(json.dumps(dict(windows=len(windows),strategy_runs=len(counts),max_ledger_error=max(abs(float(r['ledger_error'])) for r in rows if r['ledger_error']),one_coin_only=True,matching_dates=True),indent=2))
print((root/'REPORT.md').read_text())
