# Task Log

## 2026-09-17 — 提交并发布 0.1.4（发布准备）

- 用户明确授权提交并发布PyPI。核对main与origin/main一致，PyPI当前0.1.3、无0.1.4。
- 复核会话上下文、共享SDK、编码与文档SOP；本机未登录GitHub CLI，Git SSH可用。
  发布workflow改由v*标签或手动触发，校验标签等于pyproject版本，沿用仓库PYPI_API_TOKEN。
- 发布前64项pytest全部通过；PG用独立临时Docker容器，结束已清理，不接业务数据库。
- README/生成链路改为正式安装说明；实际上传结果待发布完成后补记。
  私有.env/.env.local、dist和原有.DS_Store均不纳入提交。

## 2026-09-17 — 按 PyPI/pip 流程内置星历

- 用户澄清实际通过PyPI发布、pip安装。本轮调整包分发，未上传或触发外部发布。
  已读发布workflow与共享SDK SOP；官方PyPI查询当前0.1.3、尚无0.1.4。
- 原始DE440s及来源NOTICE加入src/doonook_chinese_calendar/data，显式纳入wheel/sdist。
  星历原始SHA256不变，保留JPL内嵌说明与NAIF再分发规则链接；不随包携带私有.env或凭证。
- ASTRO_EPHEMERIS_PATH为空时默认读取安装包内数据；显式覆盖无效则失败，不自动回退。
  本机项目.env/.env.local移除旧Mac绝对路径，宿主.env不改。部署不再单独COPY/下载星历。
- 发布workflow改为poetry build→检查当前版本wheel/sdist→poetry publish；token通过Poetry环境变量注入。
  去掉打包前poetry install，避免为构建安装业务/native依赖。未执行publish或提交/推送。
- scripts/check_distribution.py校验当前版本（保留旧dist产物）的数据SHA256、NOTICE和无私有dotenv。
  新wheel约29.65MiB；wheel/sdist检查通过，sdist再次重建wheel保留原数据。
- 18项星历定向测试通过；安装wheel到临时独立目录，断网并清空星历路径后完成真实全期计算。
  实测确认导入的是安装产物而非本地src；业务依赖复用已验证venv，没有声称全新ARM机器所有依赖已验证。
- README、生成链路、模板、AGENTS更新；Black/diff检查通过。
  主后端两个0.1.3依赖pin尚未改；新版发布后再统一升级和重建镜像。sxtwl原有ARM安装限制仍存在。

## 2026-09-17 — 离线星历、占星规则与 Qwen 文案

- 按用户提出的“天文数据→占星规则→LLM”落地；保留API与表列、现有writer路由及历史缓存。
  读取项目/工作区指令、后端/API与编码SOP；搜索无占星专项规范。规则作为明确的产品编辑决策记录。
- 选用MIT Skyfield + JPL DE440s本地文件；没有引入AGPL/商业双授权的Swiss Ephemeris。
  官方授权/数据来源、SHA256、安装方式和算法边界见docs/astro-generation.md。
  新增skyfield依赖并更新poetry.lock；星历32MB放~/.local/share/qwen-calendar，不进入Git/wheel。
- astro_basis.py：地心视位置、当日真黄道/春分点、热带黄道，七个天体；五类相位与明确容许度，
  太阳整宫解释与1–5评分。今明天采用当地12点快照，周/月/年汇总完整每日采样（含闰日/跨年）。
  年份1900–2099；无文件/坏数据失败，不联网下载、不随机降级。评分为编辑规则，不是科学预测。
- Qwen输入各期分数/主导因素，温度0.3；结构严格校验；星体位置、分数不由模型产生。
  现有幸运颜色/数字/贵人星座仍是旧接口娱乐装饰，不声称有天文依据。文案语义一致性仍非硬保证。
- 五个JSON列内部保存_basis（规则版本、文件指纹、采样、分数、全部聚合因素；今明天含七星位置），
  公共Pydantic响应不包含内部依据；无表迁移，旧记录不覆盖，无_basis的旧缓存不能算新算法生成。
- run_local.py新增仅本机/debug/astro-basis/{astroid}?date=...，不调用模型/不写DB，不挂生产路由。
  项目.env和.env.local填ASTRO_EPHEMERIS_PATH；宿主doonook_temp.env、远端配置、真实PG均未改。
- 真实联调发现MLX输出“草稿JSON </think> 最终JSON”，导致503。新增严格协议兼容：两个对象都
  必须通过schema后取最终对象；拒绝错字段、无标记多对象、任意尾随文本，正文标记保持字面值。
  没有放松校验或引入自动重试。之前被拒的真实输出已回放验证。
- 62项pytest全通过（含真实离线星历、相位边界、太阳宫差异、闰年/跨年、确定性、坏文件不调用模型、
  提示依据/审计入库/响应兼容、隔离PG并发与writer、协议解析）。临时PG容器清理。
- 最终真实HTTP→星历/规则→Qwen→SQLite入库30.56s，缓存4.5ms。只读检查该测试进程SQLite文件，
  确认五列均保存规则版本和星历指纹。Swagger、依据接口可用；当前PID80946，仅本机8008。
  样例：docs/examples/astro-basis-2026-09-17.json、docs/examples/qwen-fortune.json（后者更新为新链路）。
- Black、git diff --check、wheel构建及密钥/数据打包检查通过。未发布PyPI/提交Git/切换主后端或Worker。
  .56独立环境仍是较早wheel，生产安装新版时须安装Skyfield并部署星历文件、配置服务器实际路径。

## 2026-09-17 — Mac 独立接口测试入口

- 新增run_local.py，实际挂载包路由与Swagger，默认127.0.0.1:8008；通过--env-file读取模型配置。
  使用临时SQLite覆盖get_db_writer，强制清除业务PG目标；退出后临时数据库自动删除。
- 本机新增私有.env.local（0600/Git忽略），指向回环Ollama，local-test为Ollama不验证的占位key。
  不修改宿主.env、LAN Nginx白名单或真实密钥；/tmp/qwen-calendar-venv补装uvicorn0.53.0。
- 已启动测试服务（本轮PID79129），Swagger200、非法星座422。首次模型调用HTTP200但生成校验失败，
  接口返回503；诊断重试JSON通过，最终完整HTTP→真实Qwen→SQLite入库23.44s，重复请求缓存4.4ms。
  结果见dist/local-test-fortune.json（忽略）。不放松JSON校验、不引入自动重试或修改生产逻辑。
- README加入本机启动/调用/配置边界，AGENTS加入入口；Black、git diff --check通过。
  没有重跑未改动的39项业务测试；实际接口联调用于验证该开发入口。
- 服务仅供本机操作，保留运行供用户测试；该入口不验证中国主库连通性或PG并发锁。
  主后端部署及依赖版本未变；未发布或提交。

## 2026-09-17 — 复用宿主 .env，缓存连接中国 writer

- 用户确认中国是primary、本地服务器是replica，不能修改共享POSTGRES_HOST。
  采用后端/API的写缓存GET必须走writer规则；检查doonook-common实际配置与DSN选择实现。
- CalendarSettings新增与宿主同名的DOONOOK_NODE_ROLE / REMOTE_WRITER_HOST；primary用原POSTGRES_HOST，
  replica用REMOTE_WRITER_HOST，复用POSTGRES_USER/PASSWORD/PORT/DB。副本缺主库地址即拒绝配置，
  错误展示隐藏完整输入，防止泄露.env密钥。DATABASE_URL兼容属性也指向writer，URL安全编码密码。
- 保留包现有同步SQLAlchemy服务，复用配置选择规则；未将common的AsyncSession直接注入同步代码，
  未声称共用异步连接池。新增明确的writer_engine / WriterSessionLocal / get_db_writer，
  星座和黄历缓存GET显式依赖writer，旧get_db/SessionLocal保持writer兼容别名。
- warm-astro使用WriterSessionLocal，默认迁移URL走writer；Alembic配置处理URL中的百分号转义。
  无表结构/接口字段变更，不影响宿主其他模块的reader/writer路由。
- 38项全套测试通过，包含新建隔离PostgreSQL中的原有并发锁与真实HTTP writer路由；
  本地POSTGRES_HOST故意不可达、REMOTE_WRITER_HOST指向测试primary，仍成功入库且再次命中缓存。
  补充迁移writer/特殊字符密码测试1项通过，合计39项。临时PG容器清理，未连生产库。
- Black、git diff --check、新0.1.4 wheel构建通过。说明与.env.example同步拓扑配置。
- 只读检查Mac上doonook_temp/.env：角色primary、REMOTE_WRITER_HOST未配置；不代表服务器运行值。
  未修改该.env或任何POSTGRES_HOST，未修改宿主源码/依赖、生产配置、数据库或Worker。
  上线仍需实际宿主安装新wheel；本地replica环境须配置replica角色与中国主库私网地址。
  .56独立验证环境尚未安装本轮writer修复（上轮Qwen-only wheel仍在）；未发布PyPI或提交Git。

## 2026-09-17 — 星座仅用本地 Qwen，私有 .env 配置

- 按用户要求移除星座服务的 Jisu/Juhe HTTP 调用、JUHE_API_KEY 和 ASTRO_PROVIDER 切换；
  缓存缺失只调用 Qwen，旧环境中的 ASTRO_PROVIDER=jisu 也不能重新启用第三方。
  独立黄历日期接口仍使用 Jisu，保留其 JISU_API_KEY，不改历法数据来源。
- QWEN_BASE_URL、QWEN_LAN_API_KEY、QWEN_MODEL 在代码中均无实际默认值；
  从进程工作目录 .env 读取，环境变量优先；缺配置返回503，已有缓存可继续读取。
- 本机项目 .env 已填入现有 LAN Nginx 地址、密钥、模型名，权限0600；保留原数据库与黄历配置，
  删除无效的旧星座切换/聚合key配置。增加 .env.* Git忽略和不含私密值的 .env.example。
  API key用SecretStr遮蔽；检查确认真实密钥未出现在可提交文件或wheel，.env未跟踪且不打包。
- 定向pytest：27通过、1项需隔离PostgreSQL的并发测试跳过（上轮已验证并发锁，本次未改锁机制）。
  新增默认工作目录dotenv加载、缺URL/key/model不发请求、旧provider设置不能启用第三方的测试。
  Black、git diff --check、0.1.4 wheel构建通过。
- .56独立venv更新wheel，私有 ~/.config/qwen-lan/.env 保存模型配置且权限0600；
  清除QWEN环境变量后从该目录运行真实模型测试，确认直接读取.env。
  真实Qwen→临时SQLite完整字段校验入库19.36s；新session断开模型仍命中缓存6.5ms，仅一条记录。
  测试不读取业务数据库配置、不修改业务数据；临时SQLite自动清理。
- 主后端仍固定0.1.3，未修改生产进程.env/部署镜像/Worker，也未发布PyPI或提交Git。
  宿主实际升级后需把Qwen配置合并到其运行目录.env（源码目录.env不会随wheel自动部署）。

## 2026-09-17 — 本地模型到 PostgreSQL 结构契约实测

- 用户确认中国/本地双后端，计划自行用Cloudflare Worker将星座URL统一转发本地；
  本轮仅验证包的局域网Qwen调用和数据库结构，不改Worker、生产主API或业务数据库。
- Qwen提示直接附GeneratedFortune的JSON Schema；保持服务端严格验证，明确MLX当前缺少
  xgrammar，不能声称使用原生约束解码或每次模型输出必然成功。
- 实测模型响应JSON末尾夹带</think>，严格解析拒绝且PostgreSQL记录数为0；
  增加仅去除末尾协议标记的兼容，坏字段/正文/附加文字不绕过验证。
- 修正Qwen结果经JiSu schema丢失week.summary，直接映射AstroFortuneSchema并保留全部五期字段。
- 25项测试通过（含隔离PostgreSQL并发、字段无损入库、坏JSON不落库、标记兼容）；
  Black、git diff --check、wheel构建通过。
- .56独立venv安装最新0.1.4 wheel，独立PostgreSQL15容器执行包原始迁移后完成
  真实Qwen生成+入库23.69s。新session把Qwen地址改为不可达仍读取缓存，10.8ms，数据库仅1条。
  列类型INTEGER/VARCHAR/DATE/JSON与五期非空字段通过。测试临时容器清理，不触碰业务库。
- 结果样例[docs/examples/qwen-fortune.json](../docs/examples/qwen-fortune.json)，
  [完整结构契约](../docs/qwen-data-contract.md)。部署仍需主后端升级0.1.4、显式ASTRO_PROVIDER=qwen、
  注入密钥并连接writer；原有0.1.3线上依赖未更改，未发布PyPI或提交Git。

## 2026-09-17 — 整体迁入 zr 工作区

- 按用户要求从 `/Users/ruifanxu/Workspace/web/doonook_chinese_calendar` 移至
  `/Users/ruifanxu/Workspace/active/zr/doonook_chinese_calendar`；未保留旧目录或软链接。
- 移动前后核对250个文件/软链接的内容摘要和权限，Git HEAD及完整工作区状态一致；
  `.git`、`.env`、未提交Qwen代码、dist和编辑器设置完整保留，未输出凭证内容。
- 更新当前上下文、添加工作区规范入口AGENTS和docs索引；根工作区加入项目地图及日志路由。
- 本次验证用的 `/tmp/qwen-calendar-venv` editable安装已更新到新路径；确认Python定位到新源码，
  新文档链接与git diff --check通过。目录迁移没有重跑业务测试。
- 仅迁移路径及维护文档，未改业务逻辑或部署服务，未提交Git。

## 2026-09-17 — 星座运势接入局域网 Qwen

- 实际包名 doonook_chinese_calendar，独立源码位于 Workspace/web；main，原有未跟踪 .DS_Store 保留。
  沿用 zr 工作区的会话上下文、后端/API、代码、文档规范；原项目没有 AGENTS、docs 或任务日志。
- 增加可配置 Qwen provider，默认 jisu 保持旧部署兼容；显式启用后只使用 Qwen，失败不回退第三方。
  星座日期由代码控制，生成 JSON 严格校验后才保存，保留现有响应字段和原始响应形式。
- 数据库缓存 + PostgreSQL 非阻塞事务 advisory lock 避免多 worker 重复生成，失败/取消释放锁；
  旧缓存优先，包括旧供应商结果。独立包的数据库必须指向 writer。
- 修正路由默认日期在进程导入时固定的问题，增加星座/日期入参验证和模型失败503；
  增加顺序 warm-astro 命令以便提前生成，不自动执行定时任务或覆盖业务数据。
- 版本升为0.1.4，声明原来漏掉的httpx依赖，更新poetry.lock，构建wheel。
  包入口改为工厂调用时加载路由，便于独立生成器使用；未修改农历算法。
- .56已在独立venv安装wheel；原有sxtwl2.0.7的ARM sdist缺少源文件，
  从官方提交7598b0601a76cfdaa9266257b1b5690720c1e2ce构建本机和Linux ARM二进制，远端uv pip check通过。
- 真实Qwen+临时SQLite生成白羊座2026-09-17完整五期运势：30.02秒；再次命中缓存6.6毫秒，仅一行。
  示例保存在远端~/.config/qwen-lan/sample-fortune.json；未连接生产数据库。
- 最终21项pytest通过，包括隔离PostgreSQL中6个并发请求仅一次生成、HTTP响应契约、
  旧provider兼容、配置缺失、鉴权/限流/超时/截断/错误JSON、取消不落库、日期和星座校验。
  Black、git diff --check、wheel构建通过；原有Pydantic/SQLAlchemy弃用提示保留。
- 尚未发布PyPI/提交Git/部署App后端；主后端仍固定0.1.3。现有iOS20秒超时，需上线前预生成。
  已询问用户实际API部署目标；具体边界见README和context。
