import json
import subprocess
import sys
from pathlib import Path

D=Path(__file__).resolve().parent
P=json.loads((D/'protocol.json').read_text())
newruns=0
for asset in P['execution_order']:
    for window in P['windows']:
        missing=[name for name in P['strategies'] if not (D/asset/'results'/window/(name+'_trades.json.gz')).exists()]
        if missing:
            subprocess.run([sys.executable,str(D/asset/'run.py'),window,*missing],check=True)
            newruns+=len(missing)
        for name in P['strategies']:
            assert (D/asset/'results'/window/(name+'_trades.json.gz')).exists()
        completed=sum((D/a/'results'/w/(n+'_trades.json.gz')).exists()
                      for a in P['assets'] for w in P['windows'] for n in P['strategies'])
        (D/'progress.json').write_text(json.dumps({'asset':asset,'window':window,'completed_native_cases':completed,
                                                  'new_runs_this_process':newruns,'requested_native_cases':120},indent=2))
        print('THIRTY COMPLETED',asset,window,completed,'/120',flush=True)
(D/'COMPLETED.json').write_text(json.dumps({'complete':True,'native_cases':120,'reused_cases':len(P['reused_cases']),
                                          'new_native_cases':120-len(P['reused_cases'])},indent=2))
print('ALL THIRTY NATIVE BACKTESTS COMPLETE',flush=True)
