"""检查权重约束的成本换算、退出优先级和风险状态语义。"""
import sys,unittest,json,os,datetime
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,'/research/cycle_risk_weight_cap_revision/strategies')
from weight_cap_strategy import BtcCoinGuardAllocationCapStrategy as A,BtcCoinGuardPositionCapStrategy as B
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base
class Rules(unittest.TestCase):
 def make(self,cls):
  s=cls({'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'fee':.001});s.risk_trace=[{'prior_closed_equity':1000}];s.custom_exit=Mock(return_value=None);return s
 def trade(self):return Mock(amount=10.,stake_amount=200.,fee_open=.001,has_open_orders=False,open_date_utc=datetime.datetime(2020,1,1),pair='SOL/USDT')
 def adjust(self,s,t):return s.adjust_trade_position(t,datetime.datetime(2023,1,1),100.,0.,1.,1000.,100.,100.,0.,0.)
 def test_partial_exit_uses_cost_basis(self):
  with patch.object(Base,'adjust_trade_position',return_value=None):self.assertEqual(self.adjust(self.make(B),self.trade()),(-100.,'coin_weight_cap'))
 def test_allocation_cap_does_not_trim_winner(self):
  with patch.object(Base,'adjust_trade_position',return_value=None):self.assertIsNone(self.adjust(self.make(A),self.trade()))
 def test_pending_orders_and_same_day_entry(self):
  with patch.object(Base,'adjust_trade_position',return_value=None):
   t=self.trade();t.has_open_orders=True;self.assertIsNone(self.adjust(self.make(B),t));t.has_open_orders=False;t.open_date_utc=datetime.datetime(2023,1,1);self.assertIsNone(self.adjust(self.make(B),t))
 def test_original_exit_has_priority(self):
  s=self.make(B);s.custom_exit.return_value='trend_to_cash'
  with patch.object(Base,'adjust_trade_position',return_value=None):self.assertIsNone(self.adjust(s,self.trade()))
 def test_stronger_risk_reduction_retains_tag(self):
  with patch.object(Base,'adjust_trade_position',return_value=(-150.,'equity_risk_target_0.5')):self.assertEqual(self.adjust(self.make(B),self.trade()),(-150.,'equity_risk_target_0.5'))
 def test_positive_addition_is_capped_with_fee(self):
  t=self.trade();t.amount=4.
  with patch.object(Base,'adjust_trade_position',return_value=(300.,'equity_risk_target_1.0')):
   result=self.adjust(self.make(A),t);self.assertAlmostEqual(result[0],100/1.001);self.assertEqual(result[1],'equity_risk_target_1.0')
 def test_entry_limit_and_minimum(self):
  s=self.make(A)
  with patch.object(Base,'custom_stake_amount',return_value=700.):
   self.assertAlmostEqual(s.custom_stake_amount('SOL/USDT',None,1,700,1,1000,1,None,'long'),500/1.001)
   self.assertEqual(s.custom_stake_amount('SOL/USDT',None,1,700,600,1000,1,None,'long'),0)
 def test_existing_signals_and_risk_controller_inherited(self):
  for cls in [A,B]:
   for name in ['populate_indicators','populate_entry_trend','custom_exit','bot_loop_start','order_filled','next_fraction']:self.assertIs(getattr(cls,name),getattr(Base,name))
if __name__=='__main__':
 import test_equity_risk,test_cycle_risk
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
 result=unittest.TextTestRunner().run(suite);Path('/research/cycle_risk_weight_cap_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n');sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
