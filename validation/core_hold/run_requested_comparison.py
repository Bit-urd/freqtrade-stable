"""Three-pair comparison for the requested 20221121-20251007 range."""
import json
import subprocess
from pathlib import Path

ROOT = Path('/research')
FOLDER = ROOT/'btc_sol_eth_20221121_20251007'
FOLDER.mkdir(exist_ok=True)
config = json.loads((FOLDER/'config.json').read_text())
cmd = ['freqtrade', 'backtesting', '-c', str(FOLDER/'config.json'),
       '--strategy-path', str(ROOT/'strategies'), '--timerange', '20221121-20251007',
       '--fee', '0.001', '--cache', 'none', '--export', 'trades',
       '--backtest-directory', str(FOLDER), '--strategy-list',
       'Ma200BtcRegimeFullCyclePortfolioStrategy',
       'Ma200BtcRegimeFullCycleCoreHoldStrategy']
(FOLDER/'command.json').write_text(json.dumps(cmd,indent=2))
print('Starting BTC/SOL/ETH comparison; 3 slots; 1000 USDT; fee 0.1% each way.', flush=True)
with (FOLDER/'run.log').open('w') as log:
    subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
print('Backtests completed.', flush=True)
subprocess.run(['python', str(ROOT/'analyze_requested_comparison.py')], check=True)
