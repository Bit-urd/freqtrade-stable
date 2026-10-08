"""Causal prefix tests plus synthetic cases separating relative/absolute trends."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'strategies'))
from eth_rotation_strategy import EthRotationCycleRiskStrategy, EthBreadthRotationCycleRiskStrategy
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

config = json.loads((root / 'config.json').read_text())
data = root.parent / 'independent_trend_optimization_20261008/data'
history = {p.stem.split('-')[0].replace('_', '/'): pd.read_feather(p)
           for p in data.glob('*-1d.feather')}
checks = []
for cls in [EthRotationCycleRiskStrategy, EthBreadthRotationCycleRiskStrategy]:
    for pair, end in [('SUI/USDT', '2024-06-15'), ('ZEC/USDT', '2025-11-30'),
                      ('DOGE/USDT', '2022-11-08'), ('ADA/USDT', '2026-09-01')]:
        s = cls(config)
        s._history = lambda p, tf: history[p].copy()
        full = s.populate_indicators(history[pair].copy(), {'pair': pair})
        cutoff = pd.Timestamp(end, tz='UTC')
        s._history = lambda p, tf: history[p].loc[history[p].date <= cutoff].copy()
        prefix = s.populate_indicators(history[pair].loc[history[pair].date <= cutoff].copy(), {'pair': pair})
        pd.testing.assert_frame_equal(prefix.reset_index(drop=True), full.loc[full.date <= cutoff].reset_index(drop=True))
        checks.append(cls.__name__ + ':prefix:' + pair)
    s = cls(config); s._history = lambda p, tf: history[p].copy()
    original = BtcCoinGuardCycleRiskStrategy(config); original._history = s._history
    baseline = original.populate_entry_trend(original.populate_indicators(history['BTC/USDT'].copy(), {'pair': 'BTC/USDT'}), {'pair': 'BTC/USDT'})
    candidate = s.populate_entry_trend(s.populate_indicators(history['BTC/USDT'].copy(), {'pair': 'BTC/USDT'}), {'pair': 'BTC/USDT'})
    pd.testing.assert_frame_equal(candidate[baseline.columns], baseline)
    assert not candidate.rotation_allowed.any()
    checks.append(cls.__name__ + ':btc_signals_identical')

dates = pd.date_range('2020-01-01', periods=240, tz='UTC')
def candles(rate):
    close = 100 * np.exp(rate * np.arange(len(dates)))
    return pd.DataFrame(dict(date=dates, open=close, high=close * 1.01,
                             low=close * .99, close=close, volume=100.))

def synthetic(cls, btc_rate, eth_rate, peer_rates=None):
    source = {p: candles(.002) for p in cls.BREADTH_POOL}
    source.update({'BTC/USDT': candles(btc_rate), 'ETH/USDT': candles(eth_rate)})
    for p, rate in (peer_rates or {}).items(): source[p] = candles(rate)
    s = cls(config); s._history = lambda p, tf: source[p].copy()
    return s, source

s, source = synthetic(EthRotationCycleRiskStrategy, -.01, -.005)
frame = s.populate_indicators(source['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
assert frame.eth_btc_close.iloc[-1] > frame.eth_btc_close.iloc[-2]
assert not frame.eth_rotation_confirmed.iloc[-1]
checks.append('relative_strength_without_absolute_uptrend_rejected')
s, source = synthetic(EthRotationCycleRiskStrategy, .01, .005)
frame = s.populate_indicators(source['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
assert not frame.eth_rotation_confirmed.iloc[-1]
checks.append('absolute_uptrend_without_relative_strength_rejected')
s, source = synthetic(EthRotationCycleRiskStrategy, 0., .005)
frame = s.populate_indicators(source['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
assert frame.rotation_allowed.iloc[-1]
assert not frame.eth_rotation_confirmed.iloc[:50].any()
checks.append('dual_trend_confirmation_and_warmup')
entry = s.populate_entry_trend(frame.copy(), {'pair': 'SOL/USDT'})
assert entry.enter_long.iloc[-1] == 1 and entry.enter_tag.iloc[-1] == 'eth_rotation_entry'
checks.append('rotation_opens_entry_when_btc_gate_closed')
frame.loc[frame.index[-1], 'coin_risk_on'] = False
entry = s.populate_entry_trend(frame.copy(), {'pair': 'SOL/USDT'})
assert entry.enter_long.iloc[-1] == 0
checks.append('rotation_does_not_bypass_own_coin_rule')
s, source = synthetic(EthRotationCycleRiskStrategy, -.03, .005)
frame = s.populate_indicators(source['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
assert frame.eth_rotation_confirmed.iloc[-1] and not frame.rotation_stress_allowed.iloc[-1]
assert not frame.rotation_allowed.iloc[-1]
checks.append('btc_five_day_crash_closes_extra_channel')

weak_peers = {p: -.002 for p in EthRotationCycleRiskStrategy.BREADTH_POOL if p != 'SOL/USDT'}
s, source = synthetic(EthBreadthRotationCycleRiskStrategy, 0., .005, weak_peers)
frame = s.populate_indicators(source['SOL/USDT'].copy(), {'pair': 'SOL/USDT'})
assert frame.eth_rotation_confirmed.iloc[-1] and not frame.rotation_allowed.iloc[-1]
checks.append('eth_strength_alone_cannot_pass_breadth')
prior = s._breadth_features('SOL/USDT')
source['SOL/USDT'] = candles(-.03)
pd.testing.assert_frame_equal(s._breadth_features('SOL/USDT'), prior)
checks.append('own_asset_excluded_from_breadth')
s, source = synthetic(EthBreadthRotationCycleRiskStrategy, 0., .005)
source['SUI/USDT'] = source['SUI/USDT'].iloc[-20:].copy()
breadth = s._breadth_features('SOL/USDT')
assert breadth.breadth_valid_peers.iloc[-1] == 4
assert breadth.breadth_fraction.iloc[-1] == 1
checks.append('immature_new_listing_excluded_from_denominator')
for p in ['ADA/USDT', 'DOGE/USDT', 'AVAX/USDT']: source[p] = source[p].iloc[-20:].copy()
breadth = s._breadth_features('SOL/USDT')
assert not breadth.breadth_confirmed.iloc[-1] and pd.isna(breadth.breadth_fraction.iloc[-1])
checks.append('insufficient_mature_peers_fail_closed')

s = EthRotationCycleRiskStrategy(config)
row = pd.Series(dict(exposure_entry=False, exposure_exit=True, rotation_allowed=True, coin_risk_off=False))
s._last_closed_row = lambda p, now: row
now = dates[-1].to_pydatetime()
assert s.custom_exit('ZEC/USDT', None, now, 100, 0) is None
assert s.custom_exit('BTC/USDT', None, now, 100, 0) == 'trend_to_cash'
checks.append('rotation_extends_alt_holding_but_never_btc_holding')
row['coin_risk_off'] = True
assert s.custom_exit('ZEC/USDT', None, now, 100, 0) == 'coin_trend_to_cash'
checks.append('own_coin_exit_retained')
row['rotation_allowed'] = False
assert s.custom_exit('ZEC/USDT', None, now, 100, 0) == 'trend_to_cash'
checks.append('rotation_expiry_restores_btc_exit')
for risk, target in [(1., .5), (.75, .5), (.5, .5)]:
    s._risk_fraction = risk
    assert s._desired_fraction('ZEC/USDT', now) == target
    assert s._desired_fraction('BTC/USDT', now) == risk
checks.append('rotation_respects_account_risk_cap_and_btc_sizing')
row['exposure_entry'] = True
assert s._desired_fraction('ZEC/USDT', now) == s._risk_fraction
checks.append('btc_recovery_restores_original_target_fraction')
row['exposure_entry'] = False; s._risk_fraction = 1.; s._pair_budget = lambda p: 1000.
stake = s.custom_stake_amount('ZEC/USDT', now, 100, 1000, 1, 1000, 1, 'eth_rotation_entry', 'long')
assert abs(stake - 500 / 1.001) < 1e-8
assert s._pending_initial_fraction['ZEC/USDT'] == .5
assert s.confirm_trade_entry.__func__ is BtcCoinGuardCycleRiskStrategy.confirm_trade_entry
assert s.order_filled.__func__ is BtcCoinGuardCycleRiskStrategy.order_filled
checks.append('fee_adjusted_half_stake_and_unchanged_cooldown_filled_state')

# Save full causal signals for explaining missed and newly admitted opportunities.
audit = root / 'signal_audit'; audit.mkdir(exist_ok=True)
for cls in [EthRotationCycleRiskStrategy, EthBreadthRotationCycleRiskStrategy]:
    for pair in ['SUI/USDT', 'ZEC/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'ETH/USDT', 'SOL/USDT']:
        s = cls(config); s._history = lambda p, tf: history[p].copy()
        frame = s.populate_indicators(history[pair].copy(), {'pair': pair})
        frame['extra_entry_candidate'] = (frame.rotation_allowed.fillna(False)
            & ~frame.exposure_entry.fillna(False) & frame.coin_risk_on.fillna(False)
            & (frame.own_candles > s.startup_candle_count) & (frame.volume > 0))
        columns = ['date', 'close', 'exposure_entry', 'exposure_exit', 'coin_risk_on',
                   'coin_risk_off', 'eth_btc_close', 'eth_rotation_confirmed',
                   'rotation_stress_allowed', 'breadth_valid_peers', 'breadth_fraction',
                   'breadth_confirmed', 'rotation_allowed', 'extra_entry_candidate']
        frame[columns].to_csv(audit / (cls.__name__ + '_' + pair.replace('/', '_') + '.csv'), index=False)
(root / 'indicator_verification.json').write_text(json.dumps(dict(passed=True, count=len(checks), checks=checks), indent=2) + '\n')
print('Passed', len(checks), 'ETH rotation checks', flush=True)
