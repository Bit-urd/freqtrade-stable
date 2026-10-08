import ast,copy,datetime,gzip,hashlib,json,os,sys
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.resolvers import StrategyResolver
from freqtrade.persistence import Trade
root=Path(__file__).resolve().parent
config=Configuration({'config':['/freqtrade/user_data/config_cycle_risk_futures_27.json']},RunMode.BACKTEST).get_config()
strategy=StrategyResolver.load_strategy(config)
assert type(strategy).__name__=='BtcCoinGuardCycleRiskFuturesStrategy'
assert strategy.TREND_EXIT_DAYS==2 and strategy.COIN_EXIT_DAYS==2 and strategy.leverage(None,None,None,None,None,None,None)==1
old_tree=ast.parse((root/'strategies/cycle_risk_strategy.py').read_text());new_tree=ast.parse(Path('/freqtrade/user_data/strategies/cycle_risk_futures_strategy.py').read_text())
def methods(tree):return {n.name:ast.dump(n,include_attributes=False) for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef)}
old=methods(old_tree);new=methods(new_tree)
for name,body in old.items():
 if name not in ['__init__','_update_equity_risk']:assert body==new[name],name
history={p.stem.split('-')[0].replace('_USDT_USDT','/USDT:USDT'):pd.read_feather(p) for p in (root/'data').glob('*-1d-futures.feather')}
sys.path.insert(0,str(root/'strategies'))
from btc_exit_confirmation_strategy import BtcTwoDayExitCycleRiskStrategy
candidate=BtcTwoDayExitCycleRiskStrategy(copy.deepcopy(config))
for s in [strategy,candidate]:s._history=lambda pair,tf:history[pair].copy()
for pair in config['exchange']['pair_whitelist']:
 pd.testing.assert_frame_equal(strategy.populate_indicators(history[pair].copy(),{'pair':pair}),candidate.populate_indicators(history[pair].copy(),{'pair':pair}))
price={p:h.set_index('date').close for p,h in history.items()};original_proxy=Trade.get_trades_proxy;checks=0;maxerror=0.
try:
 for label in ['Requested27','MON','AERO']:
  payload=json.load(gzip.open(root/'results'/label/'BtcTwoDayExitCycleRiskStrategy.json.gz','rt'));trades=[]
  for t in payload['trades']:
   orders=[]
   for o in t['orders']:
    if o['order_filled_timestamp'] is None:continue
    when=pd.to_datetime(o['order_filled_timestamp'],unit='ms',utc=True).to_pydatetime()
    orders.append(SimpleNamespace(ft_is_open=False,filled=o['amount'],order_filled_date=when,order_filled_utc=when,safe_amount_after_fee=o['amount'],safe_price=o['safe_price'],ft_order_side=o['ft_order_side']))
   trades.append(SimpleNamespace(pair=t['pair'],orders=orders,entry_side='buy',fee_open=t['fee_open'],fee_close=t['fee_close']))
  Trade.get_trades_proxy=staticmethod(lambda **kwargs:trades if kwargs.get('is_open') is True else [])
  strategy._closed_price=lambda p,when:float(price[p].loc[pd.Timestamp(when).floor('D')-pd.Timedelta(days=1)])
  for trace in json.loads((root/'results'/label/'risk_trace_BtcTwoDayExitCycleRiskStrategy.json').read_text()):
   computed=strategy._futures_equity(pd.Timestamp(trace['execution_date']));error=abs(computed-trace['prior_closed_equity']);assert error<1e-6,(label,error);checks+=1;maxerror=max(maxerror,error)
finally:Trade.get_trades_proxy=original_proxy
for mode in [RunMode.LIVE,RunMode.DRY_RUN]:
 c=copy.deepcopy(config);c['runmode']=mode
 try:type(strategy)(c)
 except ValueError:pass
 else:raise AssertionError('Unsupported live mode accepted')
manifest=json.loads(Path('/freqtrade/user_data/strategies/OFFICIAL.json').read_text());assert hashlib.sha256(Path('/freqtrade/user_data/strategies/cycle_risk_strategy.py').read_bytes()).hexdigest()==manifest['active_source_sha256']
result=dict(passed=True,strategy=type(strategy).__name__,indicators_matched_assets=27,replayed_daily_equity_checks=checks,max_equity_error=maxerror,trading_methods_unchanged=True,spot_official_source_unchanged=True,live_mode_rejected=True)
(root/'active_futures_migration_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);os._exit(0)
