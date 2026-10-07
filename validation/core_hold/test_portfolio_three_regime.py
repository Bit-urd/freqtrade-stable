"""Verify cash defense and causal three-mode entry/exit behavior."""
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pandas as pd
sys.path.insert(0,'/research/portfolio_three_regime/strategies')
from portfolio_three_regime_strategy import BtcPortfolioThreeRegimeStrategy as Three, BtcPortfolioNoBearSwitchStrategy as NoBear
from portfolio_regime_switch_strategy import BtcPortfolioRegimeSwitchStrategy as Two
from ma200_btc_regime_full_cycle_portfolio_strategy import Ma200BtcRegimeFullCyclePortfolioStrategy as Original

class Rules(unittest.TestCase):
    def setUp(self):
        self.s=object.__new__(Three);self.now=datetime(2025,1,10,tzinfo=timezone.utc)
        self.row=dict(mode_down=False,mode_bull=False,mode_range=True,
            own_weak_2d=False,guard_coin_off=False)
        self.s._last_closed_row=Mock(return_value=self.row)
        self.data={};self.t=SimpleNamespace(pair='ETH/USDT',has_open_orders=False,
            open_date_utc=self.now-timedelta(days=10),get_custom_data=lambda k:self.data.get(k),
            set_custom_data=lambda k,v:self.data.update({k:v}))
    def exit(self):return self.s.custom_exit('ETH/USDT',self.t,self.now,100,0)
    def adjust(self):return self.s.adjust_trade_position(self.t,self.now,100,0,10,1000,100,100,0,0)
    def test_bear_accumulation_disabled_in_both_variants(self):
        self.assertFalse(Three.BEAR_ENABLED);self.assertFalse(NoBear.BEAR_ENABLED)
    def test_mode_definition_is_exclusive_and_unknown_data_is_inactive(self):
        frame=pd.DataFrame({'guard_btc_on':[True,True,False,False],
            'guard_btc_off':[False,False,True,False], 'hybrid_bull':[True,False,False,False],
            'close':[100]*4,'ema20':[90]*4,'ema50':[80]*4})
        with patch.object(Two,'populate_indicators',return_value=frame):
            result=self.s.populate_indicators(frame,{'pair':'ETH/USDT'})
        self.assertEqual(result[['mode_bull','mode_range','mode_down']].sum(axis=1).tolist(),[1,1,1,0])
    def test_downtrend_exits_and_never_adjusts(self):
        self.row.update(mode_range=False,mode_down=True)
        self.assertEqual(self.exit(),'hybrid_downtrend_cash');self.assertIsNone(self.adjust())
    def test_bull_ignores_range_alignment_loss_but_respects_coin_guard(self):
        self.row.update(mode_range=False,mode_bull=True,own_weak_2d=True)
        self.assertIsNone(self.exit())
        self.row['guard_coin_off']=True;self.assertEqual(self.exit(),'hybrid_bull_coin_weak')
    def test_range_alignment_loss_exits(self):
        self.row['own_weak_2d']=True;self.assertEqual(self.exit(),'hybrid_range_alignment_lost')
    def test_range_uses_original_weekly_adjustment(self):
        with patch.object(Original,'adjust_trade_position',return_value=-100) as call:
            self.assertEqual(self.adjust(),-100);call.assert_called_once()
    def test_downtrend_entry_is_zero_even_when_coin_is_strong(self):
        frame=pd.DataFrame({'own_candles':[300]*3,'volume':[1]*3,
            'mode_bull':[False,True,False],'mode_range':[False,False,True],
            'guard_coin_on':[True]*3,'range_alignment':[True]*3})
        out=self.s.populate_entry_trend(frame,{'pair':'ETH/USDT'})
        self.assertEqual(out.enter_long.tolist(),[0,1,1]);self.assertEqual(out.iloc[2].enter_tag,self.s.RANGE_TAG)

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
