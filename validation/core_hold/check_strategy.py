"""Offline callback regression checks: run inside the Freqtrade image."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd

strategy_path = Path('/freqtrade/user_data/strategies')
if not (strategy_path/'ma200_btc_regime_full_cycle_core_hold_strategy.py').exists():
    strategy_path = Path('/freqtrade/user_data/archive/cycle_risk_flatten_20261007/strategies')
sys.path.insert(0, str(strategy_path))
from ma200_btc_regime_full_cycle_core_hold_strategy import (
    BULL_TAG, Ma200BtcRegimeFullCycleCoreHoldStrategy as Strategy,
)


class CoreHoldChecks(unittest.TestCase):
    def setUp(self):
        self.strategy = Strategy({'stake_currency': 'USDT'})
        self.now = datetime(2026, 1, 3, tzinfo=timezone.utc)
        self.data = pd.DataFrame({
            'date': pd.date_range('2026-01-01', periods=3, tz='UTC'),
            'weekly_bull': [True, False, True],
            'btc_exit': [False] * 3, 'coin_weak_2d': [True] * 3,
        })
        self.strategy.dp = Mock()
        self.strategy.dp.get_analyzed_dataframe.return_value = (self.data, None)
        self.trade = SimpleNamespace(
            pair='BTC/USDT', enter_tag=BULL_TAG, has_open_orders=False,
            open_date_utc=datetime(2025, 1, 1, tzinfo=timezone.utc),
            amount=10., stake_amount=100., exit_side='sell', entry_side='buy',
            get_custom_data=Mock(return_value=None), set_custom_data=Mock(),
        )

    def adjust(self, minimum=1., rate=20., maximum=1000.):
        return self.strategy.adjust_trade_position(
            self.trade, self.now, rate, 0., minimum, maximum, rate, rate, 0., 0.)

    def test_closed_candle_weekly_target(self):
        self.assertEqual(self.strategy._weekly_target(self.trade.pair, self.now), .5)

    def test_trim_ratios_and_fill_state(self):
        for retained in (.25, .5, .75):
            self.strategy.CORE_RETAIN_FRACTION = retained
            self.assertEqual(self.adjust(), (-100 * (1-retained), 'bull_core_trim'))
        self.trade.set_custom_data.assert_not_called()
        self.strategy.order_filled(self.trade.pair, self.trade,
                                  SimpleNamespace(ft_order_side='sell',
                                                  ft_order_tag='bull_core_trim'), self.now)
        self.trade.set_custom_data.assert_called_once_with('core_hold_trimmed', True)
        self.trade.get_custom_data.return_value = True
        self.assertIsNone(self.adjust())

    def test_exchange_minimum_uses_market_value(self):
        self.assertEqual(self.adjust(minimum=75.), (-50., 'bull_core_trim'))
        self.assertIsNone(self.adjust(minimum=75., rate=10.))

    def test_btc_exit_takes_priority(self):
        self.data.loc[1, 'btc_exit'] = True
        self.assertIsNone(self.adjust())
        self.assertEqual(self.strategy.custom_exit(
            self.trade.pair, self.trade, self.now, 20., 0.), 'bull_btc_bear_core_exit')

    def test_early_entry_keeps_btc_filter(self):
        self.strategy.BULL_ENTRY_MODE = 'early'
        data = pd.DataFrame({'own_candles': [100]*3, 'btc_above': [True, True, False],
                             'close': [20.]*3, 'ema20': [10., 11., 12.],
                             'ema50': [15.]*3, 'volume': [1.]*3, 'bear_target': [0.]*3})
        result = self.strategy.populate_entry_trend(data, {'pair': 'BTC/USDT'})
        self.assertEqual(result.loc[1, 'enter_long'], 1)
        self.assertTrue(pd.isna(result.loc[2, 'enter_long']))

    def test_core_restore_waits_for_fill_and_respects_available_cash(self):
        self.strategy.CORE_RESTORE_ON_RECOVERY = True
        self.strategy.BULL_WEEKLY_SIZING = False
        self.data['coin_recovered'] = True
        self.trade.get_custom_data.return_value = True
        self.strategy._equity = Mock(return_value=1200.)
        self.strategy._slots = Mock(return_value=3)
        self.assertEqual(self.adjust(), (200., 'bull_core_restore'))
        self.trade.set_custom_data.assert_not_called()
        self.assertIsNone(self.adjust(minimum=25., maximum=20.))
        self.trade.set_custom_data.assert_not_called()
        self.strategy.order_filled(self.trade.pair, self.trade,
                                  SimpleNamespace(ft_order_side='buy',
                                                  ft_order_tag='bull_core_restore'), self.now)
        self.trade.set_custom_data.assert_called_once_with('core_hold_trimmed', False)

    def test_handover_topup_marks_state_only_after_fill(self):
        self.trade.enter_tag = 'bear_accumulate'
        self.strategy.HANDOVER_TOP_UP = True
        self.strategy._bull_seen_since_open = Mock(return_value=True)
        self.strategy._equity = Mock(return_value=1200.)
        self.strategy._slots = Mock(return_value=3)
        self.data['btc_above'] = True
        self.assertEqual(self.adjust(), (200., 'handover_top_up'))
        self.trade.set_custom_data.assert_not_called()
        self.assertIsNone(self.adjust(minimum=25., maximum=20.))
        self.trade.set_custom_data.assert_not_called()
        self.strategy.order_filled(self.trade.pair, self.trade,
                                  SimpleNamespace(ft_order_side='buy',
                                                  ft_order_tag='handover_top_up'), self.now)
        self.trade.set_custom_data.assert_any_call('handover_topped_up', True)

    def test_unified_handover_core_exits_on_btc_only(self):
        self.trade.enter_tag = 'bear_accumulate'
        self.strategy.HANDOVER_CORE_HOLD = True
        self.strategy._bull_seen_since_open = Mock(return_value=True)
        self.data['bull_exit'] = True
        self.assertIsNone(self.strategy.custom_exit(self.trade.pair, self.trade,
                                                   self.now, 20., 0.))
        self.data.loc[1, 'btc_exit'] = True
        self.assertEqual(self.strategy.custom_exit(self.trade.pair, self.trade,
                                                  self.now, 20., 0.),
                         'handover_btc_bear_core_exit')

    def test_disabling_weekly_sizing_preserves_untrimmed_exposure(self):
        self.data['coin_weak_2d'] = False
        self.strategy._weekly_target = Mock(return_value=.5)
        self.trade.get_custom_data.side_effect = lambda key: {
            'weekly_bull_seen': True, 'weekly_target': 1.,
        }.get(key)
        self.strategy.BULL_WEEKLY_SIZING = False
        self.assertIsNone(self.adjust())
        self.strategy.BULL_WEEKLY_SIZING = True
        self.assertEqual(self.adjust(), -50.)

    def test_public_growth_profiles_match_backtested_settings(self):
        sys.path.append(str(Path(__file__).parent / 'strategies'))
        import json
        from ma200_btc_regime_full_cycle_core_hold_growth_strategy import (
            Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy,
            Ma200BtcRegimeFullCycleCoreHoldRecoveryStrategy,
        )
        keys = ['HANDOVER_TOP_UP', 'BULL_WEEKLY_SIZING', 'HANDOVER_CORE_HOLD',
                'CORE_RESTORE_ON_RECOVERY', 'CORE_RETAIN_FRACTION',
                'BTC_BEAR_CONFIRM_DAYS', 'BULL_ENTRY_MODE']
        recorded = json.loads((Path(__file__).parent / 'improve_btc_sol_eth' / 'selection.json').read_text())['default_settings']
        recorded['BULL_ENTRY_MODE'] = 'alignment'
        recovery = {**recorded, 'HANDOVER_CORE_HOLD': True, 'CORE_RESTORE_ON_RECOVERY': True}
        for public, tested in [(Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy, recorded),
                               (Ma200BtcRegimeFullCycleCoreHoldRecoveryStrategy, recovery)]:
            public({'stake_currency': 'USDT'})
            for key in keys:
                self.assertEqual(getattr(public, key), tested[key])
        for key in keys:
            self.assertEqual(getattr(Strategy, key),
                             getattr(Ma200BtcRegimeFullCycleCoreHoldGrowthStrategy, key))

    def test_invalid_parameters(self):
        for name, value in [('CORE_RETAIN_FRACTION', 0), ('BTC_BEAR_CONFIRM_DAYS', 0),
                            ('BTC_BEAR_CONFIRM_DAYS', 1.5), ('BULL_ENTRY_MODE', 'unknown')]:
            invalid = type('Invalid', (Strategy,), {name: value})
            with self.assertRaises(ValueError):
                invalid({})
        for fields in [
            {'CORE_RESTORE_ON_RECOVERY': True, 'BULL_WEEKLY_SIZING': True},
            {'HANDOVER_CORE_HOLD': True, 'HANDOVER_TOP_UP': False},
        ]:
            invalid = type('InvalidDependency', (Strategy,), fields)
            with self.assertRaises(ValueError):
                invalid({})


if __name__ == '__main__':
    unittest.main()
