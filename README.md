# IPA Decrypt Lab

截至 2026-11-27，原 Telegram 机器人已切换到 **Cloudflare Workers / D1 控制面 + 按需 CircleCI macOS ARM64 工作机 + 私有 Google Drive 交付**。原运行环境 已退出派发，日常任务不依赖旧机，也无需常驻 macOS 工作机。

| 分支 | 当前用途 |
| --- | --- |
| [upgrade/managed-runtime-v0.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/tree/upgrade/managed-runtime-v0.2) | 生产运行源码；最近已验证的处理版本为 `185a52110922e0f67ac2c7dff4e1fa85b3b4c98e` |
| [upgrade/managed-runtime-maintenance-v0.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/tree/upgrade/managed-runtime-maintenance-v0.2) | 修改、文档整理和 CI 验证；提交到这里不代表已经上线 |
| [main](https://github.com/zwthys-cyber/ipa-decrypt-lab/tree/main) | 默认分支及既有账号维护、Intel 构建/发行工作流；不是当前机器人运行源码 |

公开预览发行版仍为 [v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。它的 Linux amd64 / macOS Intel 附件是旧架构快照，不包含当前 CircleCI 生产架构。准确来源以附件 BUILDINFO 为准。

## 已验证的真实链路

| 验证 | 结果 |
| --- | --- |
| 生产切换 | [45918215266](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918215266)：新源码、原机器人 webhook、该源码真实 cron、历史状态读回均通过 |
| 默认区 Go Club | CircleCI job72：6 个镜像 / 8,000 页；私有文件和主人通知已确认，已保留，不重复下载 |
| 国区红果漫剧 | [CircleCI job75](https://app.circleci.com/workflow/2ae89675-bc82-451c-b290-4ee63c2c360a/job/a1e13406-0c02-43ec-a679-5a5bfa77fd53)：17 个镜像 / 120,976 页，342,632,968 字节；下载、严格明文验证、账号数据清理、私有上传和机器人通知通过 |
| 回复延迟 | 用户 /status 截图约 1 秒；是单次观测，不是服务延迟保证 |

红果漫剧该次全程约 4 分 23 秒，其中工作机排队约 50 秒。成功解密和私有交付不等于已验证重签名、安装或应用运行。

## 当前使用

/start提供分行首页和任务按钮。应用多时每页最多3项，在原消息中翻页；列表显示应用名、版本与易读容量，失败及取消记录单独查看，长任务号不再占据正文。

仅接受配置主人的机器人私聊；不开放原运行环境 白名单和收费入口。

- 直接发送 App Store 链接或数字 App ID：提交最新版。完整 `/cn/` 链接使用独立国区账号，其余链接和数字 ID 使用默认外区账号。
- `/versions AppStore链接或AppID`：请求历史列表；`/version AppStore链接或AppID 版本号`：指定版本，也支持 Apple 历史 ID。国区必须保留完整 `/cn/` 链接。
- `/status`：按进行中、已完成、历史记录分组查看，每页3项，按钮翻页、领取和取消。
- `/get pilot_任务编号`：领取已核验、尚在领取期限内的私有 Drive 文件；用自己的 Google 账号打开。
- `/cancel pilot_任务编号`：记录取消请求，等待后台终止确认。

历史列表及 TestFlight 入口已经接入新控制面，但**新架构上的真实历史版本交付和新 TF 请求仍待分别验收**。旧架构已有的成功记录不能替代新平台实测。旧 `/latest`、`/decrypt`、`/id`、`/allow`、`/deny`、`/users` 和无任务编号的 `/cancel` 不在当前新入口支持范围内。详见 [Telegram 使用说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/TELEGRAM.md)。

## 运行与维护

Cloudflare 接收 webhook、持久化任务/去重和定时核对；GitHub 负责构建、测试和短期角色凭据签发；CircleCI 工作机复用已固定来源与摘要的公共 ARM64 运行包，处理后交给控制面验证私有 Drive 文件并通知主人。普通任务不编译项目。

当前 App Store IPA 上限为 **2,000,000,000 字节**。独立 Linux 工具的 10 GB 合成归档校验不是机器人的 10 GB 下载能力，也不是已验证的真实 10 GB 网盘传输。

生产分支 HEAD 必须等于控制面的运行源码。维护从独立维护分支开始，完成 CI，先关闭空闲旧入口，再推进已验证源码、切换并等待该源码的 cron 回执；不能直接往开启中的生产分支补提交。文档更新无需重放 Apple 任务。

- [当前操作手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md)：架构、分支、维护发布、凭据及故障处理。
- [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)：精确证据、已验证范围和剩余验收。
- [文档索引](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/DOCUMENTATION.md)：当前说明和历史资料。
- [仓库整理审计](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/REPOSITORY-AUDIT.md)：冗余候选、历史工作流及文档修订。
- [发行附件](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/RELEASES.md)：alpha.5 快照及校验。
- [原运行环境 部署档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/VPS-DEPLOYMENT.md)：仅供旧版本追溯，不用于恢复现网入口。

保留了 29 条旧任务、89 条 updates、14 条 metadata 和已知 TF 接受/回传去重记录；2 条旧 pending 及源丢失后的未知变化保持隔离，不自动重放。保存的历史文件、邀请意图和稳定 HMAC 不得因清理仓库而重置。

所有项目构建和测试只在 GitHub / 已授权的 CircleCI 执行；当前工作区和原运行环境 不运行编译或测试。不依赖个人 iPhone 或第三方解密服务。零费用是配置约束，不代表供应商额度、排队和长期可用性的保证，见 [费用与历史评估](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/ZERO-COST.md)。

## 依赖与许可证

下载客户端基于 [ApplePackage](https://github.com/Lakr233/ApplePackage)，辅助工具使用 [ipatool](https://github.com/majd/ipatool)，离线后端使用 [UnfairPlay](https://github.com/DrWhax/unfairplay)，传输加密使用 [age](https://github.com/FiloSottile/age)。原运行环境 文件交付采用官方 [Bot API server](https://github.com/tdlib/telegram-bot-api)；当前新任务通过 Telegram 通知私有 Drive 链接。

仓库许可证见 [LICENSE](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/LICENSE)，各依赖保留各自许可证。账号、模型、私钥、机器人 Token 和第三方 IPA 不随源码或发行附件提供。
