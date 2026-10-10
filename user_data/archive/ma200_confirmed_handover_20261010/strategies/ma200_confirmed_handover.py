"""Research only: existing MA200 signals plus trend-confirmed handover top-up."""
from datetime import timedelta
from ma200_btc_regime_full_cycle_portfolio_strategy import (
    Ma200BtcRegimeFullCyclePortfolioStrategy, BEAR_TAG,
)


def own_bull_confirmed(row, previous):
    """Same coin-side condition used by the existing bull entry, closed candles only."""
    if row is None or previous is None:
        return False
    return bool(
        row["close"] > row["ema20"] > row["ema50"]
        and row["ema20"] > previous["ema20"]
        and row["ema50"] > previous["ema50"]
    )


class Ma200ConfirmedHandoverStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    HANDOVER_TOP_UP = True

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit, **kwargs):
        if (trade.enter_tag == BEAR_TAG
                and not trade.get_custom_data(self.HANDOVER_KEY)
                and self._bull_seen_since_open(trade.pair, trade, current_time)):
            row = self._last_closed_row(trade.pair, current_time)
            previous = self._last_closed_row(trade.pair, current_time - timedelta(days=1))
            if (row is None or not bool(row["btc_bull_2d"])
                    or not own_bull_confirmed(row, previous)):
                return None
        return super().adjust_trade_position(
            trade, current_time, current_rate, current_profit,
            min_stake, max_stake, current_entry_rate, current_exit_rate,
            current_entry_profit, current_exit_profit, **kwargs,
        )
