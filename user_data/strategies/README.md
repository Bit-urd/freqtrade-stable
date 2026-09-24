# 策略状态与交易规则

`strategies/` 只放经过验证、目前值得用的策略，以及一个标明"验证未通过、仅研究用"的杠杆版本。四个策略都基于同一套 MA200+EMA 日线规则 + 周线仓位。

## 使用场景总览

| 策略 | 文件 | 状态 | 什么时候用 | 大致结论 |
| --- | --- | --- | --- | --- |
| `Ma200EmaAlignmentWeeklySizedStrategy` | `ma200_ema_alignment_weekly_sized_strategy.py` | 正式（单币） | 一个账户只跑一个币（`max_open_trades=1`） | 回撤明显小于持有，熊市 8/8 跑赢；单边牛市全部跑输持有；单币每年约 2 笔交易；新币要等约 200 天 |
| `Ma200EmaAlignmentWeeklySizedPortfolioStrategy` | `ma200_ema_alignment_weekly_sized_portfolio_strategy.py` | 正式（多币） | 多个币共用一个账户，每币一个槽位 | 10 币组合每年 17～28 笔，回撤 -10%～-41%（持有 -50%～-84%），去掉最高和最低贡献者后 4/5 区间仍双赢；牛市弱点没有解决；3～4 个币的小组合主要只起降回撤的作用 |
| `Ma200BtcRegimeWeeklySizedPortfolioStrategy` | `ma200_btc_regime_weekly_sized_portfolio_strategy.py` | 候选（多币） | 多币账户，币池有新币，或想让小币跟着 BTC 大环境走、熊市完全空仓 | 对比组合版 15 组里 11 组收益更好，熊市 0 亏损，新币提前 2～5 个月参与；但全周期优势主要来自新币提前进场，只看 BTC 过滤时 10 币全周期输给组合版、牛市区间全部是成本（见 [复核](../validation/ma200_btc_regime_20260923/REVIEW_20260923.md)）；代价是 BTC 跌破 MA200 时会放弃小币的独立行情（如 2025 年四季度的 ZEC） |
| `Ma200EmaAlignmentWeeklySizedLeverageStrategy` | `ma200_ema_alignment_weekly_sized_leverage_strategy.py` | **验证未通过，仅研究用** | 只用于研究"周线确认时加 3 倍杠杆"，不要 dry-run 或实盘 | 48 组里只有 11 组跑赢 1 倍对照，收益中位数 -30 个百分点，回撤更深 |

怎么选：只跑一个币用单币版；跑多个币用组合版或 BTC 定牛熊版。后两者的区别是"用每个币自己的 MA200，还是统一用 BTC 的 MA200"。所有结论都是样本内回测，还没有 dry-run。

## `Ma200BtcRegimeWeeklySizedPortfolioStrategy`（BTC 定牛熊的多币组合版，2026-09-23 加入，候选）

牛熊只看 BTC 日线 MA200（BTC 收盘 > MA200 才允许进场，跌破并连续 2 天成立就退出），EMA20/50 排列和周线仓位用每个币自己的数据，仓位算法跟组合版一样。`startup_candle_count` 从 210 降到 60，新币上线约 2 个月就能交易。

**验证结果**（[报告](../validation/ma200_btc_regime_20260923/REPORT.md)，跟组合版同币池、同日期对比，10 币 / BTC+ETH+BNB+XRP / BTC+ETH+SOL × 五个区间）：15 组里收益更好 11 组、打平 1 组、更差 3 组，回撤基本相当，交易频率全面提高。2022 年熊市三个组合都是 0 笔交易。UNI、SOL、ARB 的首笔交易分别提前到 2020-11、2021-01、2023-07。BTC+ETH+SOL 全周期从 +2024% 提高到 +4417%。

**已知局限**：BTC 跌破 MA200 时会清掉所有小币。2025-10-17 BTC 跌破后，ZEC 在 +421% 时就平仓了，组合版一直持有到 +1105%，所以 10 币组合的牛熊交替区间变差（+91% 对 +137%）。2021 年年中 BTC 有 98 天在 MA200 下方，10 币组合牛市收益变差（+1809% 对 +2439%），但回撤更小。新币第一年的周线信号比较粗糙。

**实现细节**：回测和画图时，BTC 日线、各币日线和周线都从数据目录读完整历史算指标（EMA 起算点不随回测区间变化，跟实盘一致），所以数据目录里必须有 `BTC/USDT` 日线数据，即使 BTC 不在币池里。dry-run 和实盘时用 DataProvider，交易所首次会下载 1000 根，本来就够。新币要有 60 根自己的日线才进场（实盘和回测一致）；BTC 当天数据缺失时不进场、也不按 BTC 退出。

**复核（2026-09-23）**：[REVIEW_20260923.md](../validation/ma200_btc_regime_20260923/REVIEW_20260923.md)——拆分后 BTC 过滤本身 9 组更好、5 组更差，全周期优势主要来自新币提前进场；0.3% 手续费下结论不变；81 个月度滚动起点里回撤全部小于持有，但 2023 年以后起步的收益全部跑输等权持有。

配置：`user_data/strategy_conf/ma200_btc_regime_weekly_sized_portfolio.conf` + `user_data/config_backtest_portfolio_spot.json`。

## `Ma200EmaAlignmentWeeklySizedPortfolioStrategy`（多币组合版，2026-09-23 提升为正式策略）

进出场规则、周线 100%/50% 规则和下面的原版完全一样，只改了仓位算法，让多个币能共用一个钱包：
- 原版把目标仓位算成 `目标 × (持仓市值 + 全部可用现金)`，单币时就是整个账户。放进多币共用钱包后，第一个开仓的币会占掉所有现金，其他币进不去。回测里原版放进 10 币钱包的回撤是 -47%～-85%。
- 组合版：每个币一个槽位 = 账户市值 / `max_open_trades`。开仓 = 周线目标 × 槽位。持仓期间只在周线目标**翻转**时调整（1.0→0.5 卖一半，0.5→1.0 补足一个槽位），价格涨跌不再平衡。上次应用的目标存在 trade custom data 里，bot 重启后不会丢。

**验证结果**（[报告](../validation/ma200_weekly_sized_portfolio_20260923/REPORT.md)，10 个币共用 1000 USDT、10 个槽位）：组合每年 17～28 笔交易（单币每年约 2 笔），5 个市场区间的市值回撤 -10%～-41%，等权买入持有是 -50%～-84%。每个区间去掉贡献最高和最低的币后，全周期、2024 年至今、熊市、牛熊交替 4 个区间仍然收益和回撤双赢。

**已知局限**：牛市（2020-10→2021-11）去掉 DOGE 后，组合 +580%，持有 +1687%。单币"单边牛市跑输持有"的问题**没有被解决**，完整组合只是在有超级大赢家时把它盖住了。币池是事后挑的（有幸存者偏差），全部是样本内结果，还没有 dry-run。

配置：`user_data/strategy_conf/ma200_ema_alignment_weekly_sized_portfolio.conf`（10 个币）+ `user_data/config_backtest_portfolio_spot.json`（`max_open_trades: 10`）。注意：用这个类跑单个币时要把 `max_open_trades` 设成 1，否则只会用 1/10 的资金。

原版单币策略保留不动：

## `Ma200EmaAlignmentWeeklySizedStrategy`（山寨币 MA200+EMA 趋势策略，2026-09-23 提升为正式策略）

日线 MA200 定趋势 + EMA20/50 排列决定进出场；退出要求连续 2 天满足跌破条件才清仓。在此基础上叠加一层仓位大小控制：持仓期间，**周线 EMA20>EMA50（确认周线多头）时满仓，否则减到 50%**——用比日线慢得多的信号决定"拿多大仓位"，避免了之前"分级仓位"实验里日线信号太敏感导致的反复整仓。来自 [`ma200_ema_alignment_robustness_20260922`](../validation/ma200_ema_alignment_robustness_20260922/REPORT.md) 六轮结构性实验（退出确认/分级仓位/放宽进场/10%止损/25%止损/ATR动态止损/周线仓位大小）里第二个净正面版本，取代了原来单纯的"退出确认"版本。

**这次改动是什么，为什么不是"止损"**：止损类的四次尝试（固定10%、固定25%、3倍ATR动态止损）全部失败，根因是"给已经在验证有效的退出信号之外再加一层硬止损"本质上是在每笔交易上收保险费，但真正需要它赔付的极端单日暴跌场景在全部历史数据里只出现过一次（LINK 2020-03-12）。仓位大小不同：它不强制平仓打断趋势，只是让"满仓"这件事本身跟着一个更慢的趋势判断走，牛市正常回调不会被直接洗出局，只是仓位变小。

**验证结果**：九资产全周期上，回撤在**全部9个资产**上都有改善（部分接近腰斩，如 ETH -70%→-50%、UNI -85%→-77%），熊市窗口里仓位变小让亏损普遍减半；代价集中在 BNB（历史最强单边长牛，周线回调被误伤，全周期收益打了对折）。牛市窗口没有改善（0/9，跟仓位大小无关，是退出滞后的老问题）。交易笔数没有像失败的止损实验那样暴增。

**已知且接受的局限（结构性的，不要指望靠再调参数"修好"）**：
- 任何单边牛市窗口，九个测试资产全部跑输买入持有（0/9）——均线类退出规则的固有代价。
- LINK、XRP、ZEC 全周期跑输买入持有（进场滞后错过连续拉升中段 / 震荡市反复假突破磨损），ETH、BNB、ARB、UNI、DOGE、SOL 没有这个问题。
- BNB 这类历史最强单边趋势的资产，加仓位控制后收益会明显打折——这是刻意接受的取舍（用部分上限换全局风控），不是待修的问题。
- 目前所有验证都是同一批历史数据反复检验（in-sample），还没有做过样本外/前向验证。

默认配置：`user_data/strategy_conf/ma200_ema_alignment_weekly_sized.conf`，数据用清洗过坏K线的 `user_data/data/binance_alt_spot_research_clean/`（含 1d/4h/1w 三个周期，清洗逻辑见 `clean_data.py`，改动记录见 `user_data/validation/ma200_ema_alignment_robustness_20260922/outliers.json`）。策略用 Freqtrade 标准的 `informative_pairs`（`1w`）+ `merge_informative_pair` 读取周线数据，`position_adjustment_enable=True` 做仓位调整，理论上可以直接 dry-run（还没有实际跑过）。`run_backtest_and_plot.sh` 没有默认策略，需显式设置 `STRATEGY_CONF`。

## 已归档，不再是当前候选

- `Ma200EmaAlignmentConfirmedExitStrategy`（只有退出确认、没有仓位控制的版本）：已归档到 `user_data/archive/strategies/ma200_ema_alignment_confirmed_exit_strategy.py`。被上面的周线仓位版本取代——入场和退出逻辑完全一样，周线仓位版本额外做了风控，九资产回撤全面改善。
- `Ma200EmaAlignmentStrategy`（基线核心版）：已归档到 `user_data/archive/strategies/ma200_ema_alignment_strategy.py`。退出是被验证过的劣化版本（单日触发 vs 连续2天确认）。
- `WeeklyDailyEmaPullbackStrategy`（周线过滤+日线回踩+4H确认完整版）：已归档到 `user_data/archive/strategies/weekly_daily_ema_pullback_strategy.py`。是用户最初的完整设计，但在所有测过的维度里都没有明确赢过核心版（共同区间 3/6 vs 核心版 5/6，全周期打平），也没有跟着核心版做后续优化。完整思路和数据留在 [`weekly_daily_ema_pullback_20260922/REPORT.md`](../validation/weekly_daily_ema_pullback_20260922/REPORT.md)，不会因为归档丢失。
- `Ma200TrendStrategy`（BTC 专用日线 MA200 二元策略）已于 2026-09-22 归档到 `user_data/archive/strategies/ma200_trend_strategy.py`：2021-01-01→2026-09-19 连续回测仅 +34.19%，远低于 BTC 同期 +179.34%，每日权益回撤 -72.19% 与 BTC 的 -76.67% 相差无几，下跌季度里介入的几笔常常比 BTC 本身跌得更多，永续合约资金费还会额外侵蚀收益，不构成生产依据。详见 [压力测试报告](../archive/validation/ma200_stress_20260921/REPORT.md)。
- `daily_trend_4h_breakout.py`：当前市场门控研究所复用的纯信号计算模块，不是 Freqtrade 策略类，已归档到 `user_data/archive/strategies/daily_trend_4h_breakout.py`。

BTC 日线门控的多资产适配器位于 `user_data/archive/validation/btc_recovery_ethbtc_gate_20260922/MarketGateEngineCheckStrategy.py`（连同其余支撑这条研究主线的验证目录，已归档到 `user_data/archive/validation/`，代码本身没有改动，只是搬了位置；只有 `weekly_daily_ema_pullback_20260922`、`ma200_ema_alignment_robustness_20260922` 这两个跟 `strategies/` 下现存策略直接相关的目录还留在 `user_data/validation/`）。它依赖冻结的本地历史行情，仅用于 Freqtrade 回测，不能直接运行实时交易。旧的练习和未通过替代标准的策略统一放在 `user_data/archive/strategies/`，不会被默认策略目录加载。

## 当前通用研究主线：25/50/100% 日线状态

每个标的独立计算自身趋势：日线收盘价不高于 MA200，或收盘价低于 EMA50 且 EMA20 低于 EMA50 时，目标 **0%**；从 0% 恢复的第一步是 **50%**；已有趋势仓位时，若收盘价高于 MA200 且 EMA20 > EMA50 > MA200、EMA50 上升，则目标 **100%**，否则维持 **50%**。当标的自身目标为 0%、但已完成的 BTC 日线趋势目标大于 0% 时，额外保留 **25% 核心仓**。BTC 本身不套这层外部门控。信号在收线后确定，历史验证按下一根 4H 开盘调整仓位。这是 `MARKET_GATE_VARIANT=btc_trend`，不是 `Ma200TrendStrategy` 的规则。

25% 门控在最长可用区间把六个山寨的策略收益都提高到高于原日线基线，但仍只有 **4/6** 跑赢各自买入持有；ETH、ARB 的最大回撤比原基线更深。在 2024 年后的共同区间，Freqtrade 复核为 **5/6** 跑赢持有，但加入门控后 ARB、UNI、LINK 的策略收益下降。它不是“六币大部分时期都同时收益更高、回撤更小”。[最长区间结果](../archive/validation/market_gated_core_20260922/REPORT.md)和[Freqtrade 共同区间结果](../archive/validation/btc_recovery_ethbtc_gate_20260922/FREQTRADE_REPORT.md)使用不同起点，不能直接比累计百分比。

另一个实验曾在 **4H 突破时先买 50%**，失败即快速退出。那不是这里的日线 50% 趋势状态；它换手显著增加，最长区间只有 2/6 山寨跑赢持有，已归档。[4H 试仓结果](../archive/validation/daily_trend_4h_breakout_20260922/REPORT.md)。

`Ma200TrendStrategy` 的完整交易规则（信号、状态机、仓位配置、手续费口径）已随代码一起搬到 [归档说明](../archive/README.md)。
