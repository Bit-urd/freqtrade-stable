"""旧继承链与正式单文件的离线行为一致性检查。"""
import sys,os,ast,importlib,json,unittest,datetime
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
import pandas as pd
from freqtrade.persistence import Trade
ARCHIVE=Path('/freqtrade/user_data/archive/cycle_risk_flatten_20261007/strategies');ACTIVE=Path('/freqtrade/user_data/strategies')
sys.path.insert(0,str(ARCHIVE));Old=importlib.import_module('cycle_risk_strategy').BtcCoinGuardCycleRiskStrategy
old_modules={n:sys.modules.pop(n) for n in ['cycle_risk_strategy','equity_risk_strategy','btc_trend_coin_guard_strategy','ma200_btc_regime_full_cycle_core_hold_strategy']}
sys.path.remove(str(ARCHIVE));sys.path.insert(0,str(ACTIVE));New=importlib.import_module('cycle_risk_strategy').BtcCoinGuardCycleRiskStrategy
NOW=datetime.datetime(2025,1,10,tzinfo=datetime.timezone.utc)
class Rules(unittest.TestCase):
 def make(self,cls):return cls({'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'fee':.001})
 def histories(self):
  dates=pd.date_range('2022-01-01',periods=800,tz='UTC');close=100*np.exp(np.arange(800)*.001+np.sin(np.arange(800)/13)*.2)
  coin=pd.DataFrame({'date':dates,'close':close,'volume':1.});btc=coin.copy();btc['close']=np.roll(close,7)
  weekly=coin.iloc[::7][['date','close']].copy();return {'SOL/USDT':coin,'BTC/USDT':btc,'weekly':weekly}
 def indicators(self,cls,h):
  s=self.make(cls);s._history=Mock(side_effect=lambda pair,tf:h['weekly'].copy() if tf=='1w' else h[pair].copy());return s.populate_indicators(h['SOL/USDT'].copy(),{'pair':'SOL/USDT'})
 def compare_signals(self,h):
  old=self.indicators(Old,h);new=self.indicators(New,h)
  columns=['ema20','ema50','own_candles','exposure_entry','exposure_exit','cooldown_btc_strict','coin_risk_on','coin_risk_off']
  pd.testing.assert_frame_equal(old[columns],new[columns])
  old=self.make(Old).populate_entry_trend(old,{});new=self.make(New).populate_entry_trend(new,{})
  pd.testing.assert_frame_equal(old[['enter_long','enter_tag']],new[['enter_long','enter_tag']])
 def test_all_decision_signals_match(self):self.compare_signals(self.histories())
 def test_missing_btc_days_match(self):
  h=self.histories();h['BTC/USDT']=h['BTC/USDT'].drop([200,350,351,352]);self.compare_signals(h)
 def test_future_append_does_not_change_prior_signals(self):
  h=self.histories();old=self.indicators(New,h);h2={k:v.copy() for k,v in h.items()};extra=pd.DataFrame({'date':[h['SOL/USDT'].date.iloc[-1]+pd.Timedelta(days=1)],'close':[1e9],'volume':[1.]})
  for pair in ['SOL/USDT','BTC/USDT']:h2[pair]=pd.concat([h2[pair],extra],ignore_index=True)
  newer=self.indicators(New,h2);pd.testing.assert_frame_equal(old,newer.iloc[:-1].reset_index(drop=True))
 def test_closed_row_excludes_current_and_future(self):
  for cls in [Old,New]:
   s=self.make(cls);s.dp=Mock();s.dp.get_analyzed_dataframe.return_value=(pd.DataFrame({'date':[pd.Timestamp(NOW)-pd.Timedelta(days=1),pd.Timestamp(NOW)],'close':[10,1000]}),None);self.assertEqual(s._last_closed_row('SOL/USDT',NOW)['close'],10)
 def test_exit_priority_and_missing_values_match(self):
  for row in [None,{}, {'exposure_exit':True,'coin_risk_off':True},{'exposure_exit':False,'coin_risk_off':True},{'exposure_exit':float('nan'),'coin_risk_off':float('nan')}]:
   values=[]
   for cls in [Old,New]:
    s=self.make(cls);s._last_closed_row=Mock(return_value=row);values.append(s.custom_exit('SOL/USDT',None,NOW,100,0))
   self.assertEqual(*values)
 def test_cooldown_boundaries_match(self):
  for row in [None,{}, {'cooldown_btc_strict':True},{'cooldown_btc_strict':False},{'cooldown_btc_strict':float('nan')}]:
   for days in [13,14,15]:
    t=Mock(close_date_utc=NOW-datetime.timedelta(days=days));values=[]
    with patch.object(Trade,'get_trades_proxy',return_value=[t]):
     for cls in [Old,New]:
      s=self.make(cls);s._last_closed_row=Mock(return_value=row);values.append(s.confirm_trade_entry('SOL/USDT',NOW))
    self.assertEqual(*values)
 def test_first_entry_without_history_matches(self):
  with patch.object(Trade,'get_trades_proxy',return_value=[]):
   for cls in [Old,New]:
    s=self.make(cls);s._last_closed_row=Mock(return_value={'cooldown_btc_strict':False});self.assertTrue(s.confirm_trade_entry('SOL/USDT',NOW))
 def test_entry_stake_and_pending_fraction_match(self):
  for fraction in [1.,.75,.5]:
   values=[]
   for cls in [Old,New]:
    s=self.make(cls);s._risk_fraction=fraction;s._pair_budget=Mock(return_value=500.);values.append((s.custom_stake_amount('SOL/USDT',NOW,100,500,1,1000,1,None,'long'),s._pending_initial_fraction))
   self.assertEqual(*values)
 def trade(self,stage=1.):
  t=Mock(pair='SOL/USDT',amount=10.,stake_amount=600.,fee_open=.001,realized_profit=0.,has_open_orders=False,open_date_utc=NOW-datetime.timedelta(days=1),entry_side='buy');store={} if stage is None else {'equity_risk_filled_fraction':stage};t.get_custom_data.side_effect=store.get;t.set_custom_data.side_effect=lambda k,v:store.__setitem__(k,v);return t,store
 def test_adjustments_and_guards_match(self):
  for desired,filled,pending,exit_signal in [(.5,1.,False,None),(1.,.5,False,None),(.75,.75,False,None),(.5,1.,True,None),(.5,1.,False,'trend_to_cash')]:
   values=[]
   for cls in [Old,New]:
    s=self.make(cls);s._risk_fraction=desired;s._pair_budget=Mock(return_value=1000.);s.custom_exit=Mock(return_value=exit_signal);t,store=self.trade(filled);t.has_open_orders=pending;values.append(s.adjust_trade_position(t,NOW,100,0,1,1000,100,100,0,0))
   self.assertEqual(*values)
 def test_stage_only_changes_after_fill(self):
  for cls in [Old,New]:
   s=self.make(cls);t,store=self.trade(.5);s.order_filled('SOL/USDT',t,Mock(ft_order_tag=s.ORDER_PREFIX+'0.75',ft_order_side='buy'),NOW);self.assertEqual(store[s.STAGE_KEY],.75)
 def test_daily_equity_and_rearm_transitions_match(self):
  for bull,previous,last in [(False,False,None),(True,False,None),(True,True,None),(True,False,NOW-datetime.timedelta(days=7))]:
   results=[]
   with patch.object(Trade,'get_trades_proxy',return_value=[]):
    for cls in [Old,New]:
     s=self.make(cls);s.wallets=Mock();s.wallets.get_free.return_value=600.;s.wallets.get_used.return_value=0.;s.wallets.get_starting_balance.return_value=1000.;s._risk_peak=1000.;s._previous_bull=previous;s._last_rearm_candle=last;s._btc_bull_confirmed=Mock(return_value=bull);s.bot_loop_start(NOW);s.bot_loop_start(NOW+datetime.timedelta(hours=1));results.append((s._risk_fraction,s._risk_peak,s.risk_trace))
   self.assertEqual(*results)
 def test_btc_confirmation_is_causal_and_matches(self):
  h=self.histories()['BTC/USDT'];times=[pd.Timestamp('2022-04-01'),pd.Timestamp('2022-09-01'),pd.Timestamp('2023-09-01')]
  for time in times:
   values=[]
   for cls in [Old,New]:
    s=self.make(cls);s._history=Mock(return_value=h);values.append(s._btc_bull_confirmed(time.tz_localize('UTC')))
   self.assertEqual(*values)
 def test_framework_defaults_match(self):
  for name in ['timeframe','startup_candle_count','can_short','minimal_roi','stoploss','trailing_stop','use_exit_signal','exit_profit_only','process_only_new_candles','position_adjustment_enable','max_entry_position_adjustment','order_types','order_time_in_force']:self.assertEqual(getattr(Old,name),getattr(New,name),name)
 def test_formal_class_has_no_custom_strategy_parent(self):
  from freqtrade.strategy import IStrategy
  self.assertEqual(New.__bases__,(IStrategy,))
if __name__=='__main__':
 result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules));Path('/research/cycle_risk_flatten_verification/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n');sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
