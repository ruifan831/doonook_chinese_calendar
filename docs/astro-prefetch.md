# 星座运势预生成

当前版本：0.1.5，已于2026-09-18发布PyPI，尚未部署。现有 0.1.4 只有单日期 warm-astro，
不支持本轮 --days、maintain-astro 或只读缓存开关。

## 运行边界

- 在能访问 Qwen 与数据库 writer 的服务器上运行一个专用进程，不在每个 FastAPI worker 中启动。
- 宿主仍通过既有 GET 读取相同响应；默认缓存缺失立即503，不让客户端等待模型。
- 复用宿主工作目录 `.env` 和原有 QWEN_* / POSTGRES_* / 节点角色配置。
  不修改 POSTGRES_HOST 指向；replica 通过 REMOTE_WRITER_HOST 写中国主库。
- 数据是公开共享星座内容，不使用用户生日、身份或 App 专属生成队列。
- 后台顺序执行，继续复用已有 PostgreSQL 事务锁，避免同星座/日期并发重复入库。
- 失败不保存空内容、不回退第三方；已完成记录保留。单条异常仅记录日期和编号，不打印密钥或连接串。

## 上线顺序

1. 在专用预生成环境安装已发布的 0.1.5，使用与实际 API 相同的 writer 配置。
2. 在实际宿主工作目录执行 `doonook-calendar warm-astro --days 7`。
   完成摘要 `ready=84 failed=0` 表示7天/12星座全部可读取，ready 包含已有缓存。
   部分失败时仍继续其他项、命令最终退出1；修复模型连接等问题后重跑，仅补缺。
3. 安排 `doonook-calendar maintain-astro --days 7 --interval 3600` 常驻运行。
   每轮结束后等一小时，重新计算 TIMEZONE 当天日期，再扫缺失记录。
4. API 安装同一版本，设置 `ASTRO_GENERATE_ON_REQUEST=false` 后重启。
   先预热再切换，避免初次上线时所有请求都快速返回缺数据。
5. 用真实 GET 检查12星座当天响应，验证重启预生成进程后不会重复调用模型。

仅本机临时SQLite的 run_local.py 显式启用请求内生成，便于测试模型；不代表生产默认。
若必须临时恢复旧行为，可设置 ASTRO_GENERATE_ON_REQUEST=true 并重启API，但仍可能超时。

## 进程监管示例

以下 systemd 服务仅为模板，替换 User、WorkingDirectory 和可执行路径为服务器实际值，
不要把占位值或 Mac 路径直接部署。工作目录内应有权限受限的宿主 `.env`；若宿主通过
容器环境变量注入配置，则用同一配置来源启动独立 worker 容器。

```ini
[Unit]
Description=Almanac astrology cache prefetch
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_SERVICE_USER
WorkingDirectory=/YOUR/HOST/WORKING_DIRECTORY
ExecStart=/YOUR/VENV/bin/doonook-calendar maintain-astro --days 7 --interval 3600
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=60
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
```

将调整后的模板保存为 `/etc/systemd/system/almanac-astro-prefetch.service` 后，
执行 `systemctl daemon-reload` 和 `systemctl enable --now almanac-astro-prefetch`。
通过 `journalctl -u almanac-astro-prefetch` 查看 ready/failed/complete 日志。
只部署一个监管实例；不要同时叠加 cron、多个副本或在全部Web worker中启动。
进程退出时已提交记录保留，重启会重新扫描；失败项会在下一轮重试。

## 覆盖范围与验收

- 默认窗口为当天起7天，每日12条记录，各自包含五个时段。
- 历史查询/超出未来窗口：用 `warm-astro --date YYYY-MM-DD --days N` 明确补齐。
  暂未实现 HTTP 缺失自动入队，不返回虚假的“已加入队列”提示。
- 旧内容不覆盖，不清理旧记录，不修改现有五期文案跨日期可能不一致的语义。
- 模型离线不影响已有缓存；连续离线直到窗口耗尽后，缺数据接口会503，后台仍继续尝试。
- 验收应包含：跨日滚动、单条失败继续、重跑不重生成、无缓存HTTP不调用模型、
  有缓存HTTP原样返回、worker终止释放session及线上真实数据覆盖率。
