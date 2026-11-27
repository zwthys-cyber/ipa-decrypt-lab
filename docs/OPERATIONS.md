# 维护手册

本文面向维护者。日常机器人操作见[使用指南](TELEGRAM.md)，组件分工见[架构说明](MANAGED-RUNTIME.md)。

## 分支职责

| 分支 | 用途 |
| --- | --- |
| `upgrade/managed-runtime-v0.2` | 生产处理源码，HEAD 必须与控制面配置一致 |
| `upgrade/managed-runtime-maintenance-v0.2` | 修改、文档整理与 CI 验证 |
| `main` | 默认入口、账号维护及历史 Intel 发行工作流 |

文档整理可以留在维护分支，并同步 main 的阅读入口。生产入口开启时，不直接向生产分支追加提交。

## 发布流程

1. 在维护分支准备修改，运行相关 GitHub 检查。
2. 涉及控制面时，取得与候选源码一致的成功 `circleci-control-contracts.yml` 产物。
3. 运行 `circleci-maintenance-close.yml`，指定当前生产源码及其成功 control run。存在活动任务时停止切换。
4. 核对关闭回执，以原生产 HEAD 为 lease，将已验证的维护 commit 快进到生产分支。
5. 运行 `circleci-offline-cutover.yml`，确认同一源码的历史状态读回、webhook 和真实定时触发。
6. 保持生产 HEAD 固定。后续说明和证据写入维护分支，部署来源以成功回执为准。

项目构建、测试和执行只在 GitHub 或已授权的 CircleCI 进行。本工作区不创建项目 checkout，也不运行项目测试。源码通过 GitHub API 修改。

## 凭据维护

| 项目 | 维护要求 |
| --- | --- |
| `MANAGED_TELEGRAM_BOT_TOKEN` | 当前机器人凭据，与历史 Token 分开保存 |
| `MANAGED_TF_HMAC_KEY` | 稳定密钥，历史接受去重依赖它，不随部署重建 |
| Apple 账号、GUID、模型及 checkpoint | 使用既有材料；会话维护单独执行，不借普通任务自动重登或注册电脑 |
| 交付身份与 Drive 刷新凭据 | 保留在既定控制环境，工作机只获得所需短期权限 |

五个已停用的历史派发/目录工作流继续停用。不要通过重建意图库、替换模型或重新生成密钥解决未知结果。凭据值、原生响应及私有链接不进入公开日志或源码。

## 公共运行包

普通任务加载 `runtime-pins.json` 固定的公共包，核对生产者、归档摘要、文件摘要、原生输入及主机 ABI。修改 tools、tests、.github/ops 或其他原生构建合约目录后，需要重新验证包来源。

macOS 私有子进程同时固定 HOME 和 CFFIXED_USER_HOME，保证原生工具使用隔离的账号缓存。

## 运行检查

- 以成功 cutover 收据和 readiness 回读确认源码、webhook 及定时触发。
- 提交额度由 `RUNTIME_DAILY_LIMIT` 控制，未配置时每 UTC 日 3 次，包含失败与取消；允许配置到 20。
- 等待队列最多 30 条，实际处理串行。目录查询有独立的频率和每日上限。
- /status 读取分组快照，定时触发负责外部状态核对；不为每个列表项重复调用完整核对流程。
- 文件领取窗口当前为注册后 24 小时。窗口结束不自动撤销 Drive 权限或删除文件。

## 故障处理

先确定失败阶段，再选择对应检查。账号缓存路径、会话拒绝、地区许可、模型不匹配和文件核验失败需要分别处理，诊断方法见[认证诊断](AUTH-COMPATIBILITY.md)。

外部提交、邀请接受或通知结果不明时，保留原意图并核对已有运行。取消必须等后台终止确认后再释放容量。确认过的文件和通知不自动重发。

历史交接记录及两条 held 任务继续保留，源缺口保持明确标记。相关规则见[任务恢复](SESSION-RECOVERY.md)，当前验收范围见[项目状态](PROJECT-STATUS.md)。
