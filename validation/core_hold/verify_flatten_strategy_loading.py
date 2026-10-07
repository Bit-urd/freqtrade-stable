"""验证活动入口及归档研究配置可以由Freqtrade解析。"""
import ast,json,os,sys,logging
from pathlib import Path
logging.disable(logging.CRITICAL)
from freqtrade.resolvers import StrategyResolver
from freqtrade.strategy import IStrategy
ROOT=Path('/freqtrade/user_data');ACTIVE=ROOT/'strategies';ARCH=ROOT/'archive/cycle_risk_flatten_20261007';loaded=[]
for p in sorted(ACTIVE.glob('*.py')):
 for node in ast.parse(p.read_text()).body:
  if not isinstance(node,ast.ClassDef):continue
  config={'strategy':node.name,'strategy_path':str(ACTIVE),'user_data_dir':ROOT,'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'exchange':{'name':'binance'}}
  strategy=StrategyResolver.load_strategy(config)
  if node.name=='BtcCoinGuardCycleRiskStrategy':assert strategy.__class__.__bases__==(IStrategy,)
  loaded.append({'strategy':node.name,'location':'active'})
for p in sorted((ARCH/'configs').glob('*.json')):
 data=json.loads(p.read_text());assert Path(data['strategy_path']).resolve()==ARCH/'strategies'
 config={'strategy':data['strategy'],'strategy_path':data['strategy_path'],'user_data_dir':ROOT,'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'exchange':{'name':'binance'}}
 strategy=StrategyResolver.load_strategy(config);assert strategy.__class__.__name__==data['strategy'];loaded.append({'strategy':data['strategy'],'config':p.name,'location':'archive'})
report={'passed':True,'active_python_files':4,'archive_configs_loaded':4,'loaded':loaded};Path('/research/cycle_risk_flatten_verification/loading_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report));sys.stdout.flush();sys.stderr.flush();os._exit(0)
