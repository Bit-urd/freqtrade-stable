"""Accounting regression: buy, partial sell, retained core, terminal liquidation."""
import unittest
import pandas as pd
import analyze


class EquityChecks(unittest.TestCase):
    def test_partial_exit_and_force_exit(self):
        dates = pd.date_range('2026-01-01', periods=3, tz='UTC')
        analyze.PAIRS = ['BTC/USDT']
        analyze.HISTORY = {'BTC/USDT': pd.DataFrame({'close': [100., 120., 130.]}, index=dates)}
        orders = []
        for day, amount, price, entry in [(0, 1., 100., True), (1, .5, 120., False),
                                          (2, .5, 130., False)]:
            orders.append({'amount': amount, 'safe_price': price, 'ft_is_entry': entry,
                           'order_filled_timestamp': int(dates[day].timestamp()*1000)})
        curve, terminal, _ = analyze.ledger([
            {'pair': 'BTC/USDT', 'orders': orders, 'fee_open': .001,
             'fee_close': .001, 'exit_reason': 'force_exit'}], dates)
        self.assertAlmostEqual(terminal, 1024.775)
        self.assertAlmostEqual(curve.cash.iloc[-1], 959.84)
        self.assertAlmostEqual(curve.equity.iloc[-1], 1024.84)
        self.assertAlmostEqual(analyze.stats(curve)['liquidated_return_pct'], 2.4775)


if __name__ == '__main__':
    unittest.main()
