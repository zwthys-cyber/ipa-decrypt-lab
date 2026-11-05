# IPA Decrypt Lab

这个项目将 App Store 应用的下载、历史版本选择、解密校验和 Telegram 交付串成完整流程。机器人在 Debian VPS 上常驻运行，下载和解密交给 GitHub-hosted macOS。

目前仅开放管理员私聊，可处理美区免费应用，IPA 最大 **2000 MB**。收费、多用户和应用安装后的兼容性，还在待办里。

## 下载

第一版成品位于 [GitHub Releases](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases)。里面有 Linux amd64 服务器端，以及 macOS 26 / 15 Intel 运行包；用途、配置和校验方法见 [发布说明](docs/RELEASES.md)。

这些包需要配合仓库工作流和自己的私有配置使用。Apple 账号、授权模型、Telegram 凭据和应用 IPA 都不随发布包提供。

## 现在能做什么

- 发送 App Store 链接或 App ID，默认下载最新版。
- 用 `/versions` 先查看最近一批历史版本，按需加载更早版本并直接点选。
- 用 `/version` 指定版本号或 Apple 历史版本 ID。
- 在同一张 Telegram 消息里查看阶段和耗时。
- 收到带应用图标的 `名称_版本.ipa` 文件。
- 服务重启后继续跟踪任务；发送结果不明时保留记录，避免重复发文件。

完整指令见 [Telegram 使用说明](docs/TELEGRAM.md)。

## 怎么运行

任务分成两部分：

1. **Debian VPS**：接收 Telegram 指令、保存任务状态、取回结果并发送文件。
2. **GitHub Actions**：构建和测试程序，在 macOS 上下载应用、复用已有模型解密、校验结果，再生成短期加密产物。

普通任务使用约 **28 MB 的预编译运行包**，不用每次安装 Go、编译程序或恢复整个 Swift 构建目录。源码更新后，再由独立工作流构建和测试新包。固定 Apple 公共资源也会复用缓存，并在每次使用前校验。

My BVF 的最新一次 GitHub 导出实测约 59 秒，此前预编译版样本为 1 分 49 秒。QQ 历史列表首批 10 项约 2 分 22 秒，下一批约 1 分 2 秒。再次打开已缓存的列表不启动 GitHub。这些是单次样本，排队、Apple 响应和文件大小仍会影响耗时，Telegram 上传另计。[测试记录](docs/PROJECT-STATUS.md)

## 已经验证到哪一步

已在全新的 GitHub macOS 运行器上验证了模型恢复、模型复用、检查点重放和完整 IPA 校验，也完成过 92 MB 文件的 Telegram 私聊交付。历史版本下载、可点击列表和两个 Intel 平台的成品包也都有运行记录。

解密成功的判断包含完整切片和页面校验，不能只看 `cryptid=0`。尚未把重签名、安装和实际运行纳入验证，所以结果里的 `runtime_verified` 仍为 `false`。

## 部署与配置

- [VPS 部署](docs/VPS-DEPLOYMENT.md)：运行环境、Secrets、部署、备份和回滚。
- [任务恢复](docs/SESSION-RECOVERY.md)：重启、取消和发送不确定时的处理。
- [项目状态](docs/PROJECT-STATUS.md)：当前实现、验证记录和待办。
- [离线后端研究记录](OFFLINE-BACKEND.md)：早期失败、排查过程和后续结果。

编译、测试和构建验证全部在 GitHub 上执行，VPS 只运行成品。当前实现不依赖个人 iPhone，也不接入第三方解密服务。

## 依赖与许可证

下载客户端基于 [ApplePackage](https://github.com/Lakr233/ApplePackage)，辅助工具使用 [ipatool](https://github.com/majd/ipatool)，离线后端使用 [UnfairPlay](https://github.com/DrWhax/unfairplay)，传输加密使用 [age](https://github.com/FiloSottile/age)，Telegram 文件交付使用官方 [Bot API server](https://github.com/tdlib/telegram-bot-api)。

保留各依赖的许可证和来源。仓库代码的许可证见 [LICENSE](LICENSE)；依赖代码按各自许可证分发。
