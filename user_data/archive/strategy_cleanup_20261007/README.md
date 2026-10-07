# 策略目录清理（2026-10-07）

本目录保留被移出的源码与原因；回测报告和原始成交未删除。

- `ma200_ema_alignment_weekly_sized_leverage_strategy.py`：杠杆试验失败：48 组仅 11 组胜出，收益中位数下降且回撤更高。
- `ma200_ema_alignment_weekly_sized_strategy.py`：旧单币实现，组合版设 max_open_trades=1 可以承担单币对照；没有必要平行维护。
- `ma200_btc_regime_full_cycle_core_hold_growth_strategy.py`：Growth 为现有 CoreHold 默认参数的重复包装；Recovery 已被新正式版和分阶段主线替代，不再单独探索。

附带 CoreHold 冻结依赖，方便恢复 Growth/Recovery 包装版；归档中的原 Growth 配置保持不变。活动配置改为相同默认规则的 CoreHold 类，不更改算法。旧单币版归档表示停止维护，不代表其历史验证失败。

当前目录清单及源码哈希见 manifest.json；当前正式版和保留方向见 ../../strategies/README.md。运行服务未切换。

活动目录注释中文化：改动前的八个文件备份在 before_chinese_comments/，前后源码哈希见 comment_translation.json。去除说明字符串后的语法树全部一致；正式冻结回测源码不改，活动版本另记源码哈希。加载与规则核对见 verification.json。
