"""个币预算规则：因果损失序列、账户上限、成交后风险档位和恢复加仓。"""
import sys,unittest,json,os,datetime
from pathlib import Path
from unittest.mock import Mock,patch
import pandas as pd
sys.path.insert(0,'/research/cycle_risk_loss_budget_revision/strategies')
from loss_budget_strategy import BtcCoinGuardLossBudgetStrategy as A,BtcCoinGuardTrendRestoreBudgetStrategy as B
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base
from freqtrade.persistence import Trade
NOW=datetime.datetime(2023,1,10,tzinfo=datetime.timezone.utc)
class Rules(unittest.TestCase):
 def make(self,cls=A):
  s=cls({'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'fee':.001});s._pair_budget=Mock(return_value=1000.);s.custom_exit=Mock(return_value=None);s._last_closed_row=Mock(return_value={});return s
 def closed(self,profit,days):return Mock(close_profit_abs=profit,close_date_utc=NOW-datetime.timedelta(days=days))
 def trade(self,stage):
  t=Mock(pair='SOL/USDT',amount=5.,stake_amount=500.,fee_open=.001,realized_profit=0.,has_open_orders=False,open_date_utc=NOW-datetime.timedelta(days=1));t.get_custom_data.return_value=stage;return t
 def adjust(self,s,t):return s.adjust_trade_position(t,NOW,100.,0.,1.,1000.,100.,100.,0.,0.)
 def test_no_history_full_budget(self):
  with patch.object(Trade,'get_trades_proxy',return_value=[]):self.assertEqual(self.make()._coin_risk_fraction('SOL/USDT',NOW),1.)
 def test_loss_sequence_and_chronological_order(self):
  s=self.make()
  for history,expected in [([self.closed(-1,1)],.75),([self.closed(-1,3),self.closed(-1,1)],.5),([self.closed(1,1),self.closed(-1,2)],1.),([self.closed(1,3),self.closed(-1,1)],.75),([self.closed(0,1),self.closed(-1,2)],1.)]:
   with patch.object(Trade,'get_trades_proxy',return_value=history):self.assertEqual(s._coin_risk_fraction('SOL/USDT',NOW),expected)
 def test_future_and_missing_closed_dates_excluded(self):
  t=self.closed(-1,1);t.close_date_utc=None
  with patch.object(Trade,'get_trades_proxy',return_value=[t,self.closed(-1,-1)]):self.assertEqual(self.make()._loss_streak('SOL/USDT',NOW),0)
 def test_pair_filter_used(self):
  with patch.object(Trade,'get_trades_proxy',return_value=[]) as get:self.make()._loss_streak('ETH/USDT',NOW);get.assert_called_once_with(pair='ETH/USDT',is_open=False)
 def test_account_limit_dominates(self):
  s=self.make();s._risk_fraction=.5
  with patch.object(Trade,'get_trades_proxy',return_value=[self.closed(-1,1)]):self.assertEqual(s._coin_risk_fraction('SOL/USDT',NOW),.5)
 def test_trend_restore_does_not_override_account(self):
  s=self.make(B);s._risk_fraction=.75;s._last_closed_row.return_value={'coin_budget_recovered':True}
  with patch.object(Trade,'get_trades_proxy',return_value=[self.closed(-1,1),self.closed(-1,2)]):self.assertEqual(s._coin_risk_fraction('SOL/USDT',NOW),.75)
 def test_missing_recovery_keeps_loss_limit(self):
  s=self.make(B)
  with patch.object(Trade,'get_trades_proxy',return_value=[self.closed(-1,1)]):
   for row in [None,{}, {'coin_budget_recovered':float('nan')}]:s._last_closed_row.return_value=row;self.assertEqual(s._coin_risk_fraction('SOL/USDT',NOW),.75)
 def test_entry_records_effective_fraction_without_mutating_account(self):
  s=self.make();s._loss_streak=Mock(return_value=2)
  amount=s.custom_stake_amount('SOL/USDT',NOW,100.,1000.,1.,1000.,1.,None,'long');self.assertAlmostEqual(amount,500/1.001);self.assertEqual(s._pending_initial_fraction['SOL/USDT'],.5);self.assertEqual(s._risk_fraction,1.)
 def test_no_add_before_order_fill(self):
  s=self.make();s._loss_streak=Mock(return_value=2);t=self.trade(.5);self.assertIsNone(self.adjust(s,t));t.has_open_orders=True;s._loss_streak.return_value=0;self.assertIsNone(self.adjust(s,t))
 def test_recovery_add_uses_existing_risk_fill_tag(self):
  s=self.make();s._loss_streak=Mock(return_value=0);result=self.adjust(s,self.trade(.5));self.assertGreater(result[0],0);self.assertEqual(result[1],s.ORDER_PREFIX+'1.0')
 def test_loss_cut_uses_cost_basis_and_effective_stage(self):
  s=self.make();s._loss_streak=Mock(return_value=2);t=self.trade(1.);t.amount=10.;t.stake_amount=600.
  result=self.adjust(s,t);self.assertAlmostEqual(result[0],-180.18);self.assertEqual(result[1],s.ORDER_PREFIX+'0.5')
 def test_original_exit_priority(self):
  s=self.make();s.custom_exit.return_value='trend_to_cash';s._loss_streak=Mock(return_value=2);self.assertIsNone(self.adjust(s,self.trade(1.)))
 def test_causal_recovery_signal(self):
  frame=pd.DataFrame({'close':[11.,12.,13.],'ema20':[10.,11.,12.],'ema50':[9.,9.5,10.]})
  with patch.object(Base,'populate_indicators',autospec=True,side_effect=lambda obj,df,meta:df.copy()):
   old=self.make(B).populate_indicators(frame,{});new=self.make(B).populate_indicators(pd.concat([frame,pd.DataFrame({'close':[1.],'ema20':[2.],'ema50':[3.]})],ignore_index=True),{})
  self.assertEqual(old.coin_budget_recovered.tolist(),[False,True,True]);self.assertEqual(old.coin_budget_recovered.tolist(),new.coin_budget_recovered.iloc[:-1].tolist())
 def test_original_signals_and_fills_inherited(self):
  for cls in [A,B]:
   for name in ['populate_entry_trend','custom_exit','bot_loop_start','order_filled','next_fraction']:self.assertIs(getattr(cls,name),getattr(Base,name))
if __name__=='__main__':
 import test_equity_risk,test_cycle_risk
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
 result=unittest.TextTestRunner().run(suite);Path('/research/cycle_risk_loss_budget_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n');sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
