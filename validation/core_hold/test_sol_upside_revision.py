"""检查趋势感知风控的因果性、确认期、广度与风险恢复。"""
import sys,unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock,patch
import pandas as pd
sys.path.insert(0,'/research/sol_upside_revision_v2/strategies')
from trend_aware_risk_strategy import BtcCoinGuardTrendAwareRiskStrategy as A, BtcCoinGuardTrendRecoveryRiskStrategy as B
from trend_priority_risk_strategy import BtcCoinGuardTrendPriorityRiskStrategy as C
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy as Base

class Rules(unittest.TestCase):
    def make(self,cls=A):
        s=cls({'stake_currency':'USDT','max_open_trades':1,'dry_run':True});s.dp=Mock();s.dp.current_whitelist.return_value=['SOL/USDT'];s._btc_bull_confirmed=Mock(return_value=True);return s
    def history(self):
        return pd.DataFrame({'date':pd.date_range('2024-01-01',periods=200,tz='UTC'),'close':list(range(100,300))})
    def test_strong_trend_defers_extra_cut_but_not_recovery(self):
        s=self.make();s._long_trend_supported=True
        self.assertEqual(s.next_fraction(1,.4),1);self.assertEqual(s.next_fraction(.75,.4),.75);self.assertEqual(s.next_fraction(.5,.1),1)
    def test_weak_trend_keeps_original_tiers(self):
        s=self.make();s._long_trend_supported=False
        self.assertEqual(s.next_fraction(1,.26),.75);self.assertEqual(s.next_fraction(1,.36),.5)
    def test_priority_restores_full_only_with_confirmed_support(self):
        s=self.make(C);s._long_trend_supported=True;self.assertEqual(s.next_fraction(.5,.4),1)
        s._long_trend_supported=False;self.assertEqual(s.next_fraction(1,.4),.5)
    def test_btc_weakness_blocks_long_support(self):
        s=self.make();s._btc_bull_confirmed.return_value=False;s._history=Mock(side_effect=AssertionError('must return before coin read'))
        self.assertFalse(s._closed_long_trend_supported(datetime(2024,8,1,tzinfo=timezone.utc)))
    def test_current_and_future_price_cannot_enable_support(self):
        s=self.make();h=self.history();now=h.date.iloc[-1].to_pydatetime()+timedelta(days=1)
        s._history=Mock(return_value=h);old=s._closed_long_trend_supported(now)
        s._history=Mock(return_value=pd.concat([h,pd.DataFrame({'date':[pd.Timestamp(now)],'close':[.001]})],ignore_index=True))
        self.assertEqual(old,s._closed_long_trend_supported(now));self.assertTrue(old)
    def test_two_of_three_coin_breadth(self):
        s=self.make();s.dp.current_whitelist.return_value=['BTC/USDT','ETH/USDT','SOL/USDT'];good=self.history();bad=good.copy();bad['close']=list(range(300,100,-1))
        s._history=Mock(side_effect=lambda p,t:bad if p=='ETH/USDT' else good)
        self.assertTrue(s._closed_long_trend_supported(datetime(2024,8,1,tzinfo=timezone.utc)))
        s._history=Mock(side_effect=lambda p,t:good if p=='BTC/USDT' else bad)
        self.assertFalse(s._closed_long_trend_supported(datetime(2024,8,1,tzinfo=timezone.utc)))
    def parent_loop(self,s,now,**kwargs):
        s._risk_candle=s._executing_candle_start(now);s.risk_trace.append({'prior_closed_equity':700.,'risk_fraction':s._risk_fraction})
    def test_support_needs_two_days_and_does_not_count_same_candle_twice(self):
        s=self.make();s._closed_long_trend_supported=Mock(return_value=True);now=datetime(2024,8,1,tzinfo=timezone.utc)
        with patch.object(Base,'bot_loop_start',lambda obj,current_time,**kw:self.parent_loop(obj,current_time)):
            s.bot_loop_start(now);self.assertFalse(s._long_trend_supported);s.bot_loop_start(now);self.assertEqual(s._support_days,1)
            s.bot_loop_start(now+timedelta(days=1));self.assertTrue(s._long_trend_supported)
    def test_recovery_reset_obeys_transition_and_cooldown(self):
        s=self.make(B);s._risk_fraction=.5;s._support_days=1;s._closed_long_trend_supported=Mock(return_value=True);now=datetime(2024,8,1,tzinfo=timezone.utc)
        with patch.object(Base,'bot_loop_start',lambda obj,current_time,**kw:self.parent_loop(obj,current_time)):
            s.bot_loop_start(now);self.assertEqual(s._risk_fraction,1);self.assertEqual(s._risk_peak,700)
            s._risk_fraction=.5;s.bot_loop_start(now+timedelta(days=1));self.assertEqual(s._risk_fraction,.5)
            s._previous_long_support=False;s.bot_loop_start(now+timedelta(days=2));self.assertEqual(s._risk_fraction,.5)
