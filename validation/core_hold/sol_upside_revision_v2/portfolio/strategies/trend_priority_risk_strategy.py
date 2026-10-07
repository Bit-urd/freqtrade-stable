"""固定结构对照：长期趋势连续确认时满仓，其余沿用原权益风控。"""
from trend_aware_risk_strategy import BtcCoinGuardTrendAwareRiskStrategy

class BtcCoinGuardTrendPriorityRiskStrategy(BtcCoinGuardTrendAwareRiskStrategy):
    def next_fraction(self, previous, drawdown):
        # 不重置账户峰值；报告仍按全历史最高权益计算真实回撤。
        # 保留个币与 BTC 的原退出规则，不能把权益减仓阈值当成回撤上限。
        if self._long_trend_supported:
            return 1.0
        return super().next_fraction(previous, drawdown)
