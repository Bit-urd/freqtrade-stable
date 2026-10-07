"""Check hysteresis, closed-day caching, stage fills and cost accounting."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,'/research/archive/portfolio_equity_risk_v2/strategies')
from equity_risk_strategy import BtcCoinGuardEquityRiskStrategy as Risk

class Rules(unittest.TestCase):
    def setUp(self):
        self.s=object.__new__(Risk);self.s.config={'stake_currency':'USDT','fee':.001,'dry_run':True}
        self.s._risk_fraction=1.;self.s._risk_peak=None;self.s._risk_candle=None
        self.s._pending_initial_fraction={};self.s.risk_trace=[]
        self.now=datetime(2025,1,10,tzinfo=timezone.utc)
        self.s.wallets=Mock();self.s.wallets.get_free.return_value=200
        self.s.wallets.get_used.return_value=0;self.s.wallets.get_starting_balance.return_value=1000
        self.s._closed_price=Mock(return_value=2)
        self.s._pair_budget=Mock(return_value=1000);self.s.custom_exit=Mock(return_value=None)
        self.data={};self.t=SimpleNamespace(pair='ETH/USDT',has_open_orders=False,
            open_date_utc=self.now-timedelta(days=10),amount=400,stake_amount=800,
            fee_open=.001,realized_profit=0,entry_side='buy',exit_side='sell',
            get_custom_data=lambda k:self.data.get(k),set_custom_data=lambda k,v:self.data.update({k:v}))
    def adjust(self):return self.s.adjust_trade_position(self.t,self.now,2.5,0,10,1000,2.5,2.5,0,0)
    def test_hysteresis_and_recovery(self):
        self.assertEqual(Risk.next_fraction(1,.27),.75)
        self.assertEqual(Risk.next_fraction(1,.36),.5)
        self.assertEqual(Risk.next_fraction(.5,.32),.5)
        self.assertEqual(Risk.next_fraction(.5,.29),.75)
        self.assertEqual(Risk.next_fraction(.75,.22),.75)
        self.assertEqual(Risk.next_fraction(.75,.19),1)
    def test_closed_price_highwater_and_current_day_cache(self):
        with patch('equity_risk_strategy.Trade.get_trades_proxy',return_value=[self.t]):
            self.s.bot_loop_start(self.now)
            self.assertEqual(self.s._risk_peak,1000)
            self.s.wallets.get_free.return_value=1
            self.s.bot_loop_start(self.now+timedelta(hours=1))
            self.assertEqual(len(self.s.risk_trace),1)
            self.s.wallets.get_free.return_value=200
            self.s._closed_price.return_value=1
            self.s.bot_loop_start(self.now+timedelta(days=1))
        self.assertEqual(self.s._risk_fraction,.5)
        self.assertAlmostEqual(self.s.risk_trace[-1]['prior_closed_equity'],599.2)
    def test_entry_tracks_planned_risk_until_fill(self):
        self.s._risk_fraction=.75
        amount=self.s.custom_stake_amount('ETH/USDT',self.now,2.5,1000,10,1000,1,'phase_full_entry','long')
        self.assertAlmostEqual(amount,750/1.001)
        self.s._risk_fraction=.5
        self.s.order_filled('ETH/USDT',self.t,SimpleNamespace(ft_order_tag='phase_full_entry',ft_order_side='buy'),self.now)
        self.assertEqual(self.data[self.s.STAGE_KEY],.75)
    def test_trim_uses_market_fraction_cost_basis_and_filled_state(self):
        self.s._risk_fraction=.75
        amount,tag=self.adjust();self.assertAlmostEqual(amount,-80.48)
        self.assertNotIn(self.s.STAGE_KEY,self.data)
        self.s.order_filled('ETH/USDT',self.t,SimpleNamespace(ft_order_tag=tag,ft_order_side='sell'),self.now)
        self.assertEqual(self.data[self.s.STAGE_KEY],.75)
    def test_partial_profit_is_in_sleeve_cash_once(self):
        self.s._risk_fraction=.75;self.t.realized_profit=100
        amount,_=self.adjust();self.assertAlmostEqual(amount,-20.48)
    def test_exit_has_priority_over_adjustment(self):
        self.s._risk_fraction=.5;self.s.custom_exit.return_value='trend_to_cash'
        self.assertIsNone(self.adjust())

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
