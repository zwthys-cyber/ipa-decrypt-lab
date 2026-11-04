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
3. 打开 [Telegram private IPA test session](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/workflows/telegram-session.yml)，分支 main。
4. mode=check 验证本地服务并向管理员发送一条确认消息；mode=session 开启限时轮询。
5. minutes 默认 30，允许 1–45。可选 request_id 用于启动后发送一个已经完成的交付任务。
6. 已完成文件也可用 mode=deliver 和 request_id 单独取回；该模式不重复下载或恢复模型。

所有 Telegram 会话使用同一个并发组，不能同时在其他服务轮询同一机器人。首次迁移会调用云端 logOut，再由本地服务认证；结束时退出本地会话并清理私有状态。Telegram 规定从云端退出后 10 分钟内不能重新登录云端。存在 webhook 时会明确失败，不自动删除 webhook。

官方本地 Bot API 的上传上限为 2000 MB；本项目目前将 IPA 限为 1 GiB，并保留审计器的成员数量、Mach-O 大小和读取预算。超过当前审计范围会拒绝。完整 IPA 直接在私聊中发送，不拆分文件，也不发布公开明文下载链接。[Telegram 官方说明](https://core.telegram.org/bots/api#using-a-local-bot-api-server)。

## 私聊指令

| 输入 | 行为 |
| --- | --- |
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
- 大文件发送仍需单独的真实回执确认；源码与合成测试通过不等同于实际交付成功。

## 尚未实现

计费、多用户授权、持久化生产队列、常驻部署、会话间自动恢复、独立 Apple 签名信任验证和安装运行测试。GitHub Actions 不作为无限续期的托管服务。Debian 服务器未部署或执行本项目。
