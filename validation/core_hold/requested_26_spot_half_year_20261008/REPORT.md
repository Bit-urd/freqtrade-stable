# 指定26币现货近半年回测

窗口2026-04-08—2026-10-07，共183个UTC交易日，初始10000 USDT，现货做多，无杠杆、无资金费，单边手续费0.1%，滑点0。各币等额初始独立预算、已实现利润独立复投，原版BTC一天退出与正式BTC两天退出对照，其余规则相同。

资产：0G、BONK、AAVE、ADA、AERO、APT、ARB、BOME、BTC、DOT、ETH、FIL、GRAM、JUP、LDO、LINK、OP、POL、PUMP、SKY、SOL、STRK、SUI、UNI、WCT、XRP。BONK为BONK/USDT现货，不使用1000BONK合约单位；本轮不含MON、BNB、DOGE。

|组合|策略|收益|最大回撤|平均现金占比|
|---|---|---:|---:|---:|
|Requested26 | BtcCoinGuardCycleRiskStrategy | +36.81% | 14.74% | 61.25%|
|Requested26 | BtcTwoDayExitCycleRiskStrategy | +50.38% | 12.26% | 53.48%|
|Requested26 | BuyAndHold | +36.80% | 35.88% | 6.97%|
|Mature24 | BtcCoinGuardCycleRiskStrategy | +39.88% | 15.86% | 58.38%|
|Mature24 | BtcTwoDayExitCycleRiskStrategy | +54.58% | 13.12% | 50.23%|
|Mature24 | BuyAndHold | +37.57% | 38.32% | 0.00%|

Requested26按用户指定26个槽位保留所有预算。AERO首根日线2026-07-17，截至末日83根；GRAM首根2026-07-02，共98根，均未满足MA150，策略没有买入，约7.69%初始预算保留现金。Mature24剔除这两个币重新运行，初始预算重新分配，非从26币盈亏简单相减。

持有基准在区间首日开盘等预算买入；不足61根历史的资产在第62根日线开盘买入，之前留现金。AERO持有买入日2026-09-16，GRAM为2026-09-01。策略MA150门槛与持有暖机口径不同，保留此前实验的持有定义。日终曲线不计末日强制平仓，完整成交现金另与原生最终余额核对。

26币正式两天版收益50.38%，比原版高13.57个百分点，比持有高13.58个百分点；回撤比原版低2.49个百分点，比持有低23.62个百分点。成熟24币两天版54.58%/13.12%回撤。增加已成熟资产预算提高本期收益，也使风险暴露和回撤略升，不据此事后删除其他弱币。

## 逐币贡献（26币正式两天版）

这里是同一个组合中的利润贡献，不是独立单币回测。

|标的|利润USDT|
|---|---:|
|UNI/USDT|+748.19|
|LDO/USDT|+573.84|
|PUMP/USDT|+432.63|
|STRK/USDT|+367.66|
|AAVE/USDT|+321.65|
|BOME/USDT|+320.82|
|0G/USDT|+318.99|
|ARB/USDT|+318.77|
|JUP/USDT|+256.28|
|SOL/USDT|+169.00|
|LINK/USDT|+153.82|
|SUI/USDT|+150.81|
|BONK/USDT|+139.94|
|OP/USDT|+132.29|
|POL/USDT|+122.93|
|FIL/USDT|+113.88|
|ETH/USDT|+92.26|
|APT/USDT|+90.75|
|XRP/USDT|+81.40|
|BTC/USDT|+68.49|
|SKY/USDT|+50.90|
|DOT/USDT|+43.72|
|ADA/USDT|+30.23|
|AERO/USDT|+0.00|
|GRAM/USDT|+0.00|
|WCT/USDT|-60.95|

## 代码对应

- 正式两天版：user_data/strategies/cycle_risk_strategy.py，BtcCoinGuardCycleRiskStrategy，TREND_EXIT_DAYS=2。
- 升级前原版：user_data/archive/cycle_risk_two_day_official_20261008/cycle_risk_strategy_before.py，TREND_EXIT_DAYS=1。
- 本轮原版冻结副本：strategies/cycle_risk_strategy.py；两天候选：strategies/btc_exit_confirmation_strategy.py，BtcTwoDayExitCycleRiskStrategy。AST核对候选与正式交易实现一致。
- 新增现货26币配置：user_data/config_cycle_risk_spot_26.json。正式九币选择与运行服务不变，未部署此配置。

## 核验

四次原生策略回测、两条持有曲线；独立核对六条净值、18项汇总、406次BTC退出、454次弱BTC入场冷却、728日账户风险权益。最大净值误差1.10e-11 USDT、原生最终现金误差2.98e-8 USDT。资金与行情均来自冻结快照，本轮未重新选择资产或优化参数。

[汇总](summary.csv)、[逐币归因](profit_attribution.csv)、[交易频率](trade_frequency.json)、[数据覆盖](data_audit.json)、[核验](audit_verification.json)。
