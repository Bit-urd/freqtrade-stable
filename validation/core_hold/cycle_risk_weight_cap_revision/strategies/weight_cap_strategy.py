"""固定 50% 单币权重约束：只限制新增，或同时减去持仓超额部分。"""
from cycle_risk_strategy import BtcCoinGuardCycleRiskStrategy

class BtcCoinGuardAllocationCapStrategy(BtcCoinGuardCycleRiskStrategy):
    COIN_WEIGHT_LIMIT = .5

    def _coin_limit(self):
        return self.COIN_WEIGHT_LIMIT * (self.risk_trace[-1]['prior_closed_equity'] if self.risk_trace else self.wallets.get_starting_balance())

    def custom_stake_amount(self, pair, current_time, current_rate, proposed_stake,
                            min_stake, max_stake, leverage, entry_tag, side, **kwargs):
        original = super().custom_stake_amount(pair,current_time,current_rate,proposed_stake,min_stake,max_stake,leverage,entry_tag,side,**kwargs)
        fee = .001 if self.config.get('fee') is None else float(self.config['fee'])
        amount = min(original,self._coin_limit()/(1+fee))
        return amount if amount >= (min_stake or 0) else 0.

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        original = super().adjust_trade_position(trade,current_time,current_rate,current_profit,min_stake,max_stake,current_entry_rate,current_exit_rate,current_entry_profit,current_exit_profit,**kwargs)
        if original is None or original[0] <= 0:
            return original
        room = max(0.,self._coin_limit()-float(trade.amount)*current_rate)
        amount = min(original[0],room/(1+float(trade.fee_open)))
        return (amount,original[1]) if amount >= max(1.,min_stake or 0.) else None

class BtcCoinGuardPositionCapStrategy(BtcCoinGuardAllocationCapStrategy):
    def adjust_trade_position(self, trade, current_time, current_rate, current_profit,
                              min_stake, max_stake, current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        original = super().adjust_trade_position(trade,current_time,current_rate,current_profit,min_stake,max_stake,current_entry_rate,current_exit_rate,current_entry_profit,current_exit_profit,**kwargs)
        if trade.has_open_orders or trade.open_date_utc >= current_time:
            return original
        if self.custom_exit(trade.pair,trade,current_time,current_rate,current_profit):
            return original
        value = float(trade.amount)*current_rate
        minimum = max(1.,min_stake or 0.)
        excess = value-self._coin_limit()
        if excess < minimum or value <= 0:
            return original
        parent_sell = -original[0]/float(trade.stake_amount)*value if original and original[0]<0 else 0.
        sold = max(excess,parent_sell)
        if value-sold < minimum:
            return original
        tag = original[1] if parent_sell else 'coin_weight_cap'
        # Freqtrade 部分退出参数按成本本金计，不直接传出市场价值。
        return (-float(trade.stake_amount)*sold/value,tag)
