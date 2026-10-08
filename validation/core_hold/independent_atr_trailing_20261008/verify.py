"""State machine checks runnable without Freqtrade or pandas."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'strategies'))
from atr_trailing_core import advance


class TrailingChecks(unittest.TestCase):
    def test_inactive_does_not_exit(self):
        s, hit = advance(None, '1', 100, 5, 3)
        s, hit = advance(s, '2', 50, 5, 3)
        self.assertFalse(hit)
        self.assertIsNone(s['stop'])

    def test_activation_tracks_prior_trade_peak(self):
        s, _ = advance(None, '1', 100, 5, 3)
        s, hit = advance(s, '2', 95, 5, 3, True)
        self.assertEqual(s['stop'], 85)
        self.assertFalse(hit)

    def test_expanding_atr_cannot_loosen_stop(self):
        s, _ = advance(None, '1', 100, 5, 3, True)
        s, _ = advance(s, '2', 110, 20, 3)
        self.assertEqual(s['stop'], 85)

    def test_survives_activation_flag_turning_off(self):
        s, _ = advance(None, '1', 100, 5, 3, True)
        s, hit = advance(s, '2', 84, 5, 3, False)
        self.assertTrue(s['active'])
        self.assertTrue(hit)

    def test_duplicate_callbacks_preserve_exit(self):
        s, _ = advance(None, '1', 100, 5, 3, True)
        s, hit = advance(s, '2', 84, 5, 3)
        repeated, again = advance(s, '2', 84, 5, 3)
        self.assertTrue(hit and again)
        self.assertEqual(s, repeated)

    def test_new_stop_does_not_retroactively_trigger(self):
        s, _ = advance(None, '1', 100, 10, 3, True)
        s, hit = advance(s, '2', 90, 1, 3)
        self.assertFalse(hit)
        self.assertEqual(s['stop'], 97)
        _, hit = advance(s, '3', 96, 1, 3)
        self.assertTrue(hit)

    def test_missing_atr_defers_initial_stop(self):
        s, hit = advance(None, '1', 100, float('nan'), 3, True)
        self.assertIsNone(s['stop'])
        self.assertFalse(hit)
        s, _ = advance(s, '2', 101, 5, 3)
        self.assertEqual(s['stop'], 86)

    def test_equal_close_triggers(self):
        s, _ = advance(None, '1', 100, 5, 3, True)
        _, hit = advance(s, '2', 85, 5, 3)
        self.assertTrue(hit)

    def test_shared_multiple_grid(self):
        for multiple in (2, 3, 4):
            s, _ = advance(None, '1', 100, 5, multiple, True)
            self.assertEqual(s['stop'], 100 - 5 * multiple)


if __name__ == '__main__':
    unittest.main()
