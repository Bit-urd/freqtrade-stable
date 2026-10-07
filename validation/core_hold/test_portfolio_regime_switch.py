"""Check causal mode selection, original-policy fallback and fill-only top-ups."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pandas as pd
sys.path.insert(0,'/research/portfolio_regime_switch/strategies')
from portfolio_regime_switch_strategy import BtcPortfolioRegimeSwitchStrategy as Hybrid
from ma200_btc_regime_full_cycle_portfolio_strategy import Ma200BtcRegimeFullCyclePortfolioStrategy as Original

class Rules(unittest.TestCase):
    def setUp(self):
        self.s=object.__new__(Hybrid);self.now=datetime(2025,1,10,tzinfo=timezone.utc)
        self.row=dict(hybrid_bull=True,guard_coin_on=True,guard_coin_off=False,guard_btc_off=False)
        self.s._last_closed_row=Mock(return_value=self.row)
        self.s._equity=Mock(return_value=1000);self.s._slots=Mock(return_value=1)
        self.data={};self.t=SimpleNamespace(pair='ETH/USDT',has_open_orders=False,
            open_date_utc=self.now-timedelta(days=10),amount=5,stake_amount=400,fee_open=.001,
            entry_side='buy',exit_side='sell',get_custom_data=lambda k:self.data.get(k),
            set_custom_data=lambda k,v:self.data.update({k:v}))
    def adjust(self):
        return self.s.adjust_trade_position(self.t,self.now,100,0,10,1000,100,100,0,0)
    def test_nonbull_uses_original_exit(self):
        self.row['hybrid_bull']=False
        with patch.object(Original,'custom_exit',return_value='original_exit') as call:
            self.assertEqual(self.s.custom_exit('ETH/USDT',self.t,self.now,100,0),'original_exit')
            call.assert_called_once()
    def test_bull_uses_guard_exit(self):
        with patch.object(Original,'custom_exit',return_value='original_exit') as call:
            self.assertIsNone(self.s.custom_exit('ETH/USDT',self.t,self.now,100,0))
            self.row['guard_coin_off']=True
            self.assertEqual(self.s.custom_exit('ETH/USDT',self.t,self.now,100,0),'hybrid_coin_to_cash')
            call.assert_not_called()
    def test_bull_topup_state_is_fill_only(self):
        amount,tag=self.adjust();self.assertAlmostEqual(amount,500/1.001)
        self.assertNotIn(self.s.GUARD_FILLED_KEY,self.data)
        self.s.order_filled('ETH/USDT',self.t,SimpleNamespace(ft_order_tag=tag,ft_order_side='buy'),self.now)
        self.assertIsNone(self.adjust())
    def test_nonbull_delegates_original_adjustment(self):
        self.row['hybrid_bull']=False;self.data[self.s.GUARD_FILLED_KEY]=True
        with patch.object(Original,'adjust_trade_position',return_value=-100) as call:
            self.assertEqual(self.adjust(),-100);call.assert_called_once()
        self.assertFalse(self.data[self.s.GUARD_FILLED_KEY])
    def test_guard_does_not_buy_coin_weakness(self):
        self.row['guard_coin_on']=False;self.assertIsNone(self.adjust())
        self.row.update(guard_coin_on=True,guard_coin_off=True);self.assertIsNone(self.adjust())
    def test_entry_switch_preserves_bear_entry_and_blocks_weak_coin(self):
        frame=pd.DataFrame({'enter_long':[1,1,1], 'enter_tag':['bear_accumulate']*3,
            'hybrid_bull':[False,True,True], 'guard_btc_on':[True]*3,
            'guard_coin_on':[True,False,True], 'own_candles':[250]*3,'volume':[1]*3})
        with patch.object(Original,'populate_entry_trend',return_value=frame):
            result=self.s.populate_entry_trend(frame,{'pair':'ETH/USDT'})
        self.assertEqual(result.enter_long.tolist(),[1,0,1])
        self.assertEqual(result.iloc[0].enter_tag,'bear_accumulate')
        self.assertEqual(result.iloc[2].enter_tag,self.s.GUARD_TAG)
    def test_missing_regime_is_not_bull(self):
        self.assertFalse(self.s._flag({'hybrid_bull':float('nan')},'hybrid_bull'))

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
