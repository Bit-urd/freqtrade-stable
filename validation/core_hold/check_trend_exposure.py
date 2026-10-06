"""Meaningful causal-signal and cash-exit checks for trend exposure."""
import sys, unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from types import SimpleNamespace
import pandas as pd
sys.path.insert(0, '/research/strategies')
from ma200_btc_regime_full_cycle_core_hold_strategy import (
    Ma200BtcRegimeFullCycleCoreHoldStrategy as Core,
    BtcTrendFullCycleDefensiveStrategy as TrendExposure200,
    BtcTrendFullCycleStrategy as TrendExposure200Recovery,
    BtcTrendFullCycleStrategy as TrendSleeve150,
    BtcTrendRecoveryCooldownStrategy as Cooldown,
    BtcTrendPhasedStrategy as Phased,
)

class TrendChecks(unittest.TestCase):
    def setUp(self):
        self.s=TrendExposure200({'stake_currency':'USDT'})
        self.s.dp=Mock()
        self.now=datetime(2026,1,3,tzinfo=timezone.utc)
    def test_bear_stays_cash_and_bull_buys_all_three(self):
        df=pd.DataFrame({'own_candles':[300]*3,'volume':[1.]*3,'exposure_entry':[False,True,True], 'close':[2.]*3,'ema20':[3.]*3})
        for pair in ['BTC/USDT','SOL/USDT','ETH/USDT']:
            out=self.s.populate_entry_trend(df.copy(),{'pair':pair})
            self.assertTrue(pd.isna(out.loc[0,'enter_long']))
            self.assertEqual(out.loc[1,'enter_long'],1)
    def test_exit_reads_closed_day_and_fully_exits(self):
        df=pd.DataFrame({'date':pd.date_range('2026-01-01',periods=3,tz='UTC'),'exposure_exit':[False,True,False]})
        self.s.dp.get_analyzed_dataframe.return_value=(df,None)
        self.assertEqual(self.s.custom_exit('BTC/USDT',None,self.now,10.,0.),'trend_to_cash')
    def test_no_partial_core_or_bear_accumulation(self):
        self.assertFalse(self.s.BEAR_ENABLED)
        self.assertIsNone(self.s.adjust_trade_position())
    def test_bull_stake_respects_cash(self):
        self.s._equity=Mock(return_value=1200.)
        self.s._slots=Mock(return_value=3)
        stake=self.s.custom_stake_amount('SOL/USDT',self.now,10.,100.,1.,250.,1.,'trend_full_exposure','long')
        self.assertEqual(stake,250.)
    def test_indicator_prefix_does_not_change_with_future_prices(self):
        dates=pd.date_range('2024-01-01',periods=260,tz='UTC')
        daily=pd.DataFrame({'date':dates,'close':[100.]*200+[120.]*30+[80.]*30})
        # Parent indicators use only causal EMAs, rolling MA, and closed weekly merges.
        # Exercise the subclass additions separately with parent output stubbed.
        from unittest.mock import patch
        base=Core
        for cls in [TrendExposure200,TrendExposure200Recovery,Cooldown,Phased]:
            s=cls({'stake_currency':'USDT'}); s._history=Mock(return_value=daily)
            with patch.object(base,'populate_indicators',side_effect=lambda *args:args[-2]):
                full=s.populate_indicators(pd.DataFrame({'date':dates}),{})
                s._history=Mock(return_value=daily.iloc[:235])
                prefix=s.populate_indicators(pd.DataFrame({'date':dates[:235]}),{})
            pd.testing.assert_frame_equal(full.iloc[:235].reset_index(drop=True),prefix.reset_index(drop=True))

    def test_sleeve_does_not_transfer_other_coin_profits(self):
        from unittest.mock import patch
        s=TrendSleeve150({'stake_currency':'USDT','fee':.001,'max_open_trades':3})
        s.wallets=Mock(); s.wallets.get_starting_balance.return_value=1000.
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',return_value=[SimpleNamespace(close_profit_abs=300.)]) as trades:
            stake=s.custom_stake_amount('SOL/USDT',self.now,10.,100.,1.,1000.,1.,'x','long')
        self.assertAlmostEqual(stake,(1000./3+300.)/1.001)
        trades.assert_called_once_with(pair='SOL/USDT',is_open=False)
    def test_exhausted_sleeve_and_exchange_minimum(self):
        from unittest.mock import patch
        s=TrendSleeve150({'stake_currency':'USDT','max_open_trades':3})
        s.wallets=Mock(); s.wallets.get_starting_balance.return_value=1000.
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',return_value=[SimpleNamespace(close_profit_abs=-334.)]):
            self.assertEqual(s.custom_stake_amount('SOL/USDT',self.now,10.,100.,1.,1000.,1.,'x','long'),0.)
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',return_value=[]):
            self.assertEqual(s.custom_stake_amount('SOL/USDT',self.now,10.,100.,25.,20.,1.,'x','long'),0.)

    def test_public_profile_waits_for_sufficient_btc_history(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendFullCycleStrategy
        from unittest.mock import patch
        dates=pd.date_range('2024-01-01',periods=100,tz='UTC')
        daily=pd.DataFrame({'date':dates,'close':range(100,200)})
        s=BtcTrendFullCycleStrategy({'stake_currency':'USDT'});s._history=Mock(return_value=daily)
        with patch.object(Core,'populate_indicators',side_effect=lambda *args:args[-2]):
            out=s.populate_indicators(pd.DataFrame({'date':dates}),{})
        self.assertFalse(out.exposure_entry.any())

    def test_public_missing_btc_candle_does_not_force_exit(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendFullCycleStrategy
        s=BtcTrendFullCycleStrategy({'stake_currency':'USDT'})
        s._last_closed_row=Mock(return_value=pd.Series({'exposure_exit':float('nan')}))
        self.assertIsNone(s.custom_exit('BTC/USDT',None,self.now,10.,0.))

    def test_defensive_rejects_rebound_below_long_ma(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendFullCycleDefensiveStrategy
        from unittest.mock import patch
        dates=pd.date_range('2024-01-01',periods=230,tz='UTC')
        daily=pd.DataFrame({'date':dates,'close':[100.]*200+[70.]*20+list(range(71,81))})
        s=BtcTrendFullCycleDefensiveStrategy({'stake_currency':'USDT'});s._history=Mock(return_value=daily)
        with patch.object(Core,'populate_indicators',side_effect=lambda *args:args[-2]):
            out=s.populate_indicators(pd.DataFrame({'date':dates}),{})
        self.assertFalse(out.exposure_entry.iloc[-1])
        self.assertTrue(out.exposure_exit.iloc[-1])

    def test_cooldown_blocks_subtrend_rebound_before_fourteen_days(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendRecoveryCooldownStrategy
        from unittest.mock import patch
        from datetime import timedelta
        s=BtcTrendRecoveryCooldownStrategy({'stake_currency':'USDT'})
        s._last_closed_row=Mock(return_value=pd.Series({'cooldown_btc_strict':False}))
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',return_value=[SimpleNamespace(close_date_utc=self.now-timedelta(days=13,hours=23))]) as trades:
            self.assertFalse(s.confirm_trade_entry('SOL/USDT',self.now))
        trades.assert_called_once_with(pair='SOL/USDT',is_open=False)
    def test_cooldown_boundary_and_future_trade_are_handled(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendRecoveryCooldownStrategy
        from unittest.mock import patch
        from datetime import timedelta
        s=BtcTrendRecoveryCooldownStrategy({'stake_currency':'USDT'})
        s._last_closed_row=Mock(return_value=pd.Series({'cooldown_btc_strict':False}))
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',return_value=[SimpleNamespace(close_date_utc=self.now-timedelta(days=14)),SimpleNamespace(close_date_utc=self.now+timedelta(days=1))]):
            self.assertTrue(s.confirm_trade_entry('SOL/USDT',self.now))
    def test_confirmed_long_trend_bypasses_cooldown(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendRecoveryCooldownStrategy
        from unittest.mock import patch
        s=BtcTrendRecoveryCooldownStrategy({'stake_currency':'USDT'})
        s._last_closed_row=Mock(return_value=pd.Series({'cooldown_btc_strict':True}))
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',side_effect=AssertionError('no need for history in strict bull regime')):
            self.assertTrue(s.confirm_trade_entry('SOL/USDT',self.now))
    def test_cooldown_missing_closed_data_blocks_entry(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendRecoveryCooldownStrategy
        s=BtcTrendRecoveryCooldownStrategy({'stake_currency':'USDT'})
        s._last_closed_row=Mock(return_value=None)
        self.assertFalse(s.confirm_trade_entry('SOL/USDT',self.now))
    def test_cooldown_accepts_first_position_in_independent_cash_window(self):
        from ma200_btc_regime_full_cycle_core_hold_strategy import BtcTrendRecoveryCooldownStrategy
        from unittest.mock import patch
        s=BtcTrendRecoveryCooldownStrategy({'stake_currency':'USDT'})
        s._last_closed_row=Mock(return_value=pd.Series({'cooldown_btc_strict':False}))
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',return_value=[]):
            self.assertTrue(s.confirm_trade_entry('SOL/USDT',self.now))

    def phase(self, strict=True, previous=.75, stake=200., amount=10., realized=0.):
        s=Phased({'stake_currency':'USDT','max_open_trades':3,'fee':.001})
        s._pair_budget=Mock(return_value=400.)
        s._last_closed_row=Mock(return_value=pd.Series({'cooldown_btc_strict':strict,'exposure_exit':False,'close':20.}))
        trade=SimpleNamespace(pair='SOL/USDT',has_open_orders=False,open_date_utc=datetime(2025,1,1,tzinfo=timezone.utc),enter_tag='phase_reduced_entry',amount=amount,stake_amount=stake,fee_open=.001,realized_profit=realized,entry_side='buy',exit_side='sell',get_custom_data=Mock(return_value=previous),set_custom_data=Mock())
        return s,trade
    def phase_adjust(self,s,t,rate=20.,minimum=1.,maximum=1000.):
        return s.adjust_trade_position(t,self.now,rate,0.,minimum,maximum,rate,rate,0.,0.)
    def test_initial_capital_is_not_inflated_by_open_partial_profit(self):
        from unittest.mock import patch
        s=Phased({'stake_currency':'USDT','max_open_trades':3})
        s.wallets=Mock();s.wallets.get_starting_balance.return_value=1180.
        def trades(**kwargs):
            return [SimpleNamespace(realized_profit=180.)] if kwargs.get('is_open') else [SimpleNamespace(close_profit_abs=30.)]
        with patch('ma200_btc_regime_full_cycle_core_hold_strategy.Trade.get_trades_proxy',side_effect=trades):
            self.assertAlmostEqual(s._pair_budget('SOL/USDT'),1000./3+30.)
            s.wallets.get_starting_balance.return_value=2000.
            self.assertAlmostEqual(s._pair_budget('SOL/USDT'),1000./3+30.)
        s.wallets.get_starting_balance.assert_called_once()
    def test_reduced_and_full_entry_reserve_fees_and_respect_cash(self):
        s,t=self.phase()
        self.assertAlmostEqual(s.custom_stake_amount('SOL/USDT',self.now,20.,100.,1.,1000.,1.,'phase_reduced_entry','long'),300./1.001)
        self.assertAlmostEqual(s.custom_stake_amount('SOL/USDT',self.now,20.,100.,1.,1000.,1.,'phase_full_entry','long'),400./1.001)
        self.assertEqual(s.custom_stake_amount('SOL/USDT',self.now,20.,100.,25.,20.,1.,'phase_full_entry','long'),0.)
    def test_reduce_uses_cost_basis_and_waits_for_fill(self):
        s,t=self.phase(strict=False,previous=1.,stake=400./1.001,amount=10.)
        result=self.phase_adjust(s,t,rate=40.)
        self.assertAlmostEqual(result[0],-t.stake_amount*.25)
        self.assertEqual(result[1],s.PHASE_DOWN_TAG)
        t.set_custom_data.assert_not_called()
        s.order_filled(t.pair,t,SimpleNamespace(ft_order_tag=s.PHASE_DOWN_TAG,ft_order_side='sell'),self.now)
        t.set_custom_data.assert_called_once_with(s.PHASE_KEY,.75)
    def test_topup_uses_own_reserved_cash_and_exchange_limit(self):
        s,t=self.phase()
        result=self.phase_adjust(s,t)
        self.assertAlmostEqual(result[0],199.8/1.001)
        self.assertEqual(result[1],s.PHASE_UP_TAG)
        t.set_custom_data.assert_not_called()
        self.assertEqual(self.phase_adjust(s,t,maximum=50.),(50.,s.PHASE_UP_TAG))
        self.assertIsNone(self.phase_adjust(s,t,minimum=25.,maximum=20.))
    def test_limited_topup_remains_retryable_after_fill(self):
        s,t=self.phase(stake=250.,amount=12.5)
        s.order_filled(t.pair,t,SimpleNamespace(ft_order_tag=s.PHASE_UP_TAG,ft_order_side='buy'),self.now)
        t.set_custom_data.assert_not_called()
        t.stake_amount=400./1.001;t.amount=20.
        s.order_filled(t.pair,t,SimpleNamespace(ft_order_tag=s.PHASE_UP_TAG,ft_order_side='buy'),self.now)
        t.set_custom_data.assert_called_once_with(s.PHASE_KEY,1.)
    def test_pending_orders_and_exit_signal_prevent_adjustments(self):
        s,t=self.phase()
        t.has_open_orders=True;self.assertIsNone(self.phase_adjust(s,t))
        t.has_open_orders=False
        s._last_closed_row.return_value['exposure_exit']=True
        self.assertIsNone(self.phase_adjust(s,t))
    def test_sold_and_retained_market_values_must_meet_minimum(self):
        s,t=self.phase(strict=False,previous=1.,stake=400./1.001,amount=10.)
        self.assertIsNone(self.phase_adjust(s,t,rate=40.,minimum=110.))
    def test_partial_sale_profit_is_counted_once_in_restoration(self):
        # 1,000/3 initial cash; buy with fee, sell half after price doubles.
        budget=1000./3;full_stake=budget/1.001;full_qty=full_stake/10.
        sold_qty=full_qty/2;proceeds=sold_qty*20.*.999
        sold_cost=full_stake/2*1.001;profit=proceeds-sold_cost
        s,t=self.phase(stake=full_stake/2,amount=full_qty/2,realized=profit)
        s._pair_budget.return_value=budget
        topup=self.phase_adjust(s,t)[0]
        self.assertAlmostEqual(topup,proceeds/1.001)

if __name__=='__main__': unittest.main(verbosity=2)
