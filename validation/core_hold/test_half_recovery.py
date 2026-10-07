"""Verify staged cash defense, costs and directional constraints."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,'/research/portfolio_half_recovery_v2/strategies')
from portfolio_three_regime_strategy import BtcPortfolioHalfRecoveryStrategy as Half

class Rules(unittest.TestCase):
    def setUp(self):
        self.s=object.__new__(Half);self.s.config={'fee':.001};self.now=datetime(2025,1,10,tzinfo=timezone.utc)
        self.s._equity=Mock(return_value=1000);self.s._slots=Mock(return_value=1)
        self.row=dict(hybrid_bull=True,guard_btc_off=False,guard_coin_off=False)
        self.s._last_closed_row=Mock(return_value=self.row)
        self.data={};self.t=SimpleNamespace(pair='ETH/USDT',enter_tag=self.s.EARLY_TAG,
            has_open_orders=False,open_date_utc=self.now-timedelta(days=10),amount=5,
            stake_amount=400,fee_open=.001,entry_side='buy',exit_side='sell',
            get_custom_data=lambda k:self.data.get(k),set_custom_data=lambda k,v:self.data.update({k:v}))
    def adjust(self):return self.s.adjust_trade_position(self.t,self.now,100,0,10,1000,100,100,0,0)
    def test_early_entry_fee_in_half_budget(self):
        amount=self.s.custom_stake_amount('ETH/USDT',self.now,100,1000,10,1000,1,self.s.EARLY_TAG,'long')
        self.assertAlmostEqual(amount,500/1.001)
    def test_transition_full_does_not_sell_an_already_large_coin(self):
        self.t.amount=15;self.assertIsNone(self.adjust())
    def test_transition_half_does_not_buy_a_small_coin(self):
        self.t.enter_tag=self.s.GUARD_TAG;self.row['hybrid_bull']=False;self.t.amount=3
        self.assertIsNone(self.adjust())
    def test_reduce_market_value_uses_cost_basis_and_filled_state(self):
        self.t.enter_tag=self.s.GUARD_TAG;self.row['hybrid_bull']=False;self.t.amount=10;self.t.stake_amount=800
        amount,tag=self.adjust();self.assertEqual(amount,-400);self.assertNotIn(self.s.STAGE_KEY,self.data)
        self.s.order_filled('ETH/USDT',self.t,SimpleNamespace(ft_order_tag=tag,ft_order_side='sell'),self.now)
        self.assertEqual(self.data[self.s.STAGE_KEY],.5)
    def test_restore_state_changes_only_on_fill(self):
        amount,tag=self.adjust();self.assertAlmostEqual(amount,500/1.001)
        self.assertNotIn(self.s.STAGE_KEY,self.data)
        self.s.order_filled('ETH/USDT',self.t,SimpleNamespace(ft_order_tag=tag,ft_order_side='buy'),self.now)
        self.assertEqual(self.data[self.s.STAGE_KEY],1)
    def test_btc_or_coin_weak_exits_and_cannot_adjust(self):
        self.row['guard_btc_off']=True
        self.assertEqual(self.s.custom_exit('ETH/USDT',self.t,self.now,100,0),'half_recovery_to_cash')
        self.assertIsNone(self.adjust())

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
