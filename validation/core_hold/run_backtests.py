# Historical runner: deleted trial sources must be restored from original result ZIPs before replay.
"""Reproducible isolated backtests; never starts or changes a trading bot."""
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path('/research')
NAMES = ['Ma200BtcRegimeFullCyclePortfolioStrategy',
         'Ma200BtcRegimeFullCycleCoreHoldStrategy'] + [
    f'CoreHold_{mode}_{fraction}_{days}d'
    for mode in ('alignment', 'early') for fraction in (25, 50, 75) for days in (1, 2, 3)]

parser = argparse.ArgumentParser()
parser.add_argument('--windows', nargs='+', default=['train', 'bear', 'test'])
args = parser.parse_args()

for label, timerange in [('train', '20230101-20250101'),
                         ('bear', '20210101-20230101'),
                         ('test', '20250102-20261006')]:
    if label not in args.windows:
        continue
    names = NAMES
    if label != 'train':
        selection = json.loads((ROOT/'selection.json').read_text())
        names = list(dict.fromkeys(NAMES[:2] + [selection['best_training_return'],
                                               selection['training_return_minus_2dd']]))
    output = ROOT / 'results' / label
    output.mkdir(parents=True, exist_ok=True)
    cmd = ['freqtrade', 'backtesting', '-c', str(ROOT/'config.json'),
           '--strategy-path', str(ROOT/'strategies'),
           '--timerange', timerange, '--fee', '0.001', '--cache', 'none',
           '--export', 'trades', '--backtest-directory', str(output),
           '--strategy-list', *names]
    print(f'Starting {label}: {timerange}', flush=True)
    with (output/'run.log').open('w') as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
    print(f'Completed {label}', flush=True)
    if label == 'train':
        subprocess.run(['python', str(ROOT/'analyze.py'), '--windows', 'train'], check=True)
