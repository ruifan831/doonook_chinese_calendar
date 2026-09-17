# 本地 Qwen 调用与数据库结构契约

更新：2026-09-17。范围：验证本地后端调用 Mac 模型、结构化结果校验与 PostgreSQL 持久化。

## 请求链路

用户确认中国/本地两套后端并存，星座运势请求由 Cloudflare Worker 按 URL 转发到本地后端。
本次未修改或发布 Worker。需要路由的现有接口为：

`GET /api/v1/calendar/astro/{astroid}?date=YYYY-MM-DD`

本地后端 → `.env` 的 `QWEN_BASE_URL` + `/chat/completions` → Nginx → Mac Ollama。
Nginx 只允许已配置的局域网服务器来源，并验证 Bearer key。
数据库命中时直接返回；缺失时先计算本地星历与占星规则，再请求 Qwen。Jisu / Juhe 星座调用及供应商选择已移除。

本地实际运行的 API/预生成进程必须安装新版 0.1.4，
在其工作目录 `.env` 中填写 `QWEN_BASE_URL`、`QWEN_LAN_API_KEY`、`QWEN_MODEL` 和超时。
实际地址、模型名和密钥不硬编码；配置方法及文件边界见 [README](../README.md#配置-qwen)。
缺少模型配置时未缓存请求返回503，绝不回退第三方；历史缓存保留。
主后端目前仍固定依赖 0.1.3，本验证不代表线上版本已更新。

## 什么是当前的 structured data

Qwen 收到与代码校验器一致的 JSON Schema，并按提示返回 JSON 文本。
包从 OpenAI 兼容响应的 `choices[0].message.content` 提取 JSON，执行
`GeneratedFortune.model_validate_json`，再映射为数据库/接口的 `AstroFortuneSchema`。
模型输入已有代码计算的星历因素与评分，规则和边界见[生成链路](astro-generation.md)。
数据库五个JSON列内部另存 `_basis` 审计字段，API响应不包含它，无需改表。

当前 Homebrew Ollama 的 MLX 运行环境缺少 xgrammar，未启用
`response_format: json_schema` 约束解码。因此不是模型每次输出都必然有效；
保证的是**仅符合结构的结果进入数据库**。缺字段、额外字段、非字符串、空文本、
超长文本、Markdown 包裹、输出截断或超时都会失败并返回503，不保存半份结果。
错误结果不会被替换为伪造数据，不静默调用第三方供应商。
实测Ollama会泄漏 `</think>`：支持单JSON末尾标记，也支持“完整草稿JSON → 标记 → 最终JSON”。
后一种要求两个JSON均通过完整schema校验，选最终对象；解析尊重JSON字符串中的字面标记。
不截取任意JSON片段，不接受无标记的多个对象、错误草稿/最终字段或任意附加文字。

## 数据库映射

沿用原 `75c3add9cb65_initial_migration` 和 `astro_fortunes`，没有新表结构迁移。

| 数据库列 | 类型 | 来源 |
|---|---|---|
| id | INTEGER 主键 | 数据库生成 |
| astroid | INTEGER | 服务端校验1–12的请求参数 |
| astroname | VARCHAR | 服务端固定星座映射 |
| date | DATE | 请求日期，缺省按Asia/Shanghai计算 |
| year / month / week | JSON | summary、money、career、love、health；服务端补date，week补job |
| today / tomorrow | JSON | summary、money、career、love、health、presummary、star、color、number；服务端补date |

日期不由模型决定；`number` 保持字符串，兼容现有客户端。每段模型文案必填、
非空、最长300字符。API保持原始JSON模型，无新增envelope，客户端字段不变。
修复了Qwen结果经旧JiSu schema转换时丢弃 `week.summary` 的问题。

## 验证方法

- 定向测试覆盖 `.env` 加载、移除第三方切换、缺配置拒绝调用，以及真实PostgreSQL并发锁、JSON字段无损入库、协议标记兼容和坏数据不落库。
- LAN实测：在`.56`安装本次wheel并运行 `tests/smoke_qwen_lan.py`，连接Mac上的真实模型。
- PostgreSQL实测使用`.56`上独立临时容器，执行包原始迁移后写入；不连接业务数据库。
- 写入后新开数据库session，并把第二次查询的Qwen地址设为不可达，验证仍能读取完整缓存。
- 实测结果、耗时与清理状态记录在[任务日志](../.codex/task-log.md)。

早期纯Qwen链路验证：生成并写入PostgreSQL耗时23.69秒；新session、Qwen不可达时缓存读取10.8毫秒。
列类型验证为INTEGER / VARCHAR / DATE / 五个JSON列；仅保存一条完整记录。
[完整实测JSON样例](examples/qwen-fortune.json)包含保存后的id及五期全部字段。

## 部署边界

本地包与宿主读取同一份.env：`DOONOOK_NODE_ROLE=replica` 时，writer 使用
`REMOTE_WRITER_HOST` 指定的中国主库；`POSTGRES_HOST` 保持本地副本地址。
星座及黄历缓存GET、预生成、默认迁移全部走writer；缺主库地址即配置失败。
Worker转发只能决定请求去哪台后端，不能替代主库配置或Qwen环境变量。Mac离线时已缓存内容仍可读，未缓存请求会503。
首次生成可能超过现有iOS的20秒超时，上线前需安排 `warm-astro` 预生成或处理客户端等待策略。
