"""Behavioral and temporal checks for the independent-trend research variants."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "strategies"))
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy
from independent_cycle_risk_strategy import (
    IndependentHoldCycleRiskStrategy,
    IndependentProbeCycleRiskStrategy,
    IndependentPromoteCycleRiskStrategy,
)


def main():
    config = json.loads((ROOT / "config.json").read_text())
    classes = [IndependentHoldCycleRiskStrategy, IndependentProbeCycleRiskStrategy,
               IndependentPromoteCycleRiskStrategy]
    checks = []
    history = {p.stem.split("-")[0].replace("_", "/"): pd.read_feather(p)
               for p in (ROOT / "data").glob("*-1d.feather")}
    for pair in ["BTC/USDT", "SUI/USDT", "ZEC/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT"]:
        strategy = IndependentHoldCycleRiskStrategy(config)
        strategy._history = lambda p, tf: history[p].copy()
        full = strategy.populate_indicators(history[pair].copy(), {"pair": pair})
        for end in ["2022-06-15", "2024-06-15", "2025-11-30", "2026-09-01"]:
            stamp = pd.Timestamp(end, tz="UTC")
            raw = history[pair].loc[history[pair].date <= stamp]
            if len(raw) < 200:
                continue
            strategy._history = lambda p, tf: history[p].loc[history[p].date <= stamp].copy()
            prefix = strategy.populate_indicators(raw.copy(), {"pair": pair})
            pd.testing.assert_frame_equal(prefix.reset_index(drop=True),
                                          full.loc[full.date <= stamp].reset_index(drop=True))
            checks.append(f"prefix_invariance:{pair}:{end}")
        if pair == "BTC/USDT":
            baseline = BtcCoinGuardCycleRiskStrategy(config)
            baseline._history = lambda p, tf: history[p].copy()
            original = baseline.populate_entry_trend(
                baseline.populate_indicators(history[pair].copy(), {"pair": pair}), {"pair": pair})
            for cls in classes:
                variant = cls(config)
                variant._history = lambda p, tf: history[p].copy()
                result = variant.populate_entry_trend(
                    variant.populate_indicators(history[pair].copy(), {"pair": pair}), {"pair": pair})
                assert not result.independent_strong.any()
                pd.testing.assert_frame_equal(original[["enter_long", "enter_tag"]],
                                              result[["enter_long", "enter_tag"]])
                checks.append(f"btc_entry_identity:{cls.__name__}")

    now = pd.Timestamp("2026-01-05", tz="UTC").to_pydatetime()
    row = pd.Series({"exposure_exit": True, "independent_strong": True,
                     "coin_risk_off": False})
    for cls in classes:
        strategy = cls(config)
        strategy._last_closed_row = lambda *args: row
        strategy._risk_fraction = 0.75
        assert strategy.custom_exit("ZEC/USDT", None, now, 100, 0) is None
        assert strategy.custom_exit("BTC/USDT", None, now, 100, 0) == "trend_to_cash"
        assert strategy._desired_fraction("ZEC/USDT", now) == 0.5
        strategy._risk_fraction = 0.25
        assert strategy._desired_fraction("ZEC/USDT", now) == 0.25
        row["coin_risk_off"] = True
        assert strategy.custom_exit("ZEC/USDT", None, now, 100, 0) == "coin_trend_to_cash"
        row["coin_risk_off"] = False
        row["independent_strong"] = False
        assert strategy.custom_exit("ZEC/USDT", None, now, 100, 0) == "trend_to_cash"
        row["independent_strong"] = True
        checks.append(f"exit_exception_and_risk_cap:{cls.__name__}")

    strategy = IndependentHoldCycleRiskStrategy(config)
    strategy._last_closed_row = lambda *args: row
    strategy._risk_fraction = 1.0
    strategy._pair_budget = lambda pair: 1000.0
    custom = {strategy.STAGE_KEY: 1.0}
    trade = SimpleNamespace(pair="ZEC/USDT", enter_tag="phase_full_entry", amount=10,
                            stake_amount=1000, fee_open=.001, realized_profit=0,
                            open_date_utc=pd.Timestamp("2026-01-01", tz="UTC"),
                            has_open_orders=False, get_custom_data=custom.get)
    result = strategy.adjust_trade_position(trade, now, 100, 0, 1, 1000, 100, 100, 0, 0)
    assert result == (-500.0, strategy.ORDER_PREFIX + "0.5")
    assert custom[strategy.STAGE_KEY] == 1.0, "Requested order must not preemptively change filled state"
    checks.append("partial_exit_waits_for_fill")

    promoter = IndependentPromoteCycleRiskStrategy(config)
    # Current/future candles cannot count towards the three completed-candle promotion.
    frames = pd.DataFrame({"date": pd.date_range("2026-01-03", periods=4, tz="UTC"),
                           "independent_strong": [True, True, True, True]})
    promoter.dp = SimpleNamespace(get_analyzed_dataframe=lambda *args: (frames, None))
    trade.open_date_utc = pd.Timestamp("2026-01-03", tz="UTC")
    assert not promoter._probe_confirmed(trade, now)
    assert promoter._probe_confirmed(trade, pd.Timestamp("2026-01-06", tz="UTC"))
    checks.append("probe_promotion_uses_three_completed_candles")
    (ROOT / "indicator_verification.json").write_text(json.dumps({"checks": checks, "passed": True}, indent=2))
    print(f"Passed {len(checks)} behavioral and prefix invariance checks", flush=True)


if __name__ == "__main__":
    main()
