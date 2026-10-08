import gzip,json
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parent
btc=pd.read_feather(root.parent/'independent_trend_optimization_20261008/data/BTC_USDT-1d.feather').set_index('date').close
strict=btc>btc.rolling(150).mean();count=0
for w in json.loads((root/'windows.json').read_text()):
 trades=json.load(gzip.open(root/'results'/w['label']/'ShortCooldownCycleRiskStrategy.json.gz','rt'))['trades']
 for t in trades:
  day=pd.Timestamp(t['open_date']);signal=day-pd.Timedelta(days=1)
  if strict.get(signal,False):continue
  earlier=[pd.Timestamp(x['close_date']) for x in trades if x['pair']==t['pair'] and x['exit_reason']!='force_exit' and pd.Timestamp(x['close_date'])<=day]
  if earlier:assert (day-max(earlier)).total_seconds()>=7*86400,(w['label'],t['pair'],day)
  count+=1
(root/'actual_entry_verification.json').write_text(json.dumps(dict(passed=True,weak_btc_entry_checks=count),indent=2)+'\n');print('Verified',count,'weak BTC entries')
