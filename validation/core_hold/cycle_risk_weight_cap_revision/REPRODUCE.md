# 复现

在仓库根目录运行。行情复用 production_comparison_2023_latest/data，运行时显式传入隔离数据路径；两个 user_data 只读挂载供历史分析模块和配置目录校验使用。单次只运行一个研究容器。

```bash
docker run --rm --user 0 --name freqtrade-cycle-weight-cap \
  -e PYTHONPATH=/freqtrade:/home/ftuser/.local/lib/python3.14/site-packages \
  -e OPENBLAS_NUM_THREADS=1 -e OMP_NUM_THREADS=1 -e NUMEXPR_MAX_THREADS=1 \
  -v "$PWD/validation/core_hold:/research" \
  -v "$PWD/user_data:/freqtrade/user_data:ro" \
  -v "$PWD/user_data:/research/user_data:ro" -w /research --entrypoint python \
  freqtradeorg/freqtrade@sha256:7031bca43ed7668ebf421725dd5016acade6ef88b0771db3e08c96e6d19a42db \
  run_cycle_risk_weight_cap_revision.py
```

将最后脚本名替换为 test_cycle_risk_weight_cap_revision.py 运行规则检查。全部六组完成后，宿主机运行 python3 validation/core_hold/make_cycle_risk_defense_report.py --folder cycle_risk_weight_cap_revision 生成核对报告。再次运行会复用已完成组；需要重新计算时先另行保存并移走该试验目录的results、summary.csv和progress.json。

风险档位自定义字段继续表示已经成交的账户风险指令，单币上限是额外约束，不能将该字段当作实际持仓权重。采用前日已完成权益，按执行时价格限额；成交后价格变化可能让收盘权重重新超过50%，不是硬止损或全天风险保证。
