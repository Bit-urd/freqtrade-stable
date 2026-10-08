import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent
rows=list(csv.DictReader((root/'all_comparisons.csv').open()));idx={r['window']:r for r in rows};attribution=list(csv.DictReader((root/'profit_attribution.csv').open()));annual=list(csv.DictReader((root/'continuous_annual.csv').open()));names=['BtcCoinGuardCycleRiskStrategy','BtcTwoDayExitCycleRiskStrategy','BuyAndHold']
text=['## 组合归因与连续年度表现','',
'以下逐币盈亏由实际成交及每日持仓价格重建，合计等于期末权益减初始资金。它描述既定组合中实际贡献，不能直接解释为单独持有该币的收益。','',
'### 十币连续组合：每个币实际贡献','', '|标的|原版盈亏 USDT|两天版盈亏 USDT|持有盈亏 USDT|两天版减原版 USDT|','|---|---:|---:|---:|---:|']
main=idx['Main10_full_cycle'];pairs=main['active_pairs'].split(',');aidx={(r['window'],r['strategy'],r['pair']):float(r['profit_abs']) for r in attribution}
legacy=idx['Legacy9_full_cycle'];total_delta=float(legacy['two_day_ending_equity'])-float(legacy['original_ending_equity']);sol_delta=aidx['Legacy9_full_cycle',names[1],'SOL/USDT']-aidx['Legacy9_full_cycle',names[0],'SOL/USDT']
legacy_text=['### 九币最长账户的改善来源','',f'两天版期末权益比原版增加 {total_delta:+.2f} USDT，其中 SOL 实际盈亏贡献变化 {sol_delta:+.2f} USDT，约占净改善 {sol_delta/total_delta*100:.2f}%。说明优势主要通过 SOL 持仓路径及复利实现，并非每个币都提高收益；这是既定组合真实贡献，账户风控也会参与其中。','','|标的|原版盈亏 USDT|两天版盈亏 USDT|变化 USDT|','|---|---:|---:|---:|']
for pair in legacy['active_pairs'].split(','):
 a=aidx['Legacy9_full_cycle',names[0],pair];b=aidx['Legacy9_full_cycle',names[1],pair];legacy_text.append(f"|{pair.split('/')[0]}|{a:+.2f}|{b:+.2f}|{b-a:+.2f}|")
text[4:4]=legacy_text+['']
for pair in pairs:
 vals=[aidx['Main10_full_cycle',name,pair] for name in names];text.append(f"|{pair.split('/')[0]}|{vals[0]:+.2f}|{vals[1]:+.2f}|{vals[2]:+.2f}|{vals[1]-vals[0]:+.2f}|")
text+=['','### 同一个十币连续账户的年度表现','',
'账户状态跨年继承，没有重新开户。年度收益分母是上年末权益；此表年度回撤以该年初权益及年内峰值计算，完整账户最大回撤仍看主表。首尾年份可能为部分年度。','',
'|年份|原版年度收益 / 年内回撤|两天版年度收益 / 年内回撤|持有年度收益 / 年内回撤|','|---|---:|---:|---:|']
records=[r for r in annual if r['window']=='Main10_full_cycle'];years=sorted({r['year'] for r in records});yi={(r['year'],r['strategy']):r for r in records}
for year in years:
 vals=[f"{float(yi[year,n]['return_pct']):+.2f}% / {float(yi[year,n]['drawdown_pct']):.2f}%" for n in names];text.append(f"|{year}|{'|'.join(vals)}|")
text+=['','### PUMP 在十一币组合中的贡献','', '|方法|PUMP实际盈亏 USDT|十一币合计盈亏 USDT|十币控制账户合计盈亏 USDT|','|---|---:|---:|---:|']
for n,p,label in zip(names,['original','two_day','hold'],['原版','两天退出','持有']):
 text.append(f"|{label}|{aidx['Mature11_full_cycle',n,'PUMP/USDT']:+.2f}|{float(idx['Mature11_full_cycle'][p+'_ending_equity'])-1000:+.2f}|{float(idx['Main10_mature11_control'][p+'_ending_equity'])-1000:+.2f}|")
text+=['','PUMP与其他币的预算、复利及账户风控存在交互，加入它的总收益差并不等于上表PUMP盈亏。HYPE策略尚不可测，不在贡献表中伪造交易。','']
if (root/'DECISION.md').exists():text += [(root/'DECISION.md').read_text(),'']
p=root/'REPORT.md';s=p.read_text().replace('## 验证与可复现文件','\n'.join(text)+'\n## 验证与可复现文件');p.write_text(s)
print('Added portfolio attribution and continuous annual results')
