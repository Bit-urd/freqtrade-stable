# 当前策略：只保留必要方向（2026-10-07）

## 保留的探索方向

| 方向 | 策略 | 保留理由 |
|---|---|---|
| 正式版：收益与熊市防守折中 | `BtcCoinGuardCycleRiskStrategy`，`cycle_risk_strategy.py` | 用户确认正式版本；上涨与两类熊市改善，近期和部分标的仍有弱点 |
| 关键对照：原 Portfolio | `Ma200BtcRegimeFullCyclePortfolioStrategy` | 近期更稳，ADA/LINK/AVAX 等标的有独立优势，不能删除 |
| 上涨参与：分阶段 / 快速退出 | `BtcTrendPhasedStrategy` / `BtcTrendFastExitStrategy` | 分阶段上涨表现更强；快速退出保留作退出速度对照，两者共享 CoreHold 文件 |
| 温和核心仓 | `Ma200BtcRegimeFullCycleCoreHoldStrategy` | 保留不同于趋势清仓的核心仓逻辑；就是既有 Growth 默认规则，去掉重复别名 |
| 个币独立趋势、不依赖 BTC | `Ma200EmaAlignmentWeeklySizedPortfolioStrategy` | 研究币自身行情与 BTC 脱钩的独立方向；单币使用时槽位设为 1 |

正式版本范围仍为 BTC/SOL/ETH；[跨标的对比](../../validation/core_hold/representative_assets/REPORT.md)显示并非通用最优。正式版交易逻辑与[冻结版本](../../validation/core_hold/archive/portfolio_cycle_risk_v2/OFFICIAL.json)一致，注释和说明已统一中文。实盘重启状态持久化尚未实现，正式选定不代表已完成上线验证，本次没有提供上线配置或切换服务。

## 必要依赖与兼容实现

- `equity_risk_strategy.py`：正式版权益控制父类，不作为新的独立研究候选。
- `btc_trend_coin_guard_strategy.py`：正式版信号父类及风控消融对照，不另开优化主线。
- `ma200_btc_regime_full_cycle_core_hold_strategy.py` 中 FullCycle、Cooldown 等类为继承基础；严格 MA150 分支仅保留历史对照，不作为优先探索方向。为保持正式依赖源码不变，本轮不拆分这些类。
- `Ma200BtcRegimeFullCycleFastTestStrategy`：正在运行的 `freqtrade-fast-test` 服务依赖，保留以支持运行及重启；不是新增研究方向。
- `Ma200BtcRegimeWeeklySizedPortfolioStrategy`：现有 Docker Compose 的兼容引用，保留以免破坏用户配置；不是当前正式版。

## 配置

`config_portfolio_btc_sol_eth.json`、`config_trend_btc_sol_eth.json`、`config_trend_fast_exit_btc_sol_eth.json` 保留对应对照配置。`config_core_growth_btc_sol_eth.json` 现指向相同默认逻辑的 CoreHold 类，文件名保留方便已有引用；旧别名配置已随源码归档。个币保护配置保留作正式版信号对照。

## 已归档

失败杠杆版、旧单币周线版、Growth/Recovery 重复包装版已移至 [清理归档](../archive/strategy_cleanup_20261007/README.md)。源码、配置、哈希和旧说明均保留；以前的回测研究目录不改动。
