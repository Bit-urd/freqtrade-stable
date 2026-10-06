# Historical runner: deleted trial sources must be restored from original result ZIPs before replay.
import argparse
import json
import subprocess
from pathlib import Path

ROOT=Path('/research')
FOLDER=ROOT/'improve_btc_sol_eth'
parser=argparse.ArgumentParser()
parser.add_argument('--label',default='requested')
parser.add_argument('--timerange',default='20221121-20251007')
parser.add_argument('--strategies',nargs='+',default=['PortfolioHandoverTopUp','CoreHandoverTopUp','Core75HandoverTopUp','Core75HandoverTopUpEarly'])
args=parser.parse_args()
config=json.loads((ROOT/'btc_sol_eth_20221121_20251007/config.json').read_text())
FOLDER.mkdir(exist_ok=True)
(FOLDER/'config.json').write_text(json.dumps(config,indent=2))
output=FOLDER/'results'/args.label;output.mkdir(parents=True,exist_ok=True)
cmd=['freqtrade','backtesting','-c',str(FOLDER/'config.json'),'--strategy-path',str(ROOT/'strategies'),
     '--timerange',args.timerange,'--fee','0.001','--cache','none','--export','trades',
     '--backtest-directory',str(output),'--strategy-list',*args.strategies]
(output/'command.json').write_text(json.dumps(cmd,indent=2))
print('Starting',args.label,args.timerange,args.strategies,flush=True)
with (output/'run.log').open('w') as log:
    subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
print('Completed',args.label,flush=True)
