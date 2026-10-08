"""Research variants: preserve coin rules, broaden market permission via ETH.

All features use completed, synchronized UTC daily candles. ETH/BTC is a
synthetic close ratio. BTC trades always retain original market permission.
"""
import pandas as pd
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy


class EthRotationCycleRiskStrategy(BtcCoinGuardCycleRiskStrategy):
    ETH_PAIR = 'ETH/USDT'
    REQUIRE_BREADTH = False
    ROTATION_CAP = .5
    BTC_FIVE_DAY_FLOOR = -.10
    BREADTH_POOL = ('SOL/USDT', 'ADA/USDT', 'DOGE/USDT',
                    'AVAX/USDT', 'SUI/USDT', 'ZEC/USDT')
    BREADTH_MIN_PEERS = 3
    BREADTH_MIN_FRACTION = .60
    BREADTH_LOOKBACK = 10

    def informative_pairs(self):
        pairs = dict.fromkeys((self.BTC_PAIR, self.ETH_PAIR, *self.BREADTH_POOL))
        return [(pair, self.timeframe) for pair in pairs]

    @staticmethod
    def _flag(row, key):
        value = row.get(key, False)
        return pd.notna(value) and bool(value)

    @staticmethod
    def _strong(close):
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        return ((close > ema20) & (ema20 > ema50)
                & (ema20 > ema20.shift(1)) & (ema50 > ema50.shift(1)))

    def _breadth_features(self, pair):
        eligible, above = [], []
        for peer in self.BREADTH_POOL:
            if peer == pair:
                continue
            history = self._history(peer, self.timeframe).set_index('date')
            close = history['close']
            ma50 = close.rolling(50, min_periods=50).mean()
            mature = close.notna() & ma50.notna()
            eligible.append(mature.rename(peer))
            above.append(((close > ma50) & mature).rename(peer))
        count = pd.concat(eligible, axis=1).sum(axis=1)
        fraction = pd.concat(above, axis=1).sum(axis=1) / count.where(count >= self.BREADTH_MIN_PEERS)
        result = pd.DataFrame({'breadth_valid_peers': count, 'breadth_fraction': fraction})
        result['breadth_confirmed'] = ((fraction >= self.BREADTH_MIN_FRACTION)
                                      & (fraction >= fraction.shift(self.BREADTH_LOOKBACK)))
        return result

    def populate_indicators(self, dataframe, metadata):
        frame = super().populate_indicators(dataframe, metadata)
        eth = self._history(self.ETH_PAIR, self.timeframe)[['date', 'close']]
        btc = self._history(self.BTC_PAIR, self.timeframe)[['date', 'close']]
        market = eth.rename(columns={'close': 'eth_close'}).merge(
            btc.rename(columns={'close': 'btc_close'}), on='date', how='inner')
        market['eth_btc_close'] = market.eth_close / market.btc_close
        warm = market.eth_btc_close.rolling(50, min_periods=50).count() >= 50
        both = self._strong(market.eth_close) & self._strong(market.eth_btc_close) & warm
        market['eth_rotation_confirmed'] = both.rolling(2).sum() == 2
        market['btc_five_day_return'] = market.btc_close.pct_change(5, fill_method=None)
        market['rotation_stress_allowed'] = market.btc_five_day_return > self.BTC_FIVE_DAY_FLOOR
        market = market.set_index('date').join(self._breadth_features(metadata['pair'])).reset_index()
        market['rotation_allowed'] = market.eth_rotation_confirmed & market.rotation_stress_allowed
        if self.REQUIRE_BREADTH:
            market['rotation_allowed'] &= market.breadth_confirmed.fillna(False)
        if metadata['pair'] == self.BTC_PAIR:
            market['rotation_allowed'] = False
        columns = ['date', 'eth_btc_close', 'eth_rotation_confirmed',
                   'btc_five_day_return', 'rotation_stress_allowed',
                   'breadth_valid_peers', 'breadth_fraction',
                   'breadth_confirmed', 'rotation_allowed']
        return frame.merge(market[columns], on='date', how='left')

    def populate_entry_trend(self, dataframe, metadata):
        frame = super().populate_entry_trend(dataframe, metadata)
        if metadata['pair'] != self.BTC_PAIR:
            rotation = ((frame.own_candles > self.startup_candle_count)
                        & (frame.volume > 0) & frame.coin_risk_on.fillna(False)
                        & ~frame.exposure_entry.fillna(False)
                        & frame.rotation_allowed.fillna(False))
            frame.loc[rotation, ['enter_long', 'enter_tag']] = [1, 'eth_rotation_entry']
        return frame

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        row = self._last_closed_row(pair, current_time)
        if row is None:
            return None
        if self._flag(row, 'exposure_exit'):
            if pair == self.BTC_PAIR or not self._flag(row, 'rotation_allowed'):
                return 'trend_to_cash'
        return 'coin_trend_to_cash' if self._flag(row, 'coin_risk_off') else None

    def _desired_fraction(self, pair, current_time):
        row = self._last_closed_row(pair, current_time)
        if pair == self.BTC_PAIR or row is None or self._flag(row, 'exposure_entry'):
            return self._risk_fraction
        return min(self._risk_fraction, self.ROTATION_CAP)

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fraction = self._desired_fraction(pair, current_time)
        fee = .001 if self.config.get('fee') is None else float(self.config['fee'])
        amount = min(fraction * self._pair_budget(pair) / (1 + fee), max_stake)
        if amount < (min_stake or 0):
            return 0.0
        self._pending_initial_fraction[pair] = fraction
        return amount

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._desired_fraction(trade.pair, current_time)
        previous = trade.get_custom_data(self.STAGE_KEY)
        previous = 1.0 if previous is None else previous
        if desired == previous:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        cash = max(0.0, self._pair_budget(trade.pair) + float(trade.realized_profit or 0)
                   - float(trade.stake_amount) * (1 + fee))
        delta = desired * (cash + value) - value
        minimum = max(1.0, min_stake or 0)
        tag = self.ORDER_PREFIX + str(desired)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, tag) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, tag)
        return None


class EthBreadthRotationCycleRiskStrategy(EthRotationCycleRiskStrategy):
    REQUIRE_BREADTH = True
