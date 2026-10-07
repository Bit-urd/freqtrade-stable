"""Causal timing and independent capital checks for the selected revision."""
import sys, unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pandas as pd
sys.path.insert(0, '/freqtrade/user_data/strategies')
import ma200_btc_regime_full_cycle_core_hold_strategy as module

class FastExitChecks(unittest.TestCase):
    def indicators(self, cls, history, frame=None):
        s=cls({'stake_currency':'USDT','max_open_trades':3})
        s._history=Mock(return_value=history)
        with patch.object(module.Ma200BtcRegimeFullCycleCoreHoldStrategy, 'populate_indicators', side_effect=lambda df, meta:df.copy()):
            return s.populate_indicators(history.copy() if frame is None else frame.copy(), {'pair':'BTC/USDT'})

    def history(self):
        return pd.DataFrame({'date':pd.date_range('2025-01-01',periods=200,tz='UTC'),'close':[100.]*190+[110.]*9+[50.]})

    def test_single_weak_day_exits_but_original_waits(self):
        h=self.history()
        new=self.indicators(module.BtcTrendFastExitStrategy,h)
        old=self.indicators(module.BtcTrendPhasedStrategy,h)
        self.assertFalse(bool(new.exposure_exit.iloc[-2]))
        self.assertTrue(bool(new.exposure_exit.iloc[-1]))
        self.assertFalse(bool(old.exposure_exit.iloc[-1]))

    def test_future_candles_do_not_change_past_signals(self):
        h=self.history();short=h.iloc[:-1].copy()
        a=self.indicators(module.BtcTrendFastExitStrategy,short)
        b=self.indicators(module.BtcTrendFastExitStrategy,h,short)
        for key in ['exposure_entry','exposure_exit','cooldown_btc_strict']:
            pd.testing.assert_series_equal(a[key],b[key])

    def test_exit_only_after_weak_candle_closes(self):
        s=module.BtcTrendFastExitStrategy({'stake_currency':'USDT'})
        dates=pd.date_range('2025-01-01',periods=2,tz='UTC')
        s.dp=Mock();s.dp.get_analyzed_dataframe.return_value=(pd.DataFrame({'date':dates,'exposure_exit':[False,True]}),None)
        self.assertIsNone(s.custom_exit('BTC/USDT',Mock(),dates[1].to_pydatetime(),1.,0.))
        self.assertEqual(s.custom_exit('BTC/USDT',Mock(),(dates[1]+timedelta(days=1)).to_pydatetime(),1.,0.),'trend_to_cash')

    def test_full_early_entry_still_reserves_other_coin_capital(self):
        s=module.BtcTrendFastExitStrategy({'stake_currency':'USDT','max_open_trades':3,'fee':.001})
        s.wallets=Mock();s.wallets.get_starting_balance.return_value=1000.
        with patch.object(module.Trade,'get_trades_proxy',return_value=[]):
            amount=s.custom_stake_amount('SOL/USDT',None,10.,1000.,1.,1000.,1.,'phase_reduced_entry','long')
        self.assertAlmostEqual(amount*1.001,1000./3)
        self.assertLessEqual(amount,1000./3)

if __name__=='__main__':unittest.main(verbosity=2)
