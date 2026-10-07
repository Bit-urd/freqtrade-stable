"""检查亏损冷却、边界、历史持仓和既有风控不变。"""
import sys,unittest,json,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,'/research/cycle_risk_loss_cooldown_revision/strategies')
from loss_cooldown_strategy import BtcCoinGuardLossCooldownStrategy as C,Trade
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base

class Rules(unittest.TestCase):
    now=datetime(2025,8,20,tzinfo=timezone.utc)
    def make(self,bull=False):
        s=C({'stake_currency':'USDT','max_open_trades':3,'dry_run':True});s._btc_bull_confirmed=Mock(return_value=bull);return s
    def trade(self,days,profit):return SimpleNamespace(close_date_utc=self.now-timedelta(days=days),close_profit_abs=profit)
    def entry(self,trades,bull=False,parent=True):
        s=self.make(bull)
        with patch.object(Base,'confirm_trade_entry',return_value=parent),patch.object(Trade,'get_trades_proxy',return_value=trades):return s.confirm_trade_entry(pair='SOL/USDT',current_time=self.now)
    def test_first_participation_preserved(self):self.assertTrue(self.entry([]))
    def test_confirmed_btc_bypasses_new_loss_gate(self):self.assertTrue(self.entry([self.trade(1,-50)],bull=True))
    def test_loss_waits_and_fourteen_day_boundary_allows(self):
        self.assertFalse(self.entry([self.trade(13,-50)]));self.assertTrue(self.entry([self.trade(14,-50)]))
    def test_winning_trade_does_not_add_cooldown(self):self.assertTrue(self.entry([self.trade(1,50)]))
    def test_parent_rejection_remains_rejection(self):self.assertFalse(self.entry([],bull=True,parent=False))
    def test_future_closed_trade_not_used(self):self.assertTrue(self.entry([self.trade(-1,-50)]))
    def test_latest_trade_controls_not_any_historical_loss(self):self.assertTrue(self.entry([self.trade(2,-50),self.trade(1,10)]))
    def test_exit_stake_risk_and_fill_methods_unchanged(self):
        for name in ['bot_loop_start','next_fraction','custom_exit','custom_stake_amount','adjust_trade_position','order_filled','populate_indicators','populate_entry_trend','_pair_budget']:self.assertIs(getattr(C,name),getattr(Base,name))

if __name__=='__main__':
    import test_equity_risk,test_cycle_risk
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
    result=unittest.TextTestRunner().run(suite)
    Path('/research/cycle_risk_loss_cooldown_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun,'new_loss_cooldown_checks':8,'existing_risk_checks':13},indent=2)+'\n')
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
