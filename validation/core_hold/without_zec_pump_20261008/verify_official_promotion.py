import ast, copy, hashlib, importlib.util, json, os, sys
from pathlib import Path
import pandas as pd
from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.resolvers import StrategyResolver
root=Path('/research/without_zec_pump_20261008')
active=Path('/freqtrade/user_data/strategies/cycle_risk_strategy.py')
def normalized(path):
    tree=ast.parse(path.read_text())
    for node in ast.walk(tree):
        if hasattr(node,'body') and isinstance(node.body,list) and node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
            node.body.pop(0)
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TREND_EXIT_DAYS' for t in node.targets):node.value=ast.Constant(2)
    return ast.dump(tree,include_attributes=False)
assert normalized(active)==normalized(root/'strategies/cycle_risk_strategy.py')
sys.path.insert(0,str(root/'strategies'))
from btc_exit_confirmation_strategy import BtcTwoDayExitCycleRiskStrategy as Candidate
spec=importlib.util.spec_from_file_location('official_cycle_risk',active);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
Official=module.BtcCoinGuardCycleRiskStrategy
config=Configuration({'config':['/freqtrade/user_data/config_cycle_risk_nine_assets.json']},RunMode.BACKTEST).get_config()
resolved=StrategyResolver.load_strategy(config)
assert resolved.__class__.__name__=='BtcCoinGuardCycleRiskStrategy'
assert resolved.TREND_EXIT_DAYS==2 and resolved.COIN_EXIT_DAYS==2 and resolved.RECOVERY_COOLDOWN_DAYS==14
assert config['trading_mode']=='spot' and config['max_open_trades']==9 and config['dry_run'] is True
assert config['exchange']['pair_whitelist']==[a+'/USDT' for a in ['BTC','ETH','BNB','LINK','XRP','UNI','DOGE','SOL','ARB']]
history={p.stem.split('-')[0].replace('_','/'):pd.read_feather(p) for p in (root/'data').glob('*-1d.feather')}
for pair in config['exchange']['pair_whitelist']:
    baseline=Candidate(copy.deepcopy(config));formal=Official(copy.deepcopy(config))
    for strategy in [baseline,formal]:strategy._history=lambda p,tf:history[p].copy()
    left=baseline.populate_indicators(history[pair].copy(),{'pair':pair});right=formal.populate_indicators(history[pair].copy(),{'pair':pair})
    pd.testing.assert_frame_equal(left,right)
manifest=json.loads(Path('/freqtrade/user_data/strategies/OFFICIAL.json').read_text())
assert hashlib.sha256(active.read_bytes()).hexdigest()==manifest['active_source_sha256']
assert hashlib.sha256(Path('/freqtrade/user_data/config_cycle_risk_nine_assets.json').read_bytes()).hexdigest()==manifest['config_sha256']
result=dict(passed=True,checks=['AST identical to validated candidate except documented BTC exit constant','Freqtrade config and strategy resolve successfully','nine assets and nine budget slots; dry-run spot','indicator frame matches validated candidate for all nine assets','official manifest source and configuration hashes match'],running_service_changed=False)
(root/'official_promotion_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Official promotion verification passed',flush=True)
os._exit(0)
