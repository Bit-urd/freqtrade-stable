import copy,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root/'strategies'))
from limited_shared_cash_strategy import LimitedSharedCashCycleRiskStrategy as Candidate
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Original
pairs=['BTC/USDT','ETH/USDT','SOL/USDT'];config=json.loads((root/'config.json').read_text());checks=[]
now=datetime(2025,6,1,tzinfo=timezone.utc)
def build(eligible,risk=1):
 s=Candidate(copy.deepcopy(config));s.dp=SimpleNamespace(current_whitelist=lambda:pairs);s.wallets=SimpleNamespace(get_starting_balance=lambda:1000.);s._risk_fraction=risk
 s._last_closed_row=lambda p,t:pd.Series({'coin_risk_on':p in eligible,'exposure_entry':True,'cooldown_btc_strict':True,'volume':100.})
 return s
for eligible,risk,maxcash in [(set(pairs),1,1000),(set(),1,1000),({'ETH/USDT'},1,1000),(set(),.5,1000),(set(),1,100),(set(),1,5)]:
 s=build(eligible,risk)
 with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[]):
  amount=s.custom_stake_amount(pairs[0],now,100,100,10,maxcash,1,'','long')
 if s.budget_requests:
  r=s.budget_requests[-1];assert 0<=r['extra']<=.5*r['base']+1e-8;assert amount<=maxcash and amount<=1.5*r['base']+1e-8
  assert r['extra']<=.5*max(0,maxcash-r['reserved']-r['base']*1.001)/1.001+1e-8
  assert s._pending_initial_fraction[pairs[0]]==risk
 else:assert amount==0
 if eligible==set(pairs):assert abs(amount-1000/3/1.001)<1e-7
 checks.append(f'cash_reserve_cap_risk_minimum:{eligible}:{risk}:{maxcash}')
s=build(set())
s._last_closed_row=lambda *a:pd.Series({'coin_risk_on':pd.NA,'exposure_entry':pd.NA,'cooldown_btc_strict':False})
with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[]):assert s.custom_stake_amount(pairs[0],now,100,100,10,1000,1,'','long')>0
checks.append('missing_peer_signal_conservative_half_reserve')
for method in ['populate_indicators','custom_exit','confirm_trade_entry','adjust_trade_position','order_filled','bot_loop_start','_pair_budget','next_fraction']:
 assert getattr(Candidate,method) is getattr(Original,method);checks.append('inherited:'+method)
s=build(set())
del s.__dict__['_last_closed_row']
frame=pd.DataFrame({'date':pd.to_datetime([now-timedelta(days=1),now,now+timedelta(days=1)],utc=True),'coin_risk_on':[False,True,True],'exposure_entry':[True,True,True],'cooldown_btc_strict':[False,True,True],'volume':[100.,100.,100.]})
s.dp.get_analyzed_dataframe=lambda pair,timeframe:(frame.copy(),None)
with patch('cycle_risk_strategy.Trade.get_trades_proxy',return_value=[]):s.custom_stake_amount(pairs[0],now,100,100,10,1000,1,'','long')
assert abs(s.budget_requests[-1]['reserved']-1000/3)<1e-7
checks.append('peer_reservation_uses_last_completed_candle_only')
(root/'verification.json').write_text(json.dumps(dict(passed=True,count=len(checks),checks=checks),indent=2)+'\n');print('Passed',len(checks),'checks')
