# Doonook Chinese Calendar

黄历与星座运势 FastAPI 包。0.1.4 星座运势使用本地星历、规则引擎和 Qwen 生成；黄历、农历和节假日逻辑保持原实现。

## 星座生成流程

`GET /api/v1/calendar/astro/{astroid}?date=YYYY-MM-DD` 的响应仍是原始
`AstroFortuneSchema`，没有新增 envelope；包含 today、tomorrow、week、month、year。
已核对黄历通 Android/iOS 的字段模型。

1. App 请求只读取 `astro_fortunes` 的星座/日期缓存，保留原响应格式和历史记录。
2. 默认 `ASTRO_GENERATE_ON_REQUEST=false`，缺失立即返回 503 + Retry-After，不调用或等待模型。
3. 独立预生成进程按“当天全部星座，再下一天”的顺序计算星历并调用 Qwen。
4. 后台生成沿用 PostgreSQL 星座/日期事务锁、二次缓存检查和完整 JSON 校验；成功才入库。
5. 单条失败不影响其他星座；下一轮重试缺失项，已生成记录不覆盖。

仅调试或迁移时可显式设置 `ASTRO_GENERATE_ON_REQUEST=true` 恢复请求内生成；
这会再次承担模型延迟，不建议在 App 的正式查询进程启用。

模型收到与校验器一致的JSON Schema；当前MLX环境未启用约束解码，结构保证由服务端校验实现。
完整字段映射与中/本地后端路由边界见[数据库契约](docs/qwen-data-contract.md)。

计算方法、评分规则、授权和部署见[星历生成链路](docs/astro-generation.md)。
五个现有JSON列内部保存 `_basis` 审计依据，公共响应仍沿用原字段。
没有数据库表列变更。旧记录不会被覆盖；同星座/日期的旧重复记录优先取最早记录。
同星期/月/年的文案仍按原表结构存于每日记录，不保证跨日期文本逐字一致。

## 配置 Qwen

星座运势已移除 Jisu / Juhe 调用和供应商切换，不再需要 `ASTRO_PROVIDER`。
URL、API Key、模型名均无代码默认值；预生成进程缺少任一配置时无法生成，已有缓存仍可读取。

实际配置写入 **API / CLI 进程工作目录下的 `.env`**，模板见 [.env.example](.env.example)：

```dotenv
QWEN_BASE_URL=填写本地模型的Nginx地址并以/v1结尾
QWEN_LAN_API_KEY=填写Nginx的Bearer密钥
QWEN_MODEL=填写Ollama模型名称
QWEN_TIMEOUT_SECONDS=120
ASTRO_GENERATE_ON_REQUEST=false
TIMEZONE=Asia/Shanghai
ASTRO_EPHEMERIS_PATH=
```

本机项目 `.env` 已填入现有部署值，权限为 `600`；`.env` 和 `.env.*` 均被 Git 忽略，
只提交无地址/密钥的 `.env.example`。配置不随 Python wheel 分发，也不返回给客户端。
Key 使用 `SecretStr`，普通配置对象展示会遮蔽它。环境变量优先于 `.env`；修改文件后重启进程生效。

包安装到主后端后，读取的是**主后端进程工作目录的 `.env`**，不会自动读取本源码目录的文件。
容器可通过 `--env-file /安全路径/.env` 注入；不要把 `.env` 复制进镜像或静态资源目录。
数据库沿用部署的 `POSTGRES_*`，部署时将 Qwen 四项加入现有宿主 `.env`。
`ASTRO_EPHEMERIS_PATH` 留空即可使用随pip包安装的星历文件，仅在替换数据文件时填写。

局域网服务器另有私有配置 `~/.config/qwen-lan/.env`，用于独立模型验证；
从该目录运行时自动加载，手动测试也可通过 `TEST_QWEN_ENV_FILE` 指定绝对路径。
Qwen 只接收星座和日期，不发送用户身份或生日。Nginx 保留已有来源白名单和 Bearer 鉴权，
因此当前配置用于获准的本地服务器调用 Mac；在 Mac 源码目录执行网络调用不等于已获白名单许可。
Ollama 本身不要求 API key，这里的 key 是 Nginx 的访问凭证。

`JISU_API_KEY` 仅保留给独立的黄历日期接口；该接口未改为模型生成。

## 复用 doonook_temp 的 .env 与中国主库

无需修改 `POSTGRES_HOST`，也不需要单独给包复制一份 `.env`。在 `doonook_temp`
目录启动宿主时，包直接读取同一份 `.env`；容器部署继续由宿主的 env_file 注入。
本包沿用 `doonook_common` 的节点角色与主库地址规则，保留现有同步 SQLAlchemy 会话：

| 部署节点 | DOONOOK_NODE_ROLE | POSTGRES_HOST | REMOTE_WRITER_HOST | 本包数据库连接 |
|---|---|---|---|---|
| 中国 primary | primary | 中国节点本地 PG | 不使用 | POSTGRES_HOST |
| 本地 replica | replica | 本地只读副本，保持原值 | 中国主库的 WireGuard 地址 | REMOTE_WRITER_HOST |

本地服务器的宿主 `.env` 使用：

```dotenv
DOONOOK_NODE_ROLE=replica
REMOTE_WRITER_HOST=填写中国主库的WireGuard地址
# POSTGRES_HOST 保持原值；POSTGRES_USER/PASSWORD/PORT/DB 沿用宿主配置
# QWEN_BASE_URL / QWEN_LAN_API_KEY / QWEN_MODEL 同样放在这份 .env
```

副本角色缺少 `REMOTE_WRITER_HOST` 时配置加载失败，不会退回本地副本。
不要把中国 primary 的部署文件原样当成本地 replica 的文件；Mac 开发环境的节点角色也不代表服务器配置。
环境变量优先于文件，修改部署配置后需重启。

`/astro/{astroid}` 与 `/daily` 虽是 GET，均可能写数据库缓存，所以显式使用包内
`get_db_writer`。查询、锁、生成后的写入与回读始终连接同一主库，避免副本延迟造成重复生成。
`warm-astro` 和默认迁移地址也指向 writer。包内保留 `get_db` / `SessionLocal` 兼容别名，
均指向 writer；不引入按 GET 自动分配 reader 的规则。其他宿主模块的读写路由不受影响。

本次是复用宿主**配置规则**，没有把 `doonook_common` 的异步 `AsyncSession` 直接传入同步服务。
响应与表结构不变，无需客户端改动；依然需要在实际宿主安装更新后的 wheel 才能生效。
共享公开星座内容不新增 App 专属业务配置或跨 App 数据。

## 延迟与提前生成（0.1.5）

已把 HTTP 查询和模型生成分开。详细配置、监管进程与上线顺序见
[预生成运维](docs/astro-prefetch.md)。以下命令需安装包含本轮改动的 0.1.5，不能直接用于旧 0.1.4。

```bash
# 首次补齐：今天起连续7天，全部12星座，84条每日记录。
doonook-calendar warm-astro --days 7
# 常驻维护：每轮完成后等待一小时，按最新北京时间补齐未来7天。
doonook-calendar maintain-astro --days 7 --interval 3600
# 补指定日期/星座，单次命令支持 --date / 多个 --sign。
doonook-calendar warm-astro --date 2026-09-17 --days 2 --sign 1 --sign 2
```

每条记录含今日、明日、周、月、年五期内容；7天不是7次模型调用，而是最多84次。
单条约30秒时首次一轮约42分钟，仅为估算。滚动窗口以后通常每天新增12条；
已有内容直接读缓存。单条失败继续；warm-astro 有失败则非零退出，maintain-astro 下一轮补齐。
当前/未来窗口之外的日期可通过 warm-astro 手动补齐，HTTP 不自动排队任意历史日期。
常驻进程需由 systemd 或容器监管；包发布不会自动安装或启动服务器任务。

## 安装与宿主接入

当前已发布版本为0.1.5（2026-09-18），可通过pip升级使用预生成与详细文案。
Skyfield依赖由pip安装，JPL星历随wheel/sdist内置，无需单独部署星历或为它编译C程序。
构建/发布时执行 `python scripts/check_distribution.py` 检查数据完整性与私有配置排除。

源码：`pip install -e .`。本地构建的 wheel：
`dist/doonook_chinese_calendar-0.1.5-py3-none-any.whl`。

`doonook_temp` 的运行依赖和 `Dockerfile.base` 仍固定 0.1.3。
正式接入本轮功能需在明确的部署目标中统一升级依赖、安装 0.1.5、
重建基础镜像，注入上面的环境变量，预生成数据后验证现有 `/calendar/astro` 接口。
发布流程由匹配包版本的 `v*` 标签触发，或从 GitHub Actions 手动执行；先检查分发包，再上传 PyPI。

Apple Silicon / Linux ARM 上，现有依赖 `sxtwl==2.0.7` 的 PyPI sdist 缺少 C++ 源文件。
本次从官方 `yuangu/sxtwl_cpp` 提交
`7598b0601a76cfdaa9266257b1b5690720c1e2ce` 的 `python/` 目录构建，
Linux ARM wheel 在隔离 Docker Python 3.11 环境生成，没有在服务器安装编译器。
目标系统须验证 ABI；本次 Linux ARM wheel 仅在 Ubuntu 25.04 / Python 3.11.16 验证。

## 在 Mac 上启动接口测试

独立入口 [run_local.py](run_local.py) 会启动完整日历路由与 Swagger。
它使用临时 SQLite 覆盖路由数据库依赖，退出后删除；不会连接 `.env` 中的业务 PostgreSQL。
该模式验证真实 Qwen → HTTP 接口 → JSON 校验 → 缓存，不验证 PostgreSQL writer 路由或跨进程并发锁。

本机已准备 `/tmp/qwen-calendar-venv` 和被 Git 忽略的 `.env.local`，从本项目目录启动：

```bash
/tmp/qwen-calendar-venv/bin/python run_local.py --env-file .env.local --port 8008
```

打开 `http://127.0.0.1:8008/docs`，选择 `GET /api/v1/calendar/astro/{astroid}`，
点击 Try it out，填星座编号1–12和可选日期（YYYY-MM-DD），再 Execute。命令行也可测试：

```bash
curl --max-time 150 'http://127.0.0.1:8008/api/v1/calendar/astro/1?date=2026-09-17'
```

`.env.local` 的 URL 指向 Mac 本机 Ollama 回环接口；不经过仅允许局域网服务器访问的 Nginx。
其中 `QWEN_LAN_API_KEY=local-test` 仅满足客户端必填校验，Ollama 不校验这个占位值。
该文件只用于本机调试，不要拿它替换服务器的 Nginx 地址/真实密钥配置。
脚本仅读取选定文件中的模型及日历 API 配置，数据库设置强制替换为隔离测试会话。
测试文件的 `JISU_API_KEY` 留空；本轮联调的是星座接口，第三方黄历接口需单独有效配置。

热模型生成通常需20–30秒，冷启动可能更久；同日期同星座再次请求命中缓存。
模型输出未通过校验时返回503且不写入，可再次Execute；不同日期/星座会重新生成。
终端 Ctrl+C 停止，重启后临时缓存清空。脚本只监听127.0.0.1，默认单进程。
测试环境位于 `/tmp`，被清理后需重建 Python 3.11+ 环境，安装本包和 `uvicorn`；
ARM 的 sxtwl 安装限制见上方安装说明。

## 验证

测试显式覆盖数据库配置，禁止使用开发者 `.env` 中的业务数据库：

```bash
pytest -q tests
# PostgreSQL 并发测试需一次性独立测试库；测试会创建并删除 astro_fortunes
TEST_CALENDAR_DATABASE_URL=postgresql://test:test@127.0.0.1:独立测试端口/calendar_test pytest -q tests
```

`tests/smoke_qwen_lan.py` 是手动真实模型测试，使用临时 SQLite，不访问业务数据库；
设置 `TEST_QWEN_ENV_FILE` 指向私有 `.env` 后执行。生成示例存于执行用户的
`~/.config/qwen-lan/sample-fortune.json`。
可通过 `TEST_CALENDAR_DATABASE_URL` 指向本机空的独立 `qwen_contract_test` PostgreSQL库，
脚本会执行原始迁移、写入模型数据并验证断开模型后的跨session缓存读取；拒绝已有表的库。

实施记录见 [.codex/task-log.md](.codex/task-log.md)，当前上线边界见
[.codex/context.md](.codex/context.md)。
