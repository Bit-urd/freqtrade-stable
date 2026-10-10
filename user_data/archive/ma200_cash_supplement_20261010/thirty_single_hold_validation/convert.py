import hashlib
import json
from pathlib import Path
import pandas as pd

D=Path(__file__).resolve().parent
P=json.loads((D/'protocol.json').read_text())
records=[]
for asset in P['assets']:
    path=D/'raw'/(asset+'.json')
    raw=json.loads(path.read_text())
    frame=pd.DataFrame({'date':pd.to_datetime([r[0] for r in raw],unit='ms',utc=True),
                       **{key:[float(r[i]) for r in raw] for key,i in [('open',1),('high',2),('low',3),('close',4),('volume',5)]}})
    assert not frame.date.duplicated().any()
    assert frame.date.is_monotonic_increasing
    assert len(pd.date_range(frame.date.iloc[0],frame.date.iloc[-1],freq='D').difference(frame.date))==0
    assert (frame.close>0).all()
    assert frame.date.iloc[-1]>=pd.Timestamp('2026-10-06',tz='UTC')
    frame.to_feather(D/'data'/(asset+'_USDT-1d.feather'))
    weekly=frame.set_index('date').resample('W-MON',label='left',closed='left').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna().reset_index()
    weekly.to_feather(D/'data'/(asset+'_USDT-1w.feather'))
    # Reused trades require the exact same usable OHLCV history.
    for key,folder in P['reused_cases'].items():
        if key.split('/')[0]!=asset:continue
        oldpath=Path(folder.replace('/root/freqtrade-stable/validation/core_hold','/research')).parents[1]/'data'/(asset+'_USDT-1d.feather')
        old=pd.read_feather(oldpath)
        cut=pd.Timestamp('2026-10-07',tz='UTC')
        pd.testing.assert_frame_equal(frame[frame.date<cut].reset_index(drop=True),old[old.date<cut].reset_index(drop=True),check_dtype=False)
    records.append({'asset':asset,'rows':len(frame),'first':str(frame.date.iloc[0].date()),
                    'last':str(frame.date.iloc[-1].date()),'raw_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
(D/'data_manifest.json').write_text(json.dumps(records,indent=2))
print('30 daily histories frozen; no gaps; reused OHLCV verified.',flush=True)
