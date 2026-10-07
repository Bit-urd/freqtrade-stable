"""Check archived hashes, active resolver imports and unchanged official rules."""
import ast,hashlib,importlib,importlib.util,json,os,sys,unittest
from pathlib import Path
ROOT=Path('/research');ACTIVE=Path('/freqtrade/user_data/strategies');ARCHIVE=Path('/freqtrade/user_data/archive/strategy_cleanup_20261007')
sys.path.insert(0,str(ACTIVE))
manifest=json.loads((ARCHIVE/'manifest.json').read_text())
for item in manifest['archived']:
    assert not (ACTIVE/item['file']).exists()
    assert hashlib.sha256((ARCHIVE/item['file']).read_bytes()).hexdigest()==item['sha256']
official=json.loads((ROOT/'archive/portfolio_cycle_risk_v2/OFFICIAL.json').read_text())
class StripDocstrings(ast.NodeTransformer):
    def visit(self,node):
        if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and ast.get_docstring(node,clean=False) is not None:
            node.body=node.body[1:]
        return super().visit(node)
def logic(path):
    return ast.dump(StripDocstrings().visit(ast.parse(path.read_text())),include_attributes=False)
for name in manifest['retained_files']:
    assert logic(ACTIVE/name)==logic(ARCHIVE/'before_chinese_comments'/name),name
for file,digest in official['files'].items():
    frozen=ROOT/'archive/portfolio_cycle_risk_v2'/file
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()==digest
    assert logic(ACTIVE/Path(file).name)==logic(frozen)
    assert hashlib.sha256((ACTIVE/Path(file).name).read_bytes()).hexdigest()==official['active_files_sha256'][Path(file).name]
importlib.import_module('cycle_risk_strategy')
from freqtrade.commands.arguments import Arguments
from freqtrade.commands.optimize_commands import setup_optimize_configuration
from freqtrade.enums import RunMode
from freqtrade.resolvers import StrategyResolver
args=Arguments(['backtesting','-c','/freqtrade/user_data/config_portfolio_btc_sol_eth.json','--strategy-path',str(ACTIVE),'--timerange','20240101-20241231']).get_parsed_arg()
config=setup_optimize_configuration(args,RunMode.BACKTEST)
names=['BtcCoinGuardCycleRiskStrategy','Ma200BtcRegimeFullCyclePortfolioStrategy','BtcTrendPhasedStrategy','BtcTrendFastExitStrategy','Ma200BtcRegimeFullCycleCoreHoldStrategy','Ma200EmaAlignmentWeeklySizedPortfolioStrategy','Ma200BtcRegimeFullCycleFastTestStrategy','Ma200BtcRegimeWeeklySizedPortfolioStrategy','BtcTrendCoinGuardStrategy']
for name in names:
    c=dict(config);c['strategy']=name;strategy=StrategyResolver.load_strategy(c)
    assert strategy.__class__.__name__==name
    assert Path(strategy.__file__).parent==ACTIVE
for file in Path('/freqtrade/user_data').glob('config*.json'):
    try:c=json.loads(file.read_text())
    except (ValueError,OSError):continue
    if c.get('strategy'):assert c['strategy'] in names,(file.name,c['strategy'])
from ma200_btc_regime_full_cycle_core_hold_strategy import Ma200BtcRegimeFullCycleCoreHoldStrategy as Core
assert Core.HANDOVER_TOP_UP is True and Core.BULL_WEEKLY_SIZING is False
assert Core.CORE_RESTORE_ON_RECOVERY is False and Core.HANDOVER_CORE_HOLD is False
suite=unittest.TestSuite()
for name in ['test_equity_risk','test_cycle_risk']:
    spec=importlib.util.spec_from_file_location('cleanup_'+name,ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
result=unittest.TextTestRunner().run(suite)
report={'passed':result.wasSuccessful(),'policy_tests':result.testsRun,'active_strategy_classes_loaded':names,'archived_source_hashes_match':True,'official_frozen_hashes_match':True,'official_active_logic_matches_frozen':True,'all_eight_files_comment_only_changes':True,'all_existing_config_strategy_names_resolve':True,'growth_alias_defaults_preserved':True}
(ARCHIVE/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True);sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
