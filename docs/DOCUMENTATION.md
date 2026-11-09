# 项目文档索引

本文档于 2026-11-09 更新，当前成品版本为 [v0.1.0-alpha.4](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.4)。Apple 新原生认证与 Store AMD/SP 设备注册已恢复，正式 X 导出通过 32 个加密切片、86,704 页完整验证。安装运行和本轮新的 Telegram 文件发送不在这次验证范围内。

## 使用、部署与发布

| 文档 | 用途 |
| --- | --- |
| [README](../README.md) | 项目能力、运行架构与已验证范围 |
| [项目状态](PROJECT-STATUS.md) | 当前事实、运行证据、边界与待办 |
| [成品包与发布](RELEASES.md) | 平台选择、附件、摘要、来源与发布工作流 |
| [新版发布说明](releases/v0.1.0-alpha.4.md) | 白名单、隔离、配额与发布范围 |
| [多用户白名单](MULTI-USER.md) | 管理员授权、用户隔离与限制 |
| [进度与加速版](releases/v0.1.0-alpha.3.md) | alpha.3 的进度与提速快照 |
| [登录修复版](releases/v0.1.0-alpha.2.md) | alpha.2 的兼容修复快照 |
| [Telegram](TELEGRAM.md) | 指令、历史版本、配额、进度与交付 |
| [VPS 部署](VPS-DEPLOYMENT.md) | 私有配置、安装、健康检查和回滚 |
| [任务恢复](SESSION-RECOVERY.md) | SQLite、取消、未知发送结果和备份 |
| [中国区账号接入](CHINA-ACCOUNT.md) | 实时验证码、独立会话、跨运行器下载证据与模型接入边界 |
| [认证兼容](AUTH-COMPATIBILITY.md) | 当前原生登录、SP 挑战、bag 与设备证明 |
| [下载模块](DOWNLOADER.md) | 当前工作流、组件及早期 Go 研究入口 |
| [代理约束](../AGENTS.md) | 编译位置、凭据保护、平台及验证边界 |

## 历史研究与证据

| 文档 | 保留的历史范围 |
| --- | --- |
| [原生认证对照](NATIVE-STORE.md) | 首次 Swift 登录及早期下载失败 |
| [原生下载修正](NATIVE-DOWNLOAD-FIX.md) | 会话复用与免费许可处理 |
| [原始下载结果](../NATIVE-DOWNLOAD-RESULTS.md) | 2026-11-03 原包获取及 remap 失败 |
| [ent/download 调查](../ENT-DOWNLOAD.md) | 端点、会话、kbsync 与许可边界 |
| [iOS 原生解密跟进](../IOS-DECRYPTION-FOLLOWUP.md) | SINF 与原生 syscall 实测 |
| [离线后端档案](../OFFLINE-BACKEND.md) | 模型恢复、旧阻塞及跨运行器证据 |
| [早期研究](RESEARCH.md) | 合成样本、平台差异与失败证据 |
| [旧版发布记录](releases/v0.1.0-alpha.1.md) | 已被新版替换的公开成品范围 |

历史材料中的“当前”“尚未实现”“暂停”按其原实验日期解释，不能覆盖最新项目状态。所有编译与测试在 GitHub-hosted Actions 执行；VPS 只运行已验证成品。Release 不含账号、模型、交付私钥、Telegram token 或应用文件；公开发布与 VPS 部署是两个独立动作。
