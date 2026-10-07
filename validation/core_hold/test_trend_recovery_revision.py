"""验证冷却事件保留、撤销、单次执行，以及 BTC 退出优先级。"""
import sys,unittest,json,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import Mock,patch
sys.path.insert(0,'/research/trend_recovery_revision/strategies')
from recovery_refinement_strategy import BtcCoinGuardPendingRecoveryStrategy as P,BtcCoinGuardConfirmedCoinExitStrategy as C
from trend_aware_risk_strategy import BtcCoinGuardTrendRecoveryRiskStrategy as B

class Rules(unittest.TestCase):
    def make(self,cls):
        s=cls({'stake_currency':'USDT','max_open_trades':1,'dry_run':True})
        s._executing_candle_start=lambda t:t;s._risk_fraction=.5
        s._last_rearm_candle=datetime(2024,1,1,tzinfo=timezone.utc)
        return s
    def run_day(self,s,day,support):
        def parent(obj,t,**kw):
            obj._risk_candle=t;obj._long_trend_supported=support
            obj._previous_long_support=support
            obj.risk_trace.append({'prior_closed_equity':800,'execution_date':str(t)})
        with patch.object(B,'bot_loop_start',parent):s.bot_loop_start(day)
    def test_pending_waits_until_cooldown_then_executes_once(self):
        s=self.make(P);d=s._last_rearm_candle
        self.run_day(s,d+timedelta(days=5),True)
        self.assertTrue(s._pending_long_rearm);self.assertEqual(s._risk_fraction,.5)
        self.run_day(s,d+timedelta(days=13),True);self.assertEqual(s._risk_fraction,.5)
        self.run_day(s,d+timedelta(days=14),True);self.assertEqual(s._risk_fraction,1)
        self.assertEqual(s._risk_peak,800);self.assertFalse(s._pending_long_rearm)
        s._risk_fraction=.75
        self.run_day(s,d+timedelta(days=30),True);self.assertEqual(s._risk_fraction,.75)
    def test_failed_trend_cancels_pending(self):
        s=self.make(P);d=s._last_rearm_candle
        self.run_day(s,d+timedelta(days=5),True)
        self.run_day(s,d+timedelta(days=6),False);self.assertFalse(s._pending_long_rearm)
        self.run_day(s,d+timedelta(days=14),False);self.assertEqual(s._risk_fraction,.5)
    def test_same_candle_no_duplicate_execution(self):
        s=self.make(P);d=s._last_rearm_candle+timedelta(days=20)
        self.run_day(s,d,True);n=len(s.risk_trace)
        self.run_day(s,d,True);self.assertEqual(len(s.risk_trace),n)
    def test_btc_exit_not_delayed(self):
        s=self.make(C);s._last_closed_row=Mock(return_value={'coin_medium_weak':False})
        with patch.object(B,'custom_exit',return_value='trend_to_cash'):
            self.assertEqual(s.custom_exit('SOL/USDT',None,None,1,0),'trend_to_cash')
    def test_coin_exit_requires_medium_weak_and_missing_is_defensive(self):
        s=self.make(C)
        with patch.object(B,'custom_exit',return_value='coin_trend_to_cash'):
            for row,expected in [({'coin_medium_weak':False},None),({'coin_medium_weak':True},'coin_trend_to_cash'),({},'coin_trend_to_cash')]:
                s._last_closed_row=Mock(return_value=row)
                self.assertEqual(s.custom_exit('SOL/USDT',None,None,1,0),expected)

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    Path('/research/trend_recovery_revision/rule_checks.json').write_text(json.dumps({'passed':result.wasSuccessful(),'tests_run':result.testsRun},indent=2)+'\n')
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
