"""个币保护信号不变，在账户层增加权益回撤控制。

每根日线处理前只计算一次前一日收盘权益。初始风险仓位为 100%；
回撤达到 25% 时降至 75%，达到 35% 时降至 50%；
回撤收窄至 30% 以内时恢复到 75%，至 20% 以内时恢复满仓。
不使用杠杆，不在熊市分档囤币。回撤阈值是减仓触发点，不是硬性回撤上限。
研究回测按即时市价成交；实盘重启状态尚未持久化，不提供上线配置。
"""
from freqtrade.persistence import Trade
from btc_trend_coin_guard_strategy import BtcTrendCoinGuardStrategy

class BtcCoinGuardEquityRiskStrategy(BtcTrendCoinGuardStrategy):
    STAGE_KEY = 'equity_risk_filled_fraction'
    ORDER_PREFIX = 'equity_risk_target_'

    def __init__(self, config):
        super().__init__(config)
        self._risk_fraction = 1.0
        self._risk_peak = None
        self._risk_candle = None
        self._pending_initial_fraction = {}
        self.risk_trace = []

    @staticmethod
    def next_fraction(previous, drawdown):
        if drawdown >= .35:
            return .5
        if previous == 1.0:
            return .75 if drawdown >= .25 else 1.0
        if drawdown <= .20:
            return 1.0
        if previous == .5:
            return .75 if drawdown <= .30 else .5
        return .75

    def _closed_price(self, pair, current_time):
        history = self._history(pair, self.timeframe)
        closed = history.loc[history['date'] < self._executing_candle_start(current_time)]
        return None if closed.empty else float(closed.iloc[-1]['close'])

    def bot_loop_start(self, current_time, **kwargs):
        candle = self._executing_candle_start(current_time)
        if candle == self._risk_candle:
            return
        self.wallets.update()
        equity = float(self.wallets.get_free(self.config['stake_currency']))
        equity += float(self.wallets.get_used(self.config['stake_currency']))
        for trade in Trade.get_trades_proxy(is_open=True):
            price = self._closed_price(trade.pair, current_time)
            if price is None:
                return
            # 模拟钱包在退出交易时结算剩余的开仓手续费。
            # 先扣除尚未结算的费用，使权益与实际成交现金账本一致。
            if self.config.get('dry_run', False):
                equity -= float(trade.stake_amount) * float(trade.fee_open)
            equity += float(trade.amount) * price
        if self._risk_peak is None:
            self._risk_peak = float(self.wallets.get_starting_balance())
        self._risk_peak = max(self._risk_peak, equity)
        dd = max(0.0, 1 - equity / self._risk_peak) if self._risk_peak > 0 else 0.0
        self._risk_fraction = self.next_fraction(self._risk_fraction, dd)
        self._risk_candle = candle
        self.risk_trace.append({'execution_date':str(candle), 'prior_closed_equity':equity,
                                'peak':self._risk_peak, 'drawdown':dd,
                                'risk_fraction':self._risk_fraction})

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        fee = .001 if self.config.get('fee') is None else float(self.config['fee'])
        amount = min(self._risk_fraction * self._pair_budget(pair) / (1 + fee), max_stake)
        if amount < (min_stake or 0.0):
            return 0.0
        self._pending_initial_fraction[pair] = self._risk_fraction
        return amount

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return None
        if self.custom_exit(trade.pair, trade, current_time, current_rate, current_profit):
            return None
        desired = self._risk_fraction
        previous = trade.get_custom_data(self.STAGE_KEY)
        if previous is None:
            previous = 1.0
        if desired == previous:
            return None
        value = float(trade.amount) * current_rate
        fee = float(trade.fee_open)
        cash = max(0.0, self._pair_budget(trade.pair) + float(trade.realized_profit or 0.0)
                   - float(trade.stake_amount) * (1 + fee))
        delta = desired * (cash + value) - value
        minimum = max(1.0, min_stake or 0.0)
        tag = self.ORDER_PREFIX + str(desired)
        if desired > previous and delta > 0:
            amount = min(delta / (1 + fee), cash / (1 + fee), max_stake)
            return (amount, tag) if amount >= minimum else None
        sold = -delta
        if desired < previous and sold >= minimum and value - sold >= minimum and value > 0:
            return (-float(trade.stake_amount) * sold / value, tag)
        return None

    def order_filled(self, pair, trade, order, current_time, **kwargs):
        tag = order.ft_order_tag or ''
        if tag.startswith(self.ORDER_PREFIX):
            trade.set_custom_data(self.STAGE_KEY, float(tag[len(self.ORDER_PREFIX):]))
        elif order.ft_order_side == trade.entry_side and trade.get_custom_data(self.STAGE_KEY) is None:
            trade.set_custom_data(self.STAGE_KEY, self._pending_initial_fraction.pop(pair, 1.0))
