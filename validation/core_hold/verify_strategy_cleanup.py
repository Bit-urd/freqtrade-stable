"""离线检查清理后的策略加载和已有核心/风险回归检查。"""
import ast,importlib,json,logging,os,sys,unittest
from pathlib import Path
logging.disable(logging.CRITICAL)
ROOT=Path('/freqtrade/user_data/strategies');sys.path.insert(0,str(ROOT))
modules={p.stem:importlib.import_module(p.stem) for p in ROOT.glob('*.py')}
for name,module in modules.items():assert Path(module.__file__).resolve()==(ROOT/(name+'.py')).resolve()
classes={n.name for p in ROOT.glob('*.py') for n in ast.parse(p.read_text()).body if isinstance(n,ast.ClassDef)}
assert 'BtcTrendFullCycleDefensiveStrategy' not in classes
import check_strategy,test_equity_risk,test_cycle_risk
assert Path(test_cycle_risk.Cycle.__module__.replace('.','/')).name=='cycle_risk_strategy'
assert Path(sys.modules['cycle_risk_strategy'].__file__).resolve()==ROOT/'cycle_risk_strategy.py'
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in [check_strategy,test_equity_risk,test_cycle_risk])
result=unittest.TextTestRunner().run(suite);assert result.wasSuccessful()
from freqtrade.resolvers import StrategyResolver
loaded=[]
for name in sorted(classes):
 config={'strategy':name,'strategy_path':str(ROOT),'user_data_dir':ROOT.parent,'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'exchange':{'name':'binance'}}
 strategy=StrategyResolver.load_strategy(config);assert strategy.__class__.__name__==name;loaded.append(name)
configured=[]
for p in ROOT.parent.glob('*.json'):
 try:config=json.loads(p.read_text())
 except (ValueError,OSError):continue
 name=config.get('strategy')
 if name:assert name in classes,(p.name,name);configured.append({'file':p.name,'strategy':name})
report={'passed':True,'tests_run':result.testsRun,'loaded_strategy_classes':loaded,'active_config_references_resolve':configured,'live_service_restarted':False}
Path('/research/strategy_cleanup_20261007_second/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));sys.stdout.flush();sys.stderr.flush();os._exit(0)
