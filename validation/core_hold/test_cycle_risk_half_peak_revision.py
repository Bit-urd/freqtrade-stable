"""检查峰值中点、日线去重、权益追踪和原有方法不变。"""
import sys,unittest,json,os
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
sys.path.insert(0,'/research/cycle_risk_half_peak_revision/strategies')
from half_peak_rearm_strategy import BtcCoinGuardHalfPeakRearmStrategy as C
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base

class Rules(unittest.TestCase):
    now=datetime(2025,8,20,tzinfo=timezone.utc)
    def make(self,peak=1000):
        s=C({'stake_currency':'USDT','max_open_trades':3,'dry_run':True});s._risk_peak=peak;s._executing_candle_start=lambda t:t;return s
    def day(self,s,equity=600,reset=True,execute=True):
        def parent(obj,current_time,**kwargs):
            if not execute:return
            obj._risk_candle=current_time;obj._risk_fraction=1.
            obj._risk_peak=equity if reset else max(obj._risk_peak or equity,equity)
            obj.risk_trace.append({'prior_closed_equity':equity,'peak':obj._risk_peak,'drawdown':0,'risk_epoch_reset':reset,'risk_fraction':1.})
        with patch.object(Base,'bot_loop_start',parent):s.bot_loop_start(self.now)
    def test_midpoint_preserves_half_peak_gap(self):
        s=self.make();self.day(s);self.assertEqual(s._risk_peak,800);self.assertEqual(s._risk_fraction,1.);self.assertEqual(s.risk_trace[-1]['drawdown'],.25)
        self.assertEqual(s.risk_trace[-1]['peak'],800);self.assertTrue(s.risk_trace[-1]['half_peak_rearm'])
    def test_no_reset_keeps_parent_behavior(self):
        s=self.make();self.day(s,reset=False);self.assertEqual(s._risk_peak,1000);self.assertNotIn('half_peak_rearm',s.risk_trace[-1])
    def test_same_candle_does_not_repeatedly_lower_peak(self):
        s=self.make();self.day(s);self.day(s);self.assertEqual(s._risk_peak,800);self.assertEqual(len(s.risk_trace),1)
    def test_peak_never_below_equity(self):
        s=self.make();self.day(s,equity=1100);self.assertEqual(s._risk_peak,1100);self.assertEqual(s.risk_trace[-1]['drawdown'],0)
    def test_missing_initial_peak_does_not_invent_prior_peak(self):
        s=self.make(None);self.day(s);self.assertEqual(s._risk_peak,600)
    def test_parent_missing_data_does_not_touch_trace(self):
        s=self.make();self.day(s,execute=False);self.assertEqual(s._risk_peak,1000);self.assertEqual(s.risk_trace,[])
    def test_entries_exits_budget_and_original_tiers_unchanged(self):
        for name in ['next_fraction','custom_exit','custom_stake_amount','adjust_trade_position','order_filled','populate_indicators','populate_entry_trend','_pair_budget','confirm_trade_entry']:self.assertIs(getattr(C,name),getattr(Base,name))

if __name__=='__main__':
    import test_equity_risk,test_cycle_risk
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Rules),unittest.defaultTestLoader.loadTestsFromModule(test_equity_risk),unittest.defaultTestLoader.loadTestsFromModule(test_cycle_risk)])
    result=unittest.TextTestRunner().run(suite)
    Path('/research/cycle_risk_half_peak_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun,'new_peak_checks':7,'existing_risk_checks':13},indent=2)+'\n')
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
