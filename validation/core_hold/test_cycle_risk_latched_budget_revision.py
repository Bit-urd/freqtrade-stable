"""确认恢复保持至该笔结束，不产生虚假的成交风险档位。"""
import sys,unittest,json,os,datetime
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,'/research/cycle_risk_latched_budget_revision/strategies')
from latched_budget_strategy import BtcCoinGuardLatchedBudgetStrategy as C
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base
import test_cycle_risk_loss_budget_revision as prior
NOW=prior.NOW
class Rules(unittest.TestCase):
 def make(self):
  s=C({'stake_currency':'USDT','max_open_trades':3,'dry_run':True,'fee':.001});s._last_closed_row=Mock(return_value={});s._loss_streak=Mock(return_value=2);return s
 def trade(self,initial=None):
  t=Mock(pair='SOL/USDT',entry_side='buy');store=dict(initial or {});t.get_custom_data.side_effect=store.get;t.set_custom_data.side_effect=lambda key,value:store.__setitem__(key,value);return t,store
 def test_loss_limit_before_recovery(self):
  t,store=self.trade();self.assertEqual(self.make()._trade_risk_fraction(t,NOW),.5);self.assertEqual(store,{})
 def test_recovery_is_latched_through_future_weakness(self):
  s=self.make();t,store=self.trade();s._last_closed_row.return_value={'coin_budget_recovered':True};self.assertEqual(s._trade_risk_fraction(t,NOW),1.);s._last_closed_row.return_value={'coin_budget_recovered':False};self.assertEqual(s._trade_risk_fraction(t,NOW+datetime.timedelta(days=1)),1.);self.assertTrue(store[s.RELEASE_KEY])
 def test_account_limit_still_controls_released_trade(self):
  s=self.make();s._risk_fraction=.5;t,store=self.trade({s.RELEASE_KEY:True});self.assertEqual(s._trade_risk_fraction(t,NOW),.5)
 def test_next_trade_does_not_inherit_previous_release(self):
  s=self.make();t,store=self.trade({s.RELEASE_KEY:True});self.assertEqual(s._trade_risk_fraction(t,NOW),1.);new,_=self.trade();self.assertEqual(s._trade_risk_fraction(new,NOW),.5)
 def test_trend_observation_does_not_change_filled_stage(self):
  s=self.make();s._last_closed_row.return_value={'coin_budget_recovered':True};t,store=self.trade({s.STAGE_KEY:.5});s._trade_risk_fraction(t,NOW);self.assertEqual(store[s.STAGE_KEY],.5)
 def test_actual_add_updates_stage_and_release(self):
  s=self.make();s._last_closed_row.return_value={'coin_budget_recovered':True};t,store=self.trade({s.STAGE_KEY:.5});o=Mock(ft_order_tag=s.ORDER_PREFIX+'1.0',ft_order_side='buy');s.order_filled('SOL/USDT',t,o,NOW);self.assertEqual(store[s.STAGE_KEY],1.);self.assertTrue(store[s.RELEASE_KEY])
 def test_confirmed_initial_entry_records_release(self):
  s=self.make();s._last_closed_row.return_value={'coin_budget_recovered':True};t,store=self.trade();s._pending_initial_fraction['SOL/USDT']=.75;o=Mock(ft_order_tag='',ft_order_side='buy');s.order_filled('SOL/USDT',t,o,NOW);self.assertEqual(store[s.STAGE_KEY],.75);self.assertTrue(store[s.RELEASE_KEY])
 def test_flag_can_be_reloaded_from_trade_storage(self):
  s=self.make();t,_=self.trade({s.RELEASE_KEY:True});self.assertEqual(s._trade_risk_fraction(t,NOW),1.);s._loss_streak.assert_not_called()
 def test_missing_trend_does_not_release(self):
  s=self.make()
  for row in [None,{}, {'coin_budget_recovered':float('nan')}]:
   s._last_closed_row.return_value=row;t,store=self.trade();self.assertEqual(s._trade_risk_fraction(t,NOW),.5);self.assertEqual(store,{})
if __name__=='__main__':
 import test_equity_risk,test_cycle_risk
 suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromTestCase(prior.Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
 result=unittest.TextTestRunner().run(suite);Path('/research/cycle_risk_latched_budget_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n');sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
