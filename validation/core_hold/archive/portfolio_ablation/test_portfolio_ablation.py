"""Check the two experiments preserve baseline exits and fill-only states."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, '/research/archive/portfolio_ablation/strategies')
from portfolio_ablation_strategy import BtcPortfolioRecoveryTopUpStrategy as TopUp, BtcPortfolioPullbackTrimStrategy as Trim
from ma200_btc_regime_full_cycle_portfolio_strategy import BEAR_TAG

class Rules(unittest.TestCase):
    def setup_strategy(self, cls):
        s=object.__new__(cls);s._equity=Mock(return_value=1000);s._slots=Mock(return_value=1)
        s._bull_seen_since_open=Mock(return_value=True)
        self.row=dict(bull_exit=True,btc_exit=False,weekly_bull=True)
        s._last_closed_row=Mock(return_value=self.row)
        self.data={};self.now=datetime(2025,1,10,tzinfo=timezone.utc)
        self.trade=SimpleNamespace(pair='ETH/USDT',enter_tag='bull_entry',has_open_orders=False,
            open_date_utc=self.now-timedelta(days=10),amount=10,stake_amount=800,fee_open=.001,
            entry_side='buy',exit_side='sell',get_custom_data=lambda k:self.data.get(k),
            set_custom_data=lambda k,v:self.data.update({k:v}))
        self.s=s
    def adjust(self):
        return self.s.adjust_trade_position(self.trade,self.now,100,0,10,1000,100,100,0,0)
    def test_topup_keeps_original_daily_exit(self):
        self.setup_strategy(TopUp)
        self.assertIsNotNone(self.s.custom_exit('ETH/USDT',self.trade,self.now,100,0))
    def test_topup_requires_strength_and_records_only_after_fill(self):
        self.setup_strategy(TopUp);self.row['bull_exit']=False;self.trade.enter_tag=BEAR_TAG;self.trade.amount=5
        self.s._strong=Mock(return_value=True)
        amount,tag=self.adjust();self.assertAlmostEqual(amount,500/1.001)
        self.assertNotIn(self.s.RESTORE_KEY,self.data)
        self.s.order_filled('ETH/USDT',self.trade,SimpleNamespace(ft_order_tag=tag,ft_order_side='buy'),self.now)
        self.assertTrue(self.data[self.s.RESTORE_KEY])
    def test_trim_half_is_fill_only_and_not_repeated(self):
        self.setup_strategy(Trim)
        self.assertIsNone(self.s.custom_exit('ETH/USDT',self.trade,self.now,100,0))
        amount,tag=self.adjust();self.assertEqual(amount,-400)
        self.assertNotIn(self.s.TRIM_KEY,self.data)
        self.s.order_filled('ETH/USDT',self.trade,SimpleNamespace(ft_order_tag=tag,ft_order_side='sell'),self.now)
        self.assertIsNone(self.adjust())
    def test_trim_does_not_override_btc_exit(self):
        self.setup_strategy(Trim);self.row['btc_exit']=True
        self.assertIsNotNone(self.s.custom_exit('ETH/USDT',self.trade,self.now,100,0))
    def test_trim_does_not_override_weekly_weak_exit(self):
        self.setup_strategy(Trim);self.row['weekly_bull']=False
        self.assertIsNotNone(self.s.custom_exit('ETH/USDT',self.trade,self.now,100,0))
    def test_trim_restore_requires_strong_signal(self):
        self.setup_strategy(Trim);self.row['bull_exit']=False;self.data[self.s.TRIM_KEY]=True;self.trade.amount=5
        with patch.object(TopUp,'_strong',return_value=False):self.assertIsNone(self.adjust())
        with patch.object(TopUp,'_strong',return_value=True):
            amount,tag=self.adjust();self.assertAlmostEqual(amount,500/1.001);self.assertEqual(tag,self.s.RESTORE_TAG)
        self.assertTrue(self.data[self.s.TRIM_KEY])

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
