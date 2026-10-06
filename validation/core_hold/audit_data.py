import json
from pathlib import Path
import pandas as pd

root = Path('/research')
rows = []
for p in sorted(Path('/freqtrade/user_data/data/binance').glob('*.feather')):
    frame = pd.read_feather(p).sort_values('date')
    timeframe = p.stem.rsplit('-', 1)[1]
    step = pd.Timedelta(days=1 if timeframe == '1d' else 7)
    gaps = frame.loc[frame.date.diff() > step, 'date'].astype(str).tolist()
    rows.append({'file': p.name, 'rows': len(frame), 'first': str(frame.date.min()),
                 'last': str(frame.date.max()), 'duplicates': int(frame.date.duplicated().sum()),
                 'gaps': gaps, 'nonpositive_close': int((frame.close<=0).sum())})
(root/'data_manifest.json').write_text(json.dumps(rows, indent=2))
for row in rows:
    if '-1d.' in row['file']:
        print(row)
