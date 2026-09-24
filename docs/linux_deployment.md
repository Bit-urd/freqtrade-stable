# Linux 部署手册：Ma200BtcRegimeWeeklySizedPortfolioStrategy

本文说明如何在一台新的 Linux AWS EC2 服务器上部署本仓库中的
`Ma200BtcRegimeWeeklySizedPortfolioStrategy`，从拉取代码到 dry-run、实盘和长期运维。

> 这份策略目前属于候选策略。它使用日线和周线信号，`stoploss = -0.99`，基本没有硬止损；实盘前必须完成 dry-run，并确认自己能承受单币极端亏损。

## 1. 推荐服务器规格

建议使用：

- Ubuntu 24.04 LTS，64 位
- 2 vCPU
- 至少 2 GB RAM
- 20–30 GB gp3 EBS
- 1–2 GB swap
- On-Demand 实例，不使用 Spot

如果服务器只运行真实交易，不运行回测、hyperopt、FreqAI 或 Jupyter，0.5 GB RAM **可以尝试**运行这个日线策略，但它几乎没有内存余量。2 GB 以上不是硬性要求，而是为了给 Docker、操作系统、Python/CCXT、行情 DataFrame 和重连时的瞬时内存峰值留下余量。

0.5 GB 机器的建议限制：

- 只运行一个 Freqtrade 容器
- 使用 `1d`，不要增加 4h、1h 等周期
- 交易对控制在 5–11 个
- 关闭 API/UI、FreqAI、Jupyter 和回测任务
- 保留 1–2 GB swap
- 不要在交易容器运行期间下载大量历史数据
- 持续监控 `free -h`、`docker stats` 和 OOM 日志

如果只运行当前 11 个交易对的日线实盘，0.5 GB 可能长期稳定；但不能在没有监控的情况下承诺十年不发生 OOM。出现 OOM、容器频繁重启或 swap 持续增长时，应升级到 2 GB 以上，而不是继续压缩配置。

## 2. AWS 和系统安全

安全组只开放：

- SSH `22`，限制为自己的固定 IP
- 不要把 Freqtrade API 的 `8080` 直接暴露到公网

登录服务器：

```bash
sudo apt update
sudo apt install -y git curl ca-certificates chrony sqlite3
sudo systemctl enable --now chrony
```

确认系统时间和磁盘：

```bash
timedatectl
free -h
df -h
```

如果内存只有 0.5 GB，创建 swap：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 3. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

重新登录 SSH 后检查：

```bash
docker --version
docker compose version
```

## 4. 拉取代码

本仓库的策略在 `stable-dryrun` 分支中：

```bash
git clone --branch stable-dryrun --single-branch \
  git@github.com:Bit-urd/freqtrade-stable.git \
  ~/freqtrade-stable

cd ~/freqtrade-stable
```

如果服务器没有 GitHub SSH Key，应先配置 SSH Key，或使用 HTTPS 克隆。

确认策略文件存在：

```bash
ls user_data/strategies/ma200_btc_regime_weekly_sized_portfolio_strategy.py
git status
```

## 5. 创建运行目录

```bash
mkdir -p user_data/logs user_data/data user_data/backups
```

不要把以下内容提交到 Git：

- API Key 和 Secret
- SQLite 交易数据库
- 日志
- 行情数据
- 代理地址

## 6. 准备配置

复制 dry-run 配置模板：

```bash
cp config_examples/config_btc_regime_dryrun.example.json user_data/config.json
chmod 600 user_data/config.json
```

如果需要重新生成配置，也可以执行：

```bash
docker compose run --rm freqtrade \
  new-config \
  --config /freqtrade/user_data/config.json
```

编辑配置：

```bash
nano user_data/config.json
```

### 必须确认的字段

```json
{
  "initial_state": "stopped",
  "strategy": "Ma200BtcRegimeWeeklySizedPortfolioStrategy",
  "dry_run": true,
  "dry_run_wallet": 1000,
  "trading_mode": "spot",
  "stake_currency": "USDT",
  "stake_amount": "unlimited",
  "tradable_balance_ratio": 0.99,
  "max_open_trades": 11,
  "timeframe": "1d"
}
```

当前示例币池是 11 个交易对：

```text
BTC/USDT ETH/USDT BNB/USDT SOL/USDT PEPE/USDT
AAVE/USDT PUMP/USDT UNI/USDT ADA/USDT XRP/USDT SUI/USDT
```

`max_open_trades` 应与计划使用的槽位数量一致。如果币池改成 10 个币，也应改成 `10`。

### 删除无效代理

如果配置里有类似下面的内容，而服务器没有对应代理，必须删除：

```json
"httpsProxy": "http://10.66.252.254:7897"
```

### API Key

Dry-run 可以使用空 API Key。实盘 API Key 应满足：

- 只开 Spot 交易和读取权限
- 禁止提现
- 设置 IP 白名单
- 不提交到 Git

配置文件权限应为：

```bash
chmod 600 user_data/config.json
```

## 7. Docker Compose

创建或修改仓库根目录的 `docker-compose.yml`：

```yaml
services:
  freqtrade:
    image: freqtradeorg/freqtrade:stable
    container_name: freqtrade
    restart: unless-stopped
    init: true
    stop_grace_period: 30s

    volumes:
      - "./user_data:/freqtrade/user_data"

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

    command: >
      trade
      --config /freqtrade/user_data/config.json
      --strategy Ma200BtcRegimeWeeklySizedPortfolioStrategy
      --datadir /freqtrade/user_data/data
      --db-url sqlite:////freqtrade/user_data/tradesv3.dryrun.sqlite
      --logfile /freqtrade/user_data/logs/freqtrade.log
```

这里没有公开 API 端口。如果需要 Web UI/API，建议只绑定到本机：

```yaml
ports:
  - "127.0.0.1:8080:8080"
```

然后使用 SSH 隧道访问：

```bash
ssh -L 8080:127.0.0.1:8080 user@server
```

不要直接绑定为 `0.0.0.0:8080:8080`。

## 8. 拉取镜像并检查配置

```bash
docker compose pull

docker compose run --rm freqtrade \
  list-strategies \
  --config /freqtrade/user_data/config.json

docker compose run --rm freqtrade \
  test-pairlist \
  --config /freqtrade/user_data/config.json
docker compose run --rm freqtrade \
  show-config \
  --config /freqtrade/user_data/config.json
```

## 9. 行情数据

### 实盘和 dry-run

实盘或 dry-run 启动后，Freqtrade 会自动从交易所获取行情：

- 白名单交易对的 `1d` 主周期
- 策略 `informative_pairs()` 声明的每个交易对 `1w` 周期
- 额外的 `BTC/USDT` `1d` 周期

因此，实盘启动前不要求先手动运行 `download-data`。首次启动时需要等待交易所返回数据；如果网络、API Key、交易对或交易所接口有问题，日志中会出现下载失败，策略可能暂时没有信号。

检查运行中的数据和错误：

```bash
docker compose logs -f freqtrade
```

BTC 日线数据缺失时，这份策略会禁止新进场，也不会因为 BTC 信号触发退出。不要把“没有交易”误判为策略正常运行，应先检查日志和交易所连接。

### 手动预下载

下面的命令不是实盘必需步骤，主要用于回测、画图、离线检查，或者提前验证交易所能否提供这些交易对的数据。

策略需要每个交易对的日线和周线，同时必须有 `BTC/USDT` 日线数据。

```bash
docker compose run --rm freqtrade \
  download-data \
  --config /freqtrade/user_data/config.json \
  --exchange binance \
  --pairs \
    BTC/USDT ETH/USDT BNB/USDT SOL/USDT PEPE/USDT \
    AAVE/USDT PUMP/USDT UNI/USDT ADA/USDT XRP/USDT SUI/USDT \
  --timeframes 1d 1w \
  --days 1200
```

查看数据：

```bash
docker compose run --rm freqtrade \
  list-data \
  --config /freqtrade/user_data/config.json
```

策略行为：

- 新币至少有 60 根日线后才允许进场
- BTC 日线 MA200 不可用时不进场
- BTC 当天数据缺失时不会按 BTC 信号退出
- 周线信号决定半仓或满槽位

## 10. 启动 dry-run

先保持：

```json
"initial_state": "stopped",
"dry_run": true
```

确认配置无误后，把 `initial_state` 改成 `running`，然后启动：

```bash
docker compose up -d
```

检查状态和日志：

```bash
docker compose ps
docker compose logs --tail=100 freqtrade
tail -f user_data/logs/freqtrade.log
```

建议观察至少 4–8 周，因为策略使用日线和周线信号。重点检查：

- 日线收盘后是否产生预期信号
- 周线仓位调整是否正常
- 重启后交易和仓位目标是否保留
- Binance API 是否稳定
- 最小下单金额是否满足交易所要求
- 是否有交易对下架或改名

## 11. 切换到实盘

不要复用 dry-run 数据库。复制独立配置：

```bash
cp user_data/config.json user_data/config_live.json
chmod 600 user_data/config_live.json
nano user_data/config_live.json
```

修改：

```json
"dry_run": false,
"initial_state": "stopped"
```

在 `docker-compose.yml` 中将配置和数据库改为：

```yaml
--config /freqtrade/user_data/config_live.json
--db-url sqlite:////freqtrade/user_data/tradesv3.sqlite
--logfile /freqtrade/user_data/logs/freqtrade-live.log
```

启动前检查：

```bash
docker compose config
docker compose up -d
docker compose logs -f freqtrade
```

第一次实盘应使用能承受损失的小额资金，先确认真实下单、成交、手续费和退出流程。

## 12. 重要策略风险

这份策略不适合无条件十年无人监管运行：

1. `stoploss = -0.99`，没有真正的硬止损。
2. 币种快速归零时，日线退出信号可能来不及处理。
3. BTC 跌破 MA200 会让所有小币退出，可能错过小币独立上涨。
4. 没有单币仓位上限，盈利币上涨后可能占账户较大比例。
5. 服务器断网、死机或 OOM 时，策略无法管理仓位。
6. Binance 的 API、交易规则、币种和监管环境可能变化。

如果资金不能承受单币极端亏损，不要直接使用这份策略实盘。

## 13. 磁盘、内存和自动重启

`restart: unless-stopped` 只能在容器退出后重新启动，不能修复：

- 磁盘写满
- 配置错误
- 数据库损坏
- 持续 OOM
- Binance 长时间不可用

定期检查：

```bash
df -h
du -sh user_data/*
free -h
docker stats --no-stream
docker system df
docker compose ps
```

如果发现 OOM：

```bash
dmesg -T | grep -i -E 'oom|killed process'
```

优先升级到 2 GB 以上内存，而不是只增加 swap。生产机不要同时运行回测、hyperopt 和交易容器。

不要把下面命令设置成无人值守定时任务：

```bash
docker system prune -af
```

它可能删除故障恢复所需的镜像。

## 14. 数据库备份

至少备份：

- `user_data/tradesv3.sqlite`
- `user_data/config_live.json`
- `user_data/strategies/`
- `docker-compose.yml`

简单的停机备份：

```bash
mkdir -p user_data/backups
docker compose stop
cp user_data/tradesv3.sqlite \
  "user_data/backups/tradesv3-$(date +%F).sqlite"
cp user_data/config_live.json \
  "user_data/backups/config-live-$(date +%F).json"
docker compose start
```

备份必须复制到另一台机器、S3 或其他独立存储，不能只留在同一个 EBS 卷上。AWS EBS 不会自动替你创建备份，应配置 EBS Snapshot、AWS Backup 或 Data Lifecycle Manager。

## 15. 升级策略和 Freqtrade

不要自动执行 `docker compose pull`。升级流程：

```bash
cd ~/freqtrade-stable

git fetch origin
git status

docker compose stop
cp user_data/tradesv3.sqlite \
  "user_data/backups/before-upgrade-$(date +%F).sqlite"

docker compose pull
docker compose run --rm freqtrade \
  list-strategies \
  --config /freqtrade/user_data/config_live.json

docker compose up -d
docker compose logs --tail=200 freqtrade
```

升级前应阅读 Freqtrade changelog，并先在 dry-run 或备用服务器验证。

## 16. 常用运维命令

```bash
# 查看服务状态
docker compose ps

# 查看最近日志
docker compose logs --tail=200 freqtrade

# 持续查看日志
docker compose logs -f freqtrade

# 重启服务
docker compose restart freqtrade

# 停止服务
docker compose stop

# 查看容器重启次数
docker inspect -f '{{.RestartCount}}' freqtrade

# 检查内存和磁盘
free -h
df -h
```

## 17. 官方文档

- [Freqtrade Docker Quickstart](https://www.freqtrade.io/en/stable/docker_quickstart/)
- [Freqtrade Configuration](https://www.freqtrade.io/en/stable/configuration/)
- [Freqtrade Updating](https://www.freqtrade.io/en/stable/updating/)
- [AWS EBS Snapshots](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html)
- [AWS EBS CloudWatch Metrics](https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html)
