import copy,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'strategies'))
from short_cooldown_strategy import ShortCooldownCycleRiskStrategy as Candidate
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Original
config=json.loads((root/'config.json').read_text());now=datetime(2025,6,1,tzinfo=timezone.utc);checks=[]
for cls,days in [(Original,14),(Candidate,7)]:
 s=cls(copy.deepcopy(config));s._last_closed_row=lambda *args:pd.Series({'cooldown_btc_strict':False})
 for elapsed,want in [(days*86400-1,False),(days*86400,True),(days*86400+1,True)]:
  trade=SimpleNamespace(close_date_utc=now-timedelta(seconds=elapsed))
  with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[trade]):assert s.confirm_trade_entry('SOL/USDT',now)==want
  checks.append(f'{cls.__name__}:boundary:{elapsed}')
 s._last_closed_row=lambda *args:pd.Series({'cooldown_btc_strict':True})
 with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[SimpleNamespace(close_date_utc=now)]):assert s.confirm_trade_entry('SOL/USDT',now)
 checks.append(cls.__name__+':strict_btc_bypass')
 s._last_closed_row=lambda *args:pd.Series({'cooldown_btc_strict':False})
 with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[]):assert s.confirm_trade_entry('SOL/USDT',now)
 checks.append(cls.__name__+':no_closed_trade')
for method in ['populate_indicators','custom_exit','confirm_trade_entry','custom_stake_amount','adjust_trade_position','order_filled','bot_loop_start','_pair_budget','next_fraction']:
 assert getattr(Candidate,method) is getattr(Original,method);checks.append('inherited:'+method)
assert Candidate.TREND_EXIT_DAYS==1 and Candidate.RECOVERY_COOLDOWN_DAYS==7
(root/'verification.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks),indent=2)+'\n');print('Passed',len(checks),'checks')
