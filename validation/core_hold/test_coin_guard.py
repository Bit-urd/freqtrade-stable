"""Verify coin entry/exit gates, missing-data safety and indicator causality."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import pandas as pd
strategy_path = Path('/freqtrade/user_data/strategies')
if not (strategy_path/'ma200_btc_regime_full_cycle_core_hold_strategy.py').exists():
    strategy_path = Path('/freqtrade/user_data/archive/cycle_risk_flatten_20261007/strategies')
sys.path.insert(0, str(strategy_path))
from btc_trend_coin_guard_strategy import BtcTrendCoinGuardStrategy as Guard
from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendFastExitStrategy as Fast

class Rules(unittest.TestCase):
    def setUp(self):
        self.s=object.__new__(Guard)
        self.frame=pd.DataFrame({'date':pd.date_range('2020-01-01',periods=320,tz='UTC'),
            'close':[100+i*.1 for i in range(300)]+[130-i*2 for i in range(20)]})
        self.s._history=Mock(return_value=self.frame)
    def indicators(self):
        with patch.object(Fast,'populate_indicators',return_value=self.frame.copy()):
            return self.s.populate_indicators(self.frame.copy(),{'pair':'ETH/USDT'})
    def test_future_prices_do_not_change_earlier_signals(self):
        a=self.indicators()
        self.frame.loc[310:,'close']=10000
        b=self.indicators()
        pd.testing.assert_frame_equal(a.iloc[:310],b.iloc[:310])
    def test_coin_gate_requires_history_and_detects_decline(self):
        a=self.indicators()
        self.assertFalse(a.iloc[100].coin_risk_on)
        self.assertTrue(a.iloc[299].coin_risk_on)
        self.assertFalse(a.iloc[-1].coin_risk_on)
        self.assertTrue(a.iloc[-1].coin_risk_off)
    def test_coin_gate_cannot_create_a_btc_disallowed_entry(self):
        frame=pd.DataFrame({'enter_long':[1,1,0], 'coin_risk_on':[False,True,True]})
        with patch.object(Fast,'populate_entry_trend',return_value=frame):
            actual=self.s.populate_entry_trend(frame,{'pair':'ETH/USDT'})
        self.assertEqual(actual.enter_long.tolist(),[0,1,0])
    def test_missing_coin_signal_does_not_force_exit(self):
        self.s._last_closed_row=Mock(return_value={'coin_risk_off':float('nan')})
        with patch.object(Fast,'custom_exit',return_value=None):
            self.assertIsNone(self.s.custom_exit('ETH/USDT',Mock(),None,100,0))
    def test_btc_exit_and_coin_exit_both_work(self):
        self.s._last_closed_row=Mock(return_value={'coin_risk_off':True})
        with patch.object(Fast,'custom_exit',return_value='trend_to_cash'):
            self.assertEqual(self.s.custom_exit('ETH/USDT',Mock(),None,100,0),'trend_to_cash')
        with patch.object(Fast,'custom_exit',return_value=None):
            self.assertEqual(self.s.custom_exit('ETH/USDT',Mock(),None,100,0),'coin_trend_to_cash')

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Rules))
    sys.stdout.flush();sys.stderr.flush();os._exit(0 if result.wasSuccessful() else 1)
