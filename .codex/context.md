# 当前上下文

更新：2026-09-18。独立仓库main，源码位于zr/doonook_chinese_calendar。

## 0.1.5已发布，正式部署待完成

- 发布代码2112947，标签v0.1.5；GitHub Actions 35303639833成功。
- PyPI正式wheel/sdist已下载验证SHA256、星历/NOTICE、无私有dotenv；wheel包含详细提示词和预生成模块。
- 本轮71项pytest通过，含独立临时PostgreSQL并发/writer验证，容器已清理。未验证新长文案真实模型耗时。
- warm-astro --days可手动补齐，maintain-astro --days 7 --interval 3600持续补齐当天起7天/12星座；先今天，旧缓存不覆盖，失败下一轮重试。
- HTTP默认ASTRO_GENERATE_ON_REQUEST=false，缺缓存503，避免请求等待模型；run_local.py隔离演示显式开启请求内生成。
- summary目标100～150字，四维度各60～100字，presummary15～30字；max_tokens6500，每字段硬限制300字符，目标字数不是硬校验。
- doonook_temp两处版本固定值已改0.1.5，Compose独立astro-prefetch服务需在模型及writer可达的唯一节点启用；包发布/代码提交不等于服务器已启动。

## 稳定边界

- 本地JPL DE440s/Skyfield → 占星编辑规则 → Qwen → JSON校验 → writer缓存。无第三方星座fallback，Jisu仅用于黄历日期接口。
- 星历随包分发；ASTRO_EPHEMERIS_PATH可覆盖。五期JSON列保留内部_basis，对外契约不变。规则是娱乐解释而非科学预测。
- 模型URL、密钥、名称注入私有配置，不能提交或写死；局域网网关可达性要在实际节点验证。
- 复用DOONOOK_NODE_ROLE/REMOTE_WRITER_HOST选writer，中国为primary；不得为了写入修改共享POSTGRES_HOST指向。
- MLX无xgrammar，使用提示词Schema+Pydantic事后校验，兼容已观察到的think标记；不保证每句符合编辑规则。
- 主后端与包是独立仓库。源码.env不随wheel分发，不能把Mac路径当部署配置。

## 下一步

- 在实际生成节点安装0.1.5，核对模型/主库连通和QWEN_TIMEOUT_SECONDS，先warm预热，再启动维护容器。
- 更新API运行镜像并验证App获取缓存响应；尚未改生产配置、写生产库或启动生成服务。
- 证据：[预生成说明](../docs/astro-prefetch.md)、[生成链路](../docs/astro-generation.md)、[任务日志](task-log.md)。
