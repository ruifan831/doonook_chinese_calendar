# 当前上下文

更新：2026-09-18。独立仓库 `/Users/ruifanxu/Workspace/active/zr/doonook_chinese_calendar`，main。
0.1.4已发布PyPI，代码提交63fe17e，标签v0.1.4；main后续文档提交记录验收结果。
目录已由Workspace/web整体迁入zr；旧Git、本地配置与dist保留。


## 当前任务：0.1.5 预生成（本地完成，未发布）

- 9月18日增加详细文案提示：summary 100～150字、四维度各60～100字，短提示15～30字；
  max_tokens=6500，仍每字段最多300字符；41项定向测试通过、1项PG测试跳过。
  未实测新文案耗时/质量；已有dist早于此次提示修改，发布前必须重新构建。

- 新增 warm-astro --days、maintain-astro --days 7 --interval 3600；先当天12星座再未来日期，
  单条失败继续、下轮补缺，已有缓存不覆盖，复用原writer与事务锁。
- HTTP默认 ASTRO_GENERATE_ON_REQUEST=false，仅查缓存；缺失立即503，不等待模型。
  本机隔离模型演示 run_local.py 显式开启旧请求内生成；正式服务建议保持false。
- 验证：71项pytest全通过，含临时独立PostgreSQL并发/主库路由；测试容器已清理。
  wheel/sdist 0.1.5本地构建和分发检查通过，内置星历/NOTICE完整、无私有dotenv。
- 未修改服务器配置或生产库，未提交/推送/发布；不能声称线上任务已启动。
  主后端本地固定依赖已更新至0.1.5并增加独立Compose服务，仍需发布与部署。
- 下一步：发布/安装0.1.5到实际生成环境，先warm-astro补齐，再监管启动maintain-astro，
  API升级并保持只读缓存；部署路径/主库/模型连接需在实际节点核对。
- 运维与验收：[预生成说明](../docs/astro-prefetch.md)。下面保留0.1.4已验证的模型与分发背景。

- 目标：星座请求由用户的Cloudflare Worker转发本地服务器，本地调用Mac Qwen；中国为数据库primary。
- 当前链路：本地JPL DE440s/Skyfield → 太阳星座占星编辑规则 → Qwen → JSON校验 → writer缓存。
  规则、授权、采样/评分局限见[生成链路](../docs/astro-generation.md)。评分不是科学预测或个人本命盘。
- 已实现：七星位置、五相位、太阳整宫、固定日中午采样与周/月/年全期汇总、规则评分；
  五个既有JSON列存内部_basis，API字段不变。旧缓存不覆盖，旧记录不属于新算法。
- 模型：Mac Qwen3.8-27B，Ollama回环11434；Nginx LAN入口允许.56且验Bearer key。
  URL/key/model从私有.env读。Skyfield默认读pip包内DE440s，ASTRO_EPHEMERIS_PATH仅可选覆盖，
  无运行时下载或第三方星座API。原始星历与NOTICE纳入wheel/sdist，包约29.65MiB。
  当前MLX缺xgrammar；严格Pydantic校验保障入库结构，不能保证模型每句与规则一致。
  支持已观察到的末尾</think>或完整草稿JSON→标记→完整最终JSON；两对象都须过schema。
- 数据库：同步SQLAlchemy，复用宿主DOONOOK_NODE_ROLE / REMOTE_WRITER_HOST选择writer；
  不改POSTGRES_HOST。星座/黄历缓存GET、预生成、默认迁移走writer；副本缺主库地址即报错。
- 配置：本机项目.env与.env.local已填模型配置（0600/Git忽略），旧外部星历路径已删除，默认用包内数据。
  Mac的doonook_temp/.env是primary且未填REMOTE_WRITER_HOST；不是服务器运行配置的证明，未修改。
- 本机测试：run_local.py，http://127.0.0.1:8008/docs；本轮PID80946，后续须核验是否仍运行。
  使用临时SQLite，不接业务PG；有本机专用/debug/astro-basis接口。重启清空测试缓存。
- 最新验证：64项全通过，含包内离线真星历、规则、提示、schema、审计入库、隔离PG并发/writer。
  真实HTTP新链路生成30.56s、缓存4.5ms，五列_basis核验通过；wheel已重建。
- 部署尚未切换：主后端仍固定0.1.3；.56独立venv仍是较早0.1.4，无本轮writer/星历升级。
  需要升级宿主依赖/pip安装0.1.4（自动带星历和Skyfield依赖），配置本地replica到中国writer。
  源码.env不会随wheel分发；不能复制Mac路径当服务器配置。Worker未发布、业务库未写入。
- 分发验证：18项星历测试通过；wheel隔离安装后无外部路径/禁网计算通过，sdist重建数据完整。
  发布workflow通过，PyPI实际wheel/sdist下载后校验SHA256、星历、NOTICE、无私有dotenv均通过。
  PyPI wheel隔离安装后，使用测试配置并禁网完成全部五期星历计算；业务依赖复用验证venv。
  [PyPI 0.1.4](https://pypi.org/project/doonook-chinese-calendar/0.1.4/)、
  [发布流水线](https://github.com/ruifan831/doonook_chinese_calendar/actions/runs/35184523671)。
- 上线待办：正式宿主升级/网络白名单、配置writer、安排warm-astro每日预生成。
  iOS20秒超时，生成30秒以上，当前还不能宣称App线上接入完成；独立黄历日期接口仍用Jisu。
- 证据：[日志](task-log.md)、[说明](../README.md)、[今日依据样例](../docs/examples/astro-basis-2026-09-17.json)、
  [新文案样例](../docs/examples/qwen-fortune.json)。Mac服务记录在ops/docs/ops/qwen-lan-2026-09-17.md。
