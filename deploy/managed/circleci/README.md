# CircleCI 运行时

按需 macOS ARM64 工作机接收绑定源码、任务和角色的请求，复用公共运行包执行应用处理。

- [架构说明](../../../docs/MANAGED-RUNTIME.md)
- [维护发布流程](../../../docs/OPERATIONS.md)
- [验证与源码来源](../../../docs/VALIDATION.md)
- [CircleCI 配置](../../../.circleci/config.yml)
- [公共运行包清单](runtime-pins.json)
- [实现与迁移档案](../../../docs/archive/2026-11-27/CIRCLECI-RUNTIME.md)

开发修改在维护分支验证。生产入口开启时，分支 HEAD 必须与控制面配置一致；发布按空闲关闭、验证提交推进和同源码切换的顺序执行。
