# Historical runner: deleted trial sources must be restored from original result ZIPs before replay.
"""Freeze choices from requested range, then evaluate outside that range."""
import subprocess
from pathlib import Path

ROOT=Path('/research')
choices=['Ma200BtcRegimeFullCyclePortfolioStrategy',
         'Ma200BtcRegimeFullCycleCoreHoldStrategy',
         'CoreNoWeeklyTopUp','CoreUnifiedRestoreTopUp']
for label,timerange in [('stress','20210101-20221120'),('later','20251008-20261006')]:
    print('Validating',label,timerange,flush=True)
    subprocess.run(['python',str(ROOT/'run_improvements.py'),'--label',label,
                    '--timerange',timerange,'--strategies',*choices],check=True)
print('All validation backtests completed.',flush=True)
