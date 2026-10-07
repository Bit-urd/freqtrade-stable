"""Behavior checks for the Portfolio candidate, including fill-only state."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0, '/freqtrade/user_data/strategies')
sys.path.insert(0, '/research/archive/portfolio_improvement/strategies')
from ma200_btc_regime_full_cycle_portfolio_improved_strategy import BtcPortfolioImprovedStrategy

class Rules(unittest.TestCase):
    def setUp(self):
        self.s = object.__new__(BtcPortfolioImprovedStrategy)
        self.now = datetime(2025, 1, 10, tzinfo=timezone.utc)
        self.row = dict(btc_exit=False, own_weak_2d=True, weekly_bull=True,
                        btc_bull_2d=True, own_strong=False)
        self.s._last_closed_row = Mock(return_value=self.row)
        self.s._equity = Mock(return_value=1000)
        self.s._slots = Mock(return_value=1)
        self.data = {}
        self.t = SimpleNamespace(pair='ETH/USDT', enter_tag='bull_entry',
            has_open_orders=False, open_date_utc=self.now-timedelta(days=10),
            amount=10, stake_amount=800, fee_open=.001,
            entry_side='buy', exit_side='sell',
            get_custom_data=lambda key:self.data.get(key),
            set_custom_data=lambda key,value:self.data.update({key:value}))
    def adjust(self):
        return self.s.adjust_trade_position(self.t,self.now,100,0,10,1000,100,100,0,0)
    def exit(self):
        return self.s.custom_exit(self.t.pair,self.t,self.now,100,0)
    def test_daily_weak_weekly_strong_halves_and_does_not_exit(self):
        self.assertIsNone(self.exit())
        self.assertEqual(self.adjust(),(-400,self.s.DOWN_TAG))
        self.assertNotIn(self.s.EXPOSURE_KEY,self.data)
    def test_btc_break_exits_without_adjustment(self):
        self.row['btc_exit']=True
        self.assertEqual(self.exit(),'improved_btc_trend_lost')
        self.assertIsNone(self.adjust())
    def test_daily_and_weekly_weak_exit(self):
        self.row['weekly_bull']=False
        self.assertEqual(self.exit(),'improved_coin_daily_weekly_weak')
    def test_filled_reduce_is_not_repeated(self):
        self.s.order_filled(self.t.pair,self.t,SimpleNamespace(
            ft_order_tag=self.s.DOWN_TAG,ft_order_side='sell'),self.now)
        self.assertIsNone(self.adjust())
    def test_restore_requires_coin_confirmation(self):
        self.data[self.s.EXPOSURE_KEY]=.5;self.t.amount=5
        self.row.update(own_weak_2d=False,own_strong=False)
        self.assertIsNone(self.adjust())
        self.row['own_strong']=True
        amount,tag=self.adjust()
        self.assertAlmostEqual(amount,500/1.001)
        self.assertEqual(tag,self.s.UP_TAG)
        self.assertEqual(self.data[self.s.EXPOSURE_KEY],.5)
    def test_pending_orders_block_adjustment(self):
        self.t.has_open_orders=True
        self.assertIsNone(self.adjust())

if __name__ == '__main__': unittest.main()
