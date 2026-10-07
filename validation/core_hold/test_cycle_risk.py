"""Check causal BTC rearm, transition-only resets and reset cooldown."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
import pandas as pd
sys.path.insert(0,'/research/archive/portfolio_cycle_risk_v2/strategies')
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Cycle
from equity_risk_strategy import BtcCoinGuardEquityRiskStrategy as Parent

class Rules(unittest.TestCase):
    def setUp(self):
        self.s=object.__new__(Cycle);self.now=datetime(2025,1,10,tzinfo=timezone.utc)
        self.s._risk_candle=None;self.s._risk_fraction=.5;self.s._risk_peak=1000
        self.s._previous_bull=False;self.s._last_rearm_candle=None;self.s.risk_trace=[]
        self.s._btc_bull_confirmed=Mock(return_value=True)
    def update_parent(self,strategy,current_time,**kwargs):
        strategy._risk_candle=strategy._executing_candle_start(current_time)
        strategy.risk_trace.append({'prior_closed_equity':600,'peak':1000,'drawdown':.4,'risk_fraction':strategy._risk_fraction})
    def run_loop(self, now=None):
        with patch.object(Parent,'bot_loop_start',lambda strategy,current_time,**kw:self.update_parent(strategy,current_time,**kw)):
            self.s.bot_loop_start(now or self.now)
    def test_new_confirmed_bull_rearms_using_past_equity(self):
        self.run_loop();self.assertEqual(self.s._risk_fraction,1)
        self.assertEqual(self.s._risk_peak,600);self.assertTrue(self.s.risk_trace[-1]['risk_epoch_reset'])
    def test_existing_bull_does_not_repeatedly_reset(self):
        self.s._previous_bull=True;self.run_loop()
        self.assertEqual(self.s._risk_fraction,.5);self.assertFalse(self.s.risk_trace[-1]['risk_epoch_reset'])
    def test_reset_requires_fourteen_day_spacing(self):
        self.s._last_rearm_candle=self.now-timedelta(days=7);self.run_loop()
        self.assertEqual(self.s._risk_fraction,.5)
    def test_bear_never_rearms(self):
        self.s._btc_bull_confirmed.return_value=False;self.run_loop()
        self.assertEqual(self.s._risk_fraction,.5)
    def test_full_risk_does_not_reset_peak(self):
        self.s._risk_fraction=1;self.run_loop();self.assertEqual(self.s._risk_peak,1000)
        self.assertFalse(self.s.risk_trace[-1]['risk_epoch_reset'])
    def test_bull_confirmation_excludes_current_unclosed_price(self):
        dates=pd.date_range(end=self.now,periods=203,freq='D')
        frame=pd.DataFrame({'date':dates,'close':[100]*200+[90,110,999]})
        self.s._history=Mock(return_value=frame)
        self.assertFalse(Cycle._btc_bull_confirmed(self.s,self.now))
        frame.loc[200,'close']=110
        self.assertTrue(Cycle._btc_bull_confirmed(self.s,self.now))

    def test_same_day_has_no_second_update(self):
        self.run_loop();self.run_loop(self.now+timedelta(hours=1))
        self.assertEqual(len(self.s.risk_trace),1)

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
