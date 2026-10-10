import csv
import hashlib
import json
import shutil
from pathlib import Path

D=Path(__file__).resolve().parent
P=json.loads((D/'protocol.json').read_text())
audit=json.loads((D/'audit.json').read_text())
summary=json.loads((D/'summary.json').read_text())
assert audit['all_passed'] and audit['native_curves_audited']==120
assert json.loads((D/'COMPLETED.json').read_text())['complete']
rows=list(csv.DictReader((D/'comparison.csv').open()))
assert len(rows)==60
for asset in P['assets']:
    assert {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (D/asset/'strategies').glob('*.py')}==P['source_sha256']
text=(D/'REPORT.md').read_text()
full=summary['full_history'];all_cases=summary['all']
text+='\n## 分析结论\n\n'
text+=f"完整预热历史的{full['cases']}个案例中，当前版相对原版收益领先{full['current_return_wins_vs_base']}个、落后{full['current_return_losses_vs_base']}个、相同{full['current_return_ties_vs_base']}个，收益差中位数{full['median_return_delta_pp']:+.2f}个百分点。不能用早期五币的结果直接认定本机制普遍提升收益。\n\n"
text+='2024起点的假反弹是重要反例。AVAX在2024-09-02开仓、2024-10-02退出的交易，原版以21.42买入8.41枚，25.82退出，利润约36.61U；当前版在2024-09-28又以30.44加买23.67枚，最终整笔亏约74.08U。LTC同一轮交易原版约亏1.01U，当前版因交接追加买入亏约96.71U。后续资金规模也被改变，不能把窗口总收益差等同于单笔补仓损益。详见counterexample_trade_diagnostics.json。\n\n'
text+='AAVE、SOL等案例的收益改善伴随更深回撤；AVAX、APT等存在收益和回撤同时恶化的情况。正利润保留比例及回撤恶化列表已经完整列出，不能仅按收益领先案例数判断合格。\n\n'
text+='更多标的并未改变这次实验的边界：没有外部充值。收益变化为零或没有额外闲置现金成交的案例，不能证明新资金会改善复利；新增工资资金的对照仍需固定相同充值日期与金额另行测试。\n'
(D/'REPORT.md').write_text(text)
A=D.parents[2]/'user_data/archive/ma200_cash_supplement_20261010/thirty_single_hold_validation'
A.mkdir(parents=True,exist_ok=True)
for name in ['REPORT.md','comparison.csv','summary.json','audit.json','data_manifest.json','protocol.json',
             'COMPLETED.json','counterexample_trade_diagnostics.json','report.py','convert.py','driver.py','finalize.py']:
    shutil.copy2(D/name,A/name)
(A/'VALIDATED.json').write_text(json.dumps({'requested_scope_complete':True,'assets':30,'start_years':[2024,2025],
    'native_strategy_cases':120,'new_native_cases':96,'reused_native_cases':24,'holding_cases':60,
    'all_native_curves_independently_audited':True,'source_sha256':P['source_sha256'],
    'deployed':False,'external_deposits':False,'raw_evidence_directory':str(D)},indent=2))
readme=A.parent/'README.md';s=readme.read_text()
if 'thirty_single_hold_validation/REPORT.md' not in s:
    readme.write_text(s+'\n30币单独运行、2024与2025起点的MA200原版/当前版/持有对照：[完整报告](thirty_single_hold_validation/REPORT.md)。120条策略净值核对通过，晚数据样本单列；无充值，未部署。\n')
print('30-asset study archived:',A)
