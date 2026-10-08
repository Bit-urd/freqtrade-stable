"""Check that unused market examples do not conceal a broken probe-entry branch."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "strategies"))
from independent_cycle_risk_strategy import (
    IndependentHoldCycleRiskStrategy,
    IndependentProbeCycleRiskStrategy,
    IndependentPromoteCycleRiskStrategy,
)

config = json.loads((ROOT / "config.json").read_text())
frame = pd.DataFrame({"own_candles": [200], "volume": [100],
                      "exposure_entry": [False], "cooldown_btc_strict": [False],
                      "coin_risk_on": [True], "independent_strong": [True]})
now = pd.Timestamp("2026-01-06", tz="UTC")
row = pd.Series({"exposure_exit": True, "independent_strong": True})
hold = IndependentHoldCycleRiskStrategy(config)
assert hold.populate_entry_trend(frame.copy(), {"pair": "ZEC/USDT"}).enter_long.fillna(0).iloc[0] == 0
checks = ["hold_variant_does_not_add_weak_market_entries"]
for cls in [IndependentProbeCycleRiskStrategy, IndependentPromoteCycleRiskStrategy]:
    strategy = cls(config)
    entered = strategy.populate_entry_trend(frame.copy(), {"pair": "ZEC/USDT"})
    assert entered.enter_long.iloc[0] == 1 and entered.enter_tag.iloc[0] == "independent_probe"
    strategy._last_closed_row = lambda *args: row
    strategy._pair_budget = lambda pair: 1000
    amount = strategy.custom_stake_amount("ZEC/USDT", now, 100, 1000, 1, 1000, 1,
                                          "independent_probe", "long")
    assert abs(amount - 250 / 1.001) < 1e-8
    assert strategy._pending_initial_fraction["ZEC/USDT"] == .25
    checks.append(f"probe_entry_and_quarter_budget:{cls.__name__}")
    history = pd.DataFrame({"date": pd.date_range("2026-01-03", periods=3, tz="UTC"),
                            "independent_strong": [True, True, True]})
    strategy.dp = SimpleNamespace(get_analyzed_dataframe=lambda *args: (history, None))
    trade = SimpleNamespace(pair="ZEC/USDT", enter_tag="independent_probe",
                            open_date_utc=pd.Timestamp("2026-01-03", tz="UTC"))
    expected = .5 if cls.ALLOW_PROBE_PROMOTION else .25
    assert strategy._desired_fraction("ZEC/USDT", now, trade=trade) == expected
    checks.append(f"promotion_variant_distinction:{cls.__name__}")

(ROOT / "entry_verification.json").write_text(json.dumps({"passed": True, "checks": checks}, indent=2))
print(f"Passed {len(checks)} independent-entry branch checks", flush=True)
