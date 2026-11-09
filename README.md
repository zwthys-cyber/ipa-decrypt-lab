# IPA Decrypt Lab

这个项目将 App Store 和 TestFlight 应用的下载、解密校验和 Telegram 交付串成完整流程；外区 App Store 另支持历史版本选择。机器人在 Debian VPS 上常驻运行，下载和解密交给 GitHub-hosted macOS。

目前开放管理员和白名单用户私聊，可按链接处理中国区或原外区账号的免费应用，IPA 最大 **2000 MB**。每人任务、文件、进度和额度独立；收费和应用安装后的兼容性仍在待办里。

中国区模型已恢复，并通过跨运行器复用、保存状态重放和真实导出，链接路由已[部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566050391)。`/cn/` 商店链接自动使用中国区账号，其他地区链接及数字 App ID 使用原外区账号。中国区先支持最新版；外区历史版本保持可用。见 [中国区接入状态](docs/CHINA-ACCOUNT.md)。

部分国区专属应用仍有许可兼容问题：抖音在 GitHub 境外出口下收到地区不可用相关提示，尚未修复，需大陆出口对照。样本成功不代表所有国区应用都能下载。见 [当前限制与证据](docs/CHINA-ACCOUNT.md)。

机器人主人可直接发送 TestFlight 公开邀请链接，后台检查测试资格、必要时接受一次邀请、获取可用测试构建，完整解密验证后私聊回传。它使用独立持久会话和任务队列，不回退 App Store 正式版。证据与限制见 [TestFlight 自动处理](docs/TESTFLIGHT.md)。

## 下载

当前成品版本为 [v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。里面有 Linux amd64 服务器端，以及 macOS 26 / 15 Intel 运行包；用途、配置和校验方法见 [发布说明](docs/RELEASES.md)。

这些包需要配合仓库工作流和自己的私有配置使用。alpha.5 本次重打包纳入 TF 自动任务与 Beta 文件命名；包的准确源码和构建来源以附件 `BUILDINFO.json` 为准，原标签保留。Apple 账号、授权模型、Telegram 凭据和应用 IPA 都不随发布包提供。

## 现在能做什么

- 发送 App Store 链接或 App ID，默认下载最新版；`/cn/` 自动使用中国区，其他地区或纯数字使用原外区账号。
- 主人发送 TestFlight 邀请链接，自动处理可用的 iOS 测试构建；额外协议、失效会话或模型不兼容时明确停止。
- 进度卡显示下载路线；任务恢复、取消和取文件始终绑定原账号。
- 外区用 `/versions` 先查看最近一批历史版本，按需加载更早版本并直接点选。
- 外区用 `/version` 指定版本号或 Apple 历史版本 ID。
- 已部署的进度卡在同一张 Telegram 消息中显示步骤进度条、真实下载字节比例、全程与阶段耗时；约 5 秒更新计时，重启后继续累计。
- 收到带应用图标的 IPA：App Store 为 `名称_版本.ipa`，TestFlight 为 `名称_Beta_版本.ipa`。
- 服务重启后继续跟踪任务；发送结果不明时保留记录，避免重复发文件。

管理员用 `/allow 用户ID [每日额度]` 授权、`/deny 用户ID` 移除、`/users` 查看白名单。新用户默认每天 3 次，全服务总额度仍默认每天 20 次。详见[白名单说明](docs/MULTI-USER.md)。

完整指令见 [Telegram 使用说明](docs/TELEGRAM.md)。

## 怎么运行

任务分成两部分：

1. **Debian VPS**：接收 Telegram 指令、保存任务状态、取回结果并发送文件。
2. **GitHub Actions**：构建和测试程序，在 macOS 上下载应用、复用已有模型解密、校验结果，再生成短期加密产物。

普通任务使用约 **28 MB 的预编译运行包**，不用每次安装 Go、编译程序或恢复整个 Swift 构建目录。源码更新后，再由独立工作流构建和测试新包。固定 Apple 公共资源也会复用缓存，并在每次使用前校验。

My BVF 的最新一次 GitHub 导出实测约 59 秒，此前预编译版样本为 1 分 49 秒。历史查询复用同批连接后，QQ 首批 10 项约 55 秒，下一批约 1 分 3 秒。再次打开已缓存的列表不启动 GitHub。这些是单次样本，排队、Apple 响应和文件大小仍会影响耗时，Telegram 上传另计。[测试记录](docs/PROJECT-STATUS.md)

X 的后续加速对比已通过：删除账号元数据时直接复制保留项的压缩数据，完整校验仍保留。复核从约 40.4 秒降到 13.8 秒，GitHub 原生作业从 128 秒降到 103 秒；成品包约增大 3%。这是单次后台对比，完整 Telegram 交付仍受排队与网络影响。[实测与边界](docs/PROJECT-STATUS.md)

## 已经验证到哪一步（2026-11-09）

TestFlight 主人自动任务已部署，持久会话恢复、资格检查、测试包下载和严格明文校验均已通过。真实新请求 [CapyPlayer 导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) 验证了46个加密镜像、17,724页；用户提供的 Telegram 截图确认已收到 `CapyPlayer_1.1.7.ipa`。该请求已有成员资格，没有新接受邀请或电脑授权。

后续 [Beta 命名部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714903713) 已通过双平台运行包、CN客户端和 [真实无重复发送导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42716962584) 门禁及服务健康检查。新的 TF 文件使用 `名称_Beta_版本.ipa`。这不代表应用安装运行或所有 TF 应用/模型兼容性已验证。完整范围见 [TestFlight 记录](docs/TESTFLIGHT.md)。

此前的 App Store 验证如下：

2026-11-08 已恢复 Apple 新原生认证与 Store AMD 设备验证。X（App ID `333903271`）已通过正式运行包完成登录、下载、解密和完整性校验：32 个加密切片、86,704 页，清理后 IPA 为 271,261,630 字节。[完整验证记录](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2)。本次记录不包含新的 Telegram 文件发送或安装运行测试。

已在全新的 GitHub macOS 运行器上验证了模型恢复、模型复用、检查点重放和完整 IPA 校验，也完成过 92 MB 文件的 Telegram 私聊交付。历史版本下载、可点击列表和两个 Intel 平台的成品包也都有运行记录。

解密成功的判断包含完整切片和页面校验，不能只看 `cryptid=0`。尚未把重签名、安装和实际运行纳入验证，所以结果里的 `runtime_verified` 仍为 `false`。

进度卡升级已[部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443436341)，并通过[实际 X 导出与数字快照验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42444399936)。官方 Actions 已升级为固定提交的 Node.js 24 版本；新 downloader 和双平台生产任务均无 Node.js 20 弃用警告。alpha.3 已打包这些进度和提速改动；alpha.2 保留为历史快照。

## 部署与配置

完整文档入口见 [文档索引](docs/DOCUMENTATION.md)。登录流程、兼容限制和诊断入口见 [认证兼容说明](docs/AUTH-COMPATIBILITY.md)。

- [VPS 部署](docs/VPS-DEPLOYMENT.md)：运行环境、Secrets、部署、备份和回滚。
- [任务恢复](docs/SESSION-RECOVERY.md)：重启、取消和发送不确定时的处理。
- [项目状态](docs/PROJECT-STATUS.md)：当前实现、验证记录和待办。
- [离线后端研究记录](OFFLINE-BACKEND.md)：早期失败、排查过程和后续结果。

编译、测试和构建验证全部在 GitHub 上执行，VPS 只运行成品。当前实现不依赖个人 iPhone，也不接入第三方解密服务。

## 依赖与许可证

下载客户端基于 [ApplePackage](https://github.com/Lakr233/ApplePackage)，辅助工具使用 [ipatool](https://github.com/majd/ipatool)，离线后端使用 [UnfairPlay](https://github.com/DrWhax/unfairplay)，传输加密使用 [age](https://github.com/FiloSottile/age)，Telegram 文件交付使用官方 [Bot API server](https://github.com/tdlib/telegram-bot-api)。

保留各依赖的许可证和来源。仓库代码的许可证见 [LICENSE](LICENSE)；依赖代码按各自许可证分发。
