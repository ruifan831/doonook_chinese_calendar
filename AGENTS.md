# 黄历与星座 API 包

本目录是独立 Git 仓库，Python 包名 `doonook_chinese_calendar`。主后端
`../doonook_temp` 通过 Python 依赖使用本包；目录放在同一工作区不代表已升级线上依赖。

## 启动入口

开始任务前读取工作区 [AGENTS.md](../AGENTS.md)、[SOP 索引](../sop/README.md)
并打开相关规范，然后读取 [项目文档](docs/README.md)、
[当前上下文](.codex/context.md)、[最近日志](.codex/task-log.md)。
独立打开项目且共享资料不可达时，定位原工作区
`/Users/ruifanxu/Workspace/active/zr`，不能假定已读。

## 路径与约定

- `src/doonook_chinese_calendar/api/`：FastAPI 路由，保持 Android/iOS 现有响应契约。
- `services/astro_service.py`：数据库缓存与本地 Qwen 生成。
- `services/astro_prefetch.py`：顺序多日预生成与常驻补缺；HTTP默认只读缓存，部署见docs/astro-prefetch.md。
- `services/qwen_fortune.py`：Qwen 调用与 JSON 校验。
- `data/de440s.bsp` 与 `data/NOTICE.txt`：随PyPI包分发的原始星历与来源说明；发布前运行 scripts/check_distribution.py。
- `services/astro_basis.py`：离线星历与明确的占星编辑规则；依据见 docs/astro-generation.md，分数不是科学预测。
- `core/config.py` / `core/database.py`：环境配置及独立数据库连接。
- `run_local.py`：本机 Swagger + 临时 SQLite 测试入口，模型配置从私有 `.env.local` 读取。
- `tests/`：定向测试；真实模型测试 `smoke_qwen_lan.py` 仅手动执行。
- 本包 GET 运势/黄历接口会写入缓存，显式使用包内 get_db_writer。复用宿主 DOONOOK_NODE_ROLE / REMOTE_WRITER_HOST，禁止为本包修改共享 POSTGRES_HOST。模型 URL、API key、模型名放私有 `.env` 或部署环境，不能提交真实值。
- 星座只用 Qwen，禁止恢复第三方星座调用或 fallback；JISU_API_KEY 仅用于独立黄历日期接口。
- 修改包后运行相关 pytest，更新本项目 `.codex/task-log.md`；未验证的部署边界保留在 context 中。
