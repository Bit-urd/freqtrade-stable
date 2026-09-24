"""全周期组合策略的快速测试版：只用来验证"实盘跑出来的交易和回测一致"，不是用来赚钱的（2026-09-25 加入）。

正式版（Ma200BtcRegimeFullCyclePortfolioStrategy）是日线 + 周线，一年只交易几次，实盘跑一周
什么都看不到。这个版本代码完全继承正式版，只改周期和熊市分档，让所有代码路径一周内都能走到：
- 日线 → 15 分钟线：MA200 = 50 小时，EMA20 / EMA50 = 5 / 12.5 小时。
- 周线 → 1 小时线：仓位调节（满槽位 / 半槽位）看 1 小时 EMA20 > EMA50。
- 熊市分档按 15 分钟 BTC 相对 MA200 的偏离率缩小：-0.4% / -0.8% / -1.2% / -1.6% / -2.0%。
其他规则（2 根 K 线确认退出、交接、只加不减、等权槽位）跟正式版一模一样，所以实盘和回测
逐笔对上，就说明正式版的下单、仓位计算、加减仓、交接这些逻辑在实盘里也是对的。

这个版本手续费占比很高、没有任何收益预期，余额会慢慢被手续费磨掉。

用法见 docs/linux_deployment.md 第 18 节。
"""

from __future__ import annotations

from ma200_btc_regime_full_cycle_portfolio_strategy import Ma200BtcRegimeFullCyclePortfolioStrategy


class Ma200BtcRegimeFullCycleFastTestStrategy(Ma200BtcRegimeFullCyclePortfolioStrategy):
    timeframe = "15m"
    INFORMATIVE_TIMEFRAME = "1h"
    BEAR_TIERS = [(-0.004, 0.20), (-0.008, 0.40), (-0.012, 0.60), (-0.016, 0.80), (-0.020, 1.00)]
