# IPA Decrypt Lab

个人使用的 iOS 应用下载、解密校验与私有交付工具。通过 Telegram 提交应用链接，由云端工作机按需处理，完成后通过私有 Google Drive 文件交付。

## 快速使用

1. 在机器人私聊中发送 App Store 链接或 App ID。
2. 点击“进行中”查看处理状态。
3. 完成后，点击应用名称领取文件，并用自己的 Google 账号打开。

需要历史版本时，发送 `/versions 应用链接`，再选择版本。指定版本可使用 `/version 应用链接 版本号`。

中国区应用请使用带 `/cn/` 的完整链接。其他地区链接和纯数字 App ID 使用默认账号。

## 功能

- App Store 免费应用最新版下载与完整性校验。
- 历史版本查询、分页和指定版本入口。
- TestFlight 邀请链接处理入口。
- 任务分类、分页浏览、取消和私有文件领取。

App Store 最新版已完成真实交付验证。历史版本和 TestFlight 在当前平台上的完整实测仍在进行，详见[项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。

## 运行方式

Telegram 接收请求，Cloudflare Workers / D1 管理任务，CircleCI macOS ARM64 工作机执行处理，Google Drive 保存私有文件。GitHub Actions 负责构建、测试和临时凭据签发。

工作机按任务启动，普通任务复用预编译运行包。当前支持配置主人的私聊，IPA 文件上限为 2 GB。

## 文档

- [使用指南](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/TELEGRAM.md)：指令、地区选择、任务和领取方式。
- [维护手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md)：环境配置、发布和故障处理。
- [架构说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/MANAGED-RUNTIME.md)：组件职责与处理流程。
- [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)：已完成范围和后续验收。
- [验证记录](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/VALIDATION.md)：真实任务、CI 和源码来源。
- [文档目录](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/DOCUMENTATION.md)：专题说明与历史档案。

## 源码与发行版

当前服务的源码位于 [upgrade/managed-runtime-v0.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/tree/upgrade/managed-runtime-v0.2)，日常修改在维护分支验证。

[alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5) 是历史架构的公开预览包。附件用途与来源见[发行说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/RELEASES.md)。

## 依赖与许可证

主要依赖：[ApplePackage](https://github.com/Lakr233/ApplePackage)、[ipatool](https://github.com/majd/ipatool)、[UnfairPlay](https://github.com/DrWhax/unfairplay) 和 [age](https://github.com/FiloSottile/age)。

本项目的使用条款见 [LICENSE](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/LICENSE)，第三方组件保留各自许可证。
