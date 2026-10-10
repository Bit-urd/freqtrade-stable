"""Research: unchanged parent adjustments, then optional idle-cash supplementation."""
import math
from datetime import timedelta
from freqtrade.enums import RunMode
from freqtrade.persistence import Trade
from ma200_confirmed_handover import Ma200ConfirmedHandoverStrategy, own_bull_confirmed
from ma200_btc_regime_full_cycle_portfolio_strategy import BEAR_TAG


def proportional_cash(claims, cash, fee):
    clean = {str(k): float(v) for k, v in claims.items()
             if math.isfinite(float(v)) and float(v) > 0}
    total = math.fsum(clean.values())
    if not math.isfinite(cash) or cash <= 0 or total <= 0:
        return {}
    scale = min(1., cash / (1 + max(0., fee)) / total)
    return {k: v * scale for k, v in sorted(clean.items())}


class Ma200CashSupplementStrategy(Ma200ConfirmedHandoverStrategy):
    PLAN_KEY = 'supplement_plan_v1'
    REQUEST_KEY = 'supplement_request_v1'
    CORE_KEY = 'supplement_parent_day_v1'

    def __init__(self, config):
        super().__init__(config)
        self._supplement_frames = {}
        self._supplement_plan = None
        self.funding_trace = []

    def populate_indicators(self, dataframe, metadata):
        result = super().populate_indicators(dataframe, metadata)
        self._supplement_frames[metadata['pair']] = result
        return result

    def _cash_row(self, pair, now):
        # Only supplementation uses synchronized closed frames. Parent access is untouched.
        if self.dp.runmode in (RunMode.LIVE, RunMode.DRY_RUN):
            frame, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        else:
            frame = self._supplement_frames.get(pair)
        if frame is None or frame.empty:
            return None
        rows = frame.loc[frame['date'] < self._executing_candle_start(now)]
        if rows.empty:
            return None
        row = rows.iloc[-1]
        if row['date'].date() != (self._executing_candle_start(now) - timedelta(days=1)).date():
            return None
        return row

    def _cash_target(self, trade, row):
        # Read-only: only the parent may change risk/handover state.
        if self.BULL_ENTRY_FULL and not trade.get_custom_data(self.WEEKLY_SEEN_KEY):
            return 1.
        return 1. if bool(row['weekly_bull']) else .5

    def _cash_qualified(self, trade, now, row):
        if row is None or not bool(row['btc_bull_2d']) or bool(row['bull_exit']):
            return False
        if trade.enter_tag == BEAR_TAG and not trade.get_custom_data(self.HANDOVER_KEY):
            return False
        return float(row['volume']) > 0 and own_bull_confirmed(
            row, self._cash_row(trade.pair, now - timedelta(days=1)))

    def _core_busy(self, trades, now, rows):
        """Yield all cash on a day with parent orders, transitions or possible new entries."""
        day = self._executing_candle_start(now).date().isoformat()
        for trade in trades:
            row = rows.get(trade.pair)
            if (row is None or trade.has_open_orders
                    or trade.open_date_utc >= self._executing_candle_start(now)
                    or trade.get_custom_data(self.CORE_KEY) == day):
                return True
            if bool(row['bull_exit']):
                return True
            # Parent bear accumulation/handover keeps sole control of its cash.
            if trade.enter_tag == BEAR_TAG and not trade.get_custom_data(self.HANDOVER_KEY):
                return True
            previous = float(trade.get_custom_data(self.TARGET_KEY, default=1.))
            if self._cash_target(trade, row) != previous:
                return True
        held = {t.pair for t in trades}
        if len(held) < self._slots():
            for pair in self.dp.current_whitelist():
                if pair in held:
                    continue
                row = self._cash_row(pair, now)
                if row is None:
                    return True
                if float(row['volume']) <= 0 or row['own_candles'] <= self.startup_candle_count:
                    continue
                bear_allowed = self.BEAR_PAIRS is None or pair in self.BEAR_PAIRS
                if self.BEAR_ENABLED and bear_allowed and row['bear_target'] > 0:
                    return True
                if (self.BULL_ENABLED and row['btc_above']
                        and own_bull_confirmed(row, self._cash_row(pair, now - timedelta(days=1)))):
                    return True
        return False

    def _cash_plan(self, now):
        day = self._executing_candle_start(now).date().isoformat()
        if self._supplement_plan and self._supplement_plan['day'] == day:
            return self._supplement_plan
        trades = list(Trade.get_trades_proxy(is_open=True))
        rows = {t.pair: self._cash_row(t.pair, now) for t in trades}
        # Recheck priority even when restoring a fixed plan after a restart.
        busy = self._core_busy(trades, now, rows)
        for trade in trades:
            stored = trade.get_custom_data(self.PLAN_KEY)
            if not busy and stored and stored['day'] == day:
                self._supplement_plan = stored
                return stored
        cash = max(0., float(self.wallets.get_free(self.config['stake_currency'])))
        valid = all(r is not None and math.isfinite(float(r['close'])) for r in rows.values())
        values = {str(t.id): float(t.amount) * float(rows[t.pair]['close'])
                  for t in trades} if valid else {}
        equity = cash + math.fsum(values.values())
        slot = equity / self._slots()
        fee = max([float(t.fee_open or 0.) for t in trades] + [float(self.config.get('fee') or .001)])
        targets = {}; claims = {}
        if valid and not busy:
            for trade in trades:
                key = str(trade.id); row = rows[trade.pair]
                if not self._cash_qualified(trade, now, row):
                    continue
                targets[key] = self._cash_target(trade, row) * slot
                claims[key] = max(0., targets[key] - values[key])
        plan = {'day': day, 'cash': cash, 'equity': equity, 'targets': targets,
                'claims': claims, 'allocation': proportional_cash(claims, cash, fee),
                'valid': valid, 'parent_busy': busy}
        self._supplement_plan = plan
        for trade in trades:
            trade.set_custom_data(self.PLAN_KEY, plan)
        self.funding_trace.append(plan)
        return plan

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        before = (trade.get_custom_data(self.TARGET_KEY), trade.get_custom_data(self.HANDOVER_KEY))
        original = super().adjust_trade_position(
            trade, current_time, current_rate, current_profit, min_stake, max_stake,
            current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit, **kwargs)
        if not self.config.get('cash_supplement_enabled', True):
            return original
        day = self._executing_candle_start(current_time).date().isoformat()
        after = (trade.get_custom_data(self.TARGET_KEY), trade.get_custom_data(self.HANDOVER_KEY))
        if original is not None or before != after:
            trade.set_custom_data(self.CORE_KEY, day)
            # A parent action invalidates any cached supplemental budget.
            self._supplement_plan = None
            return original
        if (trade.has_open_orders or trade.open_date_utc >= current_time
                or trade.get_custom_data(self.REQUEST_KEY) == day
                or trade.get_custom_data(self.CORE_KEY) == day):
            return None
        row = self._cash_row(trade.pair, current_time)
        if not self._cash_qualified(trade, current_time, row):
            return None
        plan = self._cash_plan(current_time)
        key = str(trade.id)
        if key not in plan['targets']:
            return None
        gap = plan['targets'][key] - float(trade.amount) * current_rate
        cash = max(0., float(self.wallets.get_free(self.config['stake_currency'])))
        fee = max(float(trade.fee_open or 0.), float(self.config.get('fee') or .001))
        amount = min(plan['allocation'].get(key, 0.), gap, max_stake, cash / (1 + fee))
        if amount < max(1., min_stake or 0.):
            return None
        trade.set_custom_data(self.REQUEST_KEY, day)
        return amount, 'idle_cash:' + day


class Ma200CashSupplementDisabled(Ma200CashSupplementStrategy):
    def __init__(self, config):
        super().__init__({**config, 'cash_supplement_enabled': False})
