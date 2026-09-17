# 当前上下文

更新：2026-09-17。独立仓库 `/Users/ruifanxu/Workspace/active/zr/doonook_chinese_calendar`，main，0.1.4发布进行中。
目录已由Workspace/web整体迁入zr；旧Git、本地配置与dist保留。

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
  需要发布新版PyPI包后升级宿主依赖/pip安装（自动带星历和Skyfield依赖），配置本地replica到中国writer。
  源码.env不会随wheel分发；不能复制Mac路径当服务器配置。Worker未发布、业务库未写入。
- 分发验证：18项星历测试通过；wheel隔离安装后无外部路径/禁网计算通过，sdist重建数据完整。
  发布workflow增加分发检查与版本标签校验；用户已授权提交/发布，准备推送v0.1.4。
- 上线待办：发布PyPI、正式宿主升级/网络白名单、配置writer、安排warm-astro每日预生成。
  iOS20秒超时，生成30秒以上，当前还不能宣称App线上接入完成；独立黄历日期接口仍用Jisu。
- 证据：[日志](task-log.md)、[说明](../README.md)、[今日依据样例](../docs/examples/astro-basis-2026-09-17.json)、
  [新文案样例](../docs/examples/qwen-fortune.json)。Mac服务记录在ops/docs/ops/qwen-lan-2026-09-17.md。
