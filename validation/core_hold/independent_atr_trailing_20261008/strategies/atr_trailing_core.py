"""Completed-close trailing state, independent of the trading engine."""
import math


def advance(state, date, close, atr, multiple, activate=False):
    state = dict(state or {})
    if state.get('date') == date:
        return state, bool(state.get('hit', False))
    if not math.isfinite(close) or close <= 0:
        return state, False
    peak = max(state.get('peak', close), close)
    active = state.get('active', False) or activate
    old_stop = state.get('stop')
    # Test the previously known stop before today's close can raise it.
    hit = bool(active and old_stop is not None and close <= old_stop)
    stop = old_stop
    if active and math.isfinite(atr) and atr > 0:
        candidate = peak - multiple * atr
        stop = candidate if stop is None else max(stop, candidate)
    state.update(date=date, peak=peak, active=active, stop=stop, hit=hit)
    return state, hit
