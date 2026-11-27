# 当前运行与维护手册

核对日期：2026-11-27。生产处理版本 `185a52110922e0f67ac2c7dff4e1fa85b3b4c98e` 已通过 CircleCI75 真实国区任务和 [45918215266](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918215266) 切换检查。此后维护分支的文档提交不是新的生产部署；精确运行源码以最近成功的 cutover 收据和控制面 readiness 回读为准。

## 组件与源码

| 组件 | 当前职责 | 入口 |
| --- | --- | --- |
| Cloudflare Workers / D1 | 原机器人 webhook、主人校验、持久任务与意图、串行派发、定时核对、Drive 校验、私聊通知 | [控制入口](../deploy/managed/circleci/runtime-api.mjs)、[机器人入口](../deploy/managed/circleci/runtime-telegram.mjs) |
| CircleCI macOS ARM64 | 按任务启动；恢复短期角色凭据，下载、模型复用、完整验证及私有上传 | [工作机](../deploy/managed/circleci/managed_worker.py)、[配置](../.circleci/config.yml) |
| GitHub Actions | 无凭据公共构建/测试；经过 OIDC 绑定的短期凭据签发；受控维护切换 | [凭据签发](../.github/workflows/circleci-secret-lease.yml)、[切换](../.github/workflows/circleci-offline-cutover.yml) |
| 私有 Google Drive | 保持主人文件的私有权限，由控制面核对归属、名称、大小和 SHA-256 | [验证模块](../deploy/managed/circleci/runtime-drive.mjs) |
| main 的既有维护工作流 | 原账号会话维护、Intel 构建和旧公开发行包 | [国区会话检查](../.github/workflows/china-session-check.yml) |

只有配置主人的私聊可以提交新任务。当前没有旧白名单管理、VPS 常驻 poller、本地 Bot API 大文件传输或五秒计时进度卡。/status 按组读取D1快照，每页3项，翻页更新原消息，外部状态由 cron 核对；排队和传输速度不保证。

## 维护发布顺序

1. 在 `upgrade/managed-runtime-maintenance-v0.2` 修改并检查；不得直接改开启中的生产分支。
2. 在 GitHub 执行相关测试。涉及控制端时生成与候选源码一致的成功 `circleci-control-contracts.yml` 产物。纯文档整理可留在维护分支并同步默认分支的导航，不必切换生产。
3. 运行 `circleci-maintenance-close.yml`，输入**旧生产源码**和对应的成功 control run。它使用旧包关闭空闲入口并保留原 source、D1 与 Secrets；存在活动任务则停止。
4. 核对关闭回执后，以旧 HEAD 为 lease，将已验证维护 commit 快进到 `upgrade/managed-runtime-v0.2`。
5. 运行 `circleci-offline-cutover.yml`。必须验证该源码自己的 webhook/cron、历史读回及持有状态；不能用上一版的 cron 时间放行。
6. 成功后冻结运行分支 HEAD。文档或收据补充写在维护分支；生产源码证据来自成功运行，不靠再补一条生产提交。

CircleCI75 使用的公共 base/CN/TF 包来自 pins 中的 job62，当前原生输入合约仍匹配。文件只因名字“旧”就删除，可能使原生输入指纹失配、迫使重编译或破坏兼容性。[固定来源](../deploy/managed/circleci/runtime-pins.json) · [输入合约](../deploy/managed/circleci/fetch_runtime.py)。

## 凭据和会话

- `MANAGED_TELEGRAM_BOT_TOKEN` 是原机器人的新 Token；与旧 `TELEGRAM_BOT_TOKEN` 分开。旧 Token 已拒绝，五个旧派发/目录工作流保持停用。
- `MANAGED_TF_HMAC_KEY` 是稳定控制密钥；不能重新生成，否则历史接受去重失去一致性。
- GitHub 保存 Apple 账号、模型和既有交付私钥；CircleCI 仅接收绑定 source/run/job/profile、短时有效的角色信封，不能取得交付主私钥或 Drive 刷新凭据。真实处理时 Apple 明文只在相应 CI 临时环境出现。
- 国区普通任务仅恢复原会话/GUID/模型/checkpoint；不自动密码登录、获取新验证码、注册电脑或更换身份。2026-11-27 的单独会话维护已完成，不是今后任意登录的持续授权。
- macOS 私有子进程同时固定 HOME 与 CFFIXED_USER_HOME，避免 Foundation 回到系统用户目录；缓存退出时清除。
- 不在聊天、公开日志或源码里提交 Token、账号、模型、原生响应、私有文件 ID 或领取链接。

## 领取、取消和未知结果

完成通知是私有 Drive 链接，原生完整性校验和控制面文件归属/权限/摘要检查都必须通过。领取窗口目前为注册后 24 小时；窗口结束不自动撤销 Drive 权限，也不证明文件已删除。不能将私有文件改成公开来绕过访问问题。

/cancel 必须带 `pilot_` 任务编号，已完成文件不能按未完成任务取消。取消意图先写入，已终止的外部工作才能释放串行容量。外部提交、TF 接受或通知结果不明时保留 unknown，不重复 POST、不自动重试；确认通知也不自动再发。

当前下载提交额度由 RUNTIME_DAILY_LIMIT 控制，未配置时为每 UTC 日 3 次（含失败/取消），上限配置允许 20；等待队列最多 30 条，实际工作串行。不要把旧白名单“每人3次、全服务20次”直接当作新入口配置。目录查询另有频率/每日限制。

## 已恢复的历史与剩余验收

29 条旧任务、89 条 updates、14 条 metadata 原样读回；2 条旧 pending 和保全快照后的未知变化保持 held。source_disabled_verified=false，代表无法观察旧机物理停机；已用新 Token、旧派发停用和交接核验隔离，不能改写成已取得旧机停机证明。

原 TF 历史邀请确认 tombstone 和已确认私有回传记录均保留；禁止重接原邀请或重复发送旧文件。默认区 Go Club 和国区红果漫剧已通过新平台真实链路；新平台上的历史版本完整交付、新 TF 任务仍需各自真实输入验收。安装、签名和应用运行不在当前证明范围内。
