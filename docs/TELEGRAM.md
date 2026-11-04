# Telegram 私有交付测试

当前机器人为 @ipazake_bot。所有编译、测试、下载、解密及机器人会话仅在 GitHub-hosted Actions 中运行。这里是限时集成测试入口，不是常驻收费服务。

## 已实现的流程

私聊提交 App Store 链接或数字 ID → 固定 GitHub 工作流 → 账号授权下载 → 使用已保存模型解密 → 每个加密切片明文哈希校验 → 移除 Store 账号元数据与许可文件 → age 加密短期产物 → Linux 私有解密并复核 → Telegram 私聊发送完整 IPA。

下载端仅接受当前美区免费应用；账号仍需有合法下载许可。模型不为每个请求重新注册电脑授权。缺失加密前哈希、切片不完整、账号下载失败、元数据未清理或产物摘要不匹配都会拒绝交付。

原始 IPA、候选明文、模型及原始报告仅在运行器私有临时目录中处理。公开产物只含 age 密文和固定字段的收据，保留 1 天；密钥存于 Secret。Telegram 文件只发给配置的管理员私聊，普通用户与群组不能提交任务。IPA 需要重签名，安装与实际运行尚未验证。

## 必要配置

在仓库 Settings → Secrets and variables → Actions 配置下列 Secret，勿写入代码或公开日志：

| Secret | 用途 |
| --- | --- |
| APPLE_ID / APPLE_PASSWORD | 现有授权下载账号 |
| FAIRPLAY_MODEL_B64 | 已验证的复用模型 |
| TELEGRAM_BOT_TOKEN | BotFather 机器人令牌 |
| TELEGRAM_OWNER_ID | 管理员个人数字 ID |
| TELEGRAM_API_ID / TELEGRAM_API_HASH | 官方本地 Bot API 使用的开发者应用配置 |
| DELIVERY_AGE_IDENTITY | 私有交付 X25519 密钥 |

交付密钥由 GitHub 上的 delivery-contracts.yml / keygen 生成。工作流只输出仓库公钥封装后的密钥密文及 age 公钥；需由维护者经 GitHub API 保存密文为 Secret，并将对应公钥写入 config/delivery.json。正常使用无需重复生成，也不要覆盖现有密钥，否则之前的交付产物将无法解密。

## 首次准备与启动

1. 运行 telegram-server-build.yml，编译固定版本的官方本地 Bot API，并缓存公开二进制。该步骤不接触 Telegram 或 Apple Secret。
2. 运行 delivery-contracts.yml / test，完成 Python 边界、任务状态及 age 篡改拒绝测试。
3. 首次从云端迁移时，将 migrate_from_cloud 设为 true；已成功迁移的本仓库机器人保持 false。正常重启只连接本地服务，避免在云端退出冷却期内重复登录。
4. 打开 [Telegram private IPA test session](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/workflows/telegram-session.yml)，分支 main。
5. mode=check 验证本地服务并向管理员发送一条确认消息；mode=session 开启限时轮询。
6. minutes 默认 30，允许 1–45。可选 request_id 用于启动后发送一个已经完成的交付任务。
7. 已完成文件也可用 mode=deliver 和 request_id 单独取回；该模式不重复下载或恢复模型。

所有 Telegram 会话使用同一个并发组，不能同时在其他服务轮询同一机器人。首次迁移会调用云端 logOut，再由本地服务认证；结束时退出本地会话并清理私有状态。Telegram 规定从云端退出后 10 分钟内不能重新登录云端。存在 webhook 时会明确失败，不自动删除 webhook。

官方本地 Bot API 的上传上限为 2000 MB；本项目目前将 IPA 限为 1 GiB，并保留审计器的成员数量、Mach-O 大小和读取预算。超过当前审计范围会拒绝。完整 IPA 直接在私聊中发送，不拆分文件，也不发布公开明文下载链接。[Telegram 官方说明](https://core.telegram.org/bots/api#using-a-local-bot-api-server)。

菜单实测 [41866282876](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41866282876) 已确认：7 个中文指令、默认语言与 zh 范围、commands 菜单按钮均读回匹配。

实时进度验证：[295 项 Python 测试及 Telegram 单消息更新 41868108407](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41868108407) 已通过；[阶段通道写入与读回 41868334364](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41868334364) 已通过。两项演示不下载或解密真实应用。

## 实时进度

任务使用一张管理员私聊进度卡，显示真实阶段、任务编号和已用时间。同阶段约 15 秒刷新一次，阶段变化及时更新，避免连续发送多条通知。/status 会立即刷新当前进度卡。

升级前启动的任务没有阶段上报代码，只能显示已有的排队/执行状态。更新后的新任务才有完整阶段；可在 session 模式传入 request_id 继续跟踪旧任务，不重新提交下载。

阶段包括排队、准备环境、查询应用、验证下载账号、下载、解密及页面校验、完整 IPA 复核、结果加密、文件取回、交付复核、Telegram 上传和完成。短阶段可能在两次轮询间完成；不保证每一阶段都显示。

下载器和 Telegram 本地上传接口暂不提供可靠的逐字节回调，所以处理中不展示百分比，只有确认文件发送成功后显示 100%。上传请求等待期间显示“上传到 Telegram”，不估算已上传字节或剩余时间。

工作流只向自身提交上的固定 check 发布白名单阶段；check 绑定任务编号及运行编号，不含账号、原始日志、文件路径或密钥。机器人只接受匹配的 GitHub Actions check。进度接口不可用时退回排队/准备状态，文件发送结果未知时不显示完成，也不自动重发。

可用 telegram-session.yml / progress-demo 验证同一消息更新，演示会明确标注“不执行下载”。worker 为这一功能额外使用 checks:write，控制器使用 checks:read；用途限制见 AGENTS.md。

## 中文菜单

每次启动均向管理员私聊注册中文指令（默认语言及 zh），并将菜单按钮设为指令列表。配置后使用 getMyCommands 和 getChatMenuButton 逐项读回确认；菜单保存在 Telegram，测试会话结束后仍显示，执行指令需要会话在线。

可单独运行 telegram-session.yml / mode=menu 更新并验证菜单，不下载 IPA，也不创建任务。管理员私聊之外不注册操作菜单。若客户端尚未显示，请退出机器人聊天后重新打开。

## 私聊指令

| 输入 | 行为 |
| --- | --- |
| /decrypt | 提示输入应用链接或 ID |
| App Store HTTPS 链接或数字 ID | 创建下载与解密任务 |
| /help 或 /start | 显示使用方式 |
| /id | 显示自己的数字 ID |
| /status | 查看本次会话的当前任务 |
| /cancel | 请求取消本次会话的当前任务 |
| /get 后跟 32 位任务编号 | 取回约一天内保留的已完成文件 |

当前测试一次处理一个任务，每个会话最多提交 3 个任务，提交间隔至少 30 秒。已接收的更新使用确定性任务编号去重；提交网络超时不会盲目重复提交。任务提交到固定仓库 main 的 private-delivery.yml；机器人没有提交代码或修改 Secrets 的权限。

自动文件发送发生不明确的网络超时时，系统不会自行重发。先检查是否已经收到，再用 /get 显式重试。会话重启不恢复内存中的当前任务，但可以用已保存的任务编号取回结果。会话结束后已提交的工作流继续运行，产物到期后需重新提交任务。

## 独立工作流

- private-delivery.yml / preflight：无账号构建及测试。
- private-delivery.yml / export：需 app_id 和 32 位十六进制 request_id，生成加密交付产物。
- telegram-bootstrap.yml / identify：10 分钟身份查询，只回复请求者自己的 ID，无 Apple Secret 和任务提交权限。已经使用本地服务器的机器人不应同时运行此云端引导。
- telegram-server-build.yml：官方 C++ 服务编译，固定源码及子模块；仅缓存公开二进制。
- delivery-contracts.yml / test：无账号合成测试。
- telegram-session.yml：仅此工作流有 actions:write，用于提交/取消固定工作流；其他工作流保持只读权限。

## 实测记录

- 身份引导 [41855502108](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41855502108)：getMe 及私聊 /id 收发通过，管理员配置完成。
- 加密与密钥封装 [41855730924](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41855730924)：277 项 Python 测试及 age 加密/解密、错误密钥、截断与篡改检查通过。
- 真实私有导出 [41856194867](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41856194867)：App ID 6599842047，62 个切片、12,524 页校验通过；移除账号元数据后的 IPA 为 92,118,013 字节，公开产物仅有加密文件与收据。
- Telegram 任务合约 [41861247714](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41861247714)：管理员过滤、重复更新、模糊提交结果、取消、发送结果未知不重试及收据校验通过。
- 官方上传服务 [41860507368](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41860507368)：固定源码编译、版本检查与公开二进制缓存完成。
- 真实大文件交付 [41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056)：289 项 Python 测试（1 项跳过）、age 检查通过；本地服务认证成功，Linux 解密、摘要与结构复核后，Telegram 确认收到 92,118,013 字节完整 IPA。`plaintext_verified=true`、`runtime_verified=false`。
- 限时交互会话 [41865319660](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41865319660)：用于真实私聊指令测试；单次文件交付成功不代表所有应用或生产服务均已验证。

本轮修复了新运行器首次请求被冷却时间误拦截、手动取回后重复自动发送，本地服务临时目录未预建，以及完成迁移后重启仍检查云端登录的问题。任务合约使用合成消息；真实 Telegram 提交触发新下载任务仍需与对应运行记录分别核对。

## 尚未实现

计费、多用户授权、持久化生产队列、常驻部署、会话间自动恢复、独立 Apple 签名信任验证和安装运行测试。GitHub Actions 不作为无限续期的托管服务。Debian 服务器未部署或执行本项目。
