"""Compare frozen strategies on requested three-pair market regimes."""
import argparse
import json
import subprocess
import time
from zipfile import ZipFile, BadZipFile
from pathlib import Path

ROOT=Path('/research');FOLDER=ROOT/'trend_cooldown'
WINDOWS=[
    {'label':'requested_long','title':'此前长上涨区间','timerange':'20221121-20251007'},
    {'label':'since_last_september','title':'去年9月至今','timerange':'20250901-20261006'},
    {'label':'bear_2022','title':'2022年下跌熊市','timerange':'20220101-20221121'},
    {'label':'bull_to_bear_2021','title':'2021年牛市转2022年熊市','timerange':'20210701-20221121'},
    {'label':'bull_2023_2024','title':'2023–2024年上涨周期','timerange':'20230101-20241231'},
]
NAMES=['BtcTrendRecoveryCooldownStrategy']
parser=argparse.ArgumentParser()
parser.add_argument("--phase", choices=["training", "validation"], default="validation")
parser.add_argument('--windows',nargs='+',default=[w['label'] for w in WINDOWS])
args=parser.parse_args()
FOLDER.mkdir(exist_ok=True)
config=json.loads((ROOT/'btc_sol_eth_20221121_20251007/config.json').read_text())
assert config['exchange']['pair_whitelist']==['BTC/USDT','SOL/USDT','ETH/USDT']
assert config['max_open_trades']==3
(FOLDER/'config.json').write_text(json.dumps(config,indent=2))
(FOLDER/'windows.json').write_text(json.dumps(WINDOWS,indent=2,ensure_ascii=False))
if any(FOLDER.glob('results/**/*.zip')):
    subprocess.run(['python',str(ROOT/'analyze_trend_cooldown.py'),'--available'],check=True)
for window in WINDOWS:
    if window['label'] not in args.windows:
        continue
    folder=FOLDER/'results'/window['label'];folder.mkdir(parents=True,exist_ok=True)
    cmd=['freqtrade','backtesting','-c',str(FOLDER/'config.json'),
         '--strategy-path',str(ROOT/'strategies'),'--timerange',window['timerange'],
         '--fee','0.001','--cache','none','--export','trades',
         '--backtest-directory',str(folder),'--strategy-list',*NAMES]
    (folder/'command.json').write_text(json.dumps(cmd,indent=2))
    print('Starting',window['label'],window['timerange'],flush=True)
    old_archives=set(folder.glob('*.zip'))
    shutdown_cleanup=False
    with (folder/'run.log').open('w') as log:
        process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
        exported_at=None
        while process.poll() is None:
            archives=sorted(set(folder.glob('*.zip'))-old_archives)
            valid=False
            if archives:
                try:
                    with ZipFile(archives[-1]) as archive:
                        name=next(n for n in archive.namelist() if n.endswith('.json')
                                  and not n.endswith('_config.json') and 'strategy' not in n)
                        payload=json.loads(archive.read(name))
                        valid=set(payload['strategy'])==set(NAMES) and archive.testzip() is None
                except (OSError,ValueError,KeyError,StopIteration,BadZipFile,EOFError):
                    pass
            if valid:
                if exported_at is None:
                    exported_at=time.monotonic()
                elif time.monotonic()-exported_at>30:
                    # Results are finished and verified. Avoid waiting indefinitely
                    # for exchange/library threads during process shutdown.
                    shutdown_cleanup=True
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill();process.wait()
                    break
            time.sleep(2)
        if process.returncode and not shutdown_cleanup:
            raise subprocess.CalledProcessError(process.returncode,cmd)
    (folder/'execution.json').write_text(json.dumps({
        'returncode':process.returncode,
        'completed_export_shutdown_cleanup':shutdown_cleanup,
    },indent=2))
    print('Completed',window['label'],flush=True)
    subprocess.run(['python',str(ROOT/'analyze_trend_cooldown.py'),'--available'],check=True)
