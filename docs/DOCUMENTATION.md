# 项目文档索引

更新于2026-11-27。当前生产为Cloudflare/D1、按需CircleCI macOS ARM64和私有Drive交付；处理源码来自upgrade/managed-runtime-v0.2，main保留默认分支及账号/旧发行维护用途。维护分支中的新文档不等于新生产部署。

## 当前使用和维护

| 文档 | 用途 |
| --- | --- |
| [README](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/README.md) | 当前架构、分支与真实成功范围 |
| [操作手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md) | 维护发布、凭据、领取/取消和未知结果 |
| [Telegram](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/TELEGRAM.md) | 实际支持的主人私聊指令和Drive交付 |
| [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md) | 精确源码、CI/真实任务证据及剩余验收 |
| [任务恢复](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/SESSION-RECOVERY.md) | D1意图、隔离、取消和离线交接 |
| [中国区账号](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/CHINA-ACCOUNT.md) | 会话维护、缓存修正及单应用许可边界 |
| [下载模块](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/DOWNLOADER.md) | 当前处理流程与原生完整性要求 |
| [认证兼容](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/AUTH-COMPATIBILITY.md) | 固定错误分类，区分缓存、会话和设备问题 |
| [TestFlight](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/TESTFLIGHT.md) | 历史接受防重来源和新平台待验收范围 |
| [仓库审计](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/REPOSITORY-AUDIT.md) | 548文件检查、冗余候选和文档修订 |

## 架构与固定来源

| 文档 | 用途 |
| --- | --- |
| [托管运行时](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/MANAGED-RUNTIME.md) | 当前架构入口及历史候选验证 |
| [迁移验收](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/MIGRATION-READINESS.md) | 已完成离线切换、保留缺口及历史调查 |
| [CircleCI维护记录](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/README.md) | 实现证据及源码维护约束 |
| [CircleCI配置](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/.circleci/config.yml) | 当前按需工作机与公共构建配置 |
| [公共运行包来源](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/runtime-pins.json) | 当前固定的base/CN/TF来源及摘要 |
| [费用约束与调查档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/ZERO-COST.md) | 用户约束、历史平台调查及范围限制 |
| [仓库约束](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/AGENTS.md) | CI执行、凭据与未知结果保护 |

## 旧发行和研究档案

| 文档 | 范围 |
| --- | --- |
| [公开附件](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/RELEASES.md) | alpha.5预览版旧VPS/Intel快照，非当前生产架构 |
| [VPS部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/VPS-DEPLOYMENT.md) | 已退出派发的旧版本配置/构建/备份档案 |
| [旧白名单](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/MULTI-USER.md) | VPS多用户实现；新入口仅主人 |
| [free-pilot部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/free-pilot/DEPLOY.zh-CN.md) | 早期独立试验，不替代当前生产切换 |
| [Linux归档工具](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/free-pilot/LINUX-ARCHIVE.zh-CN.md) | 独立10GB合成完整性验证，不扩大机器人2GB能力 |
| [alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/releases/v0.1.0-alpha.5.md)、[alpha.4](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/releases/v0.1.0-alpha.4.md)、[alpha.3](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/releases/v0.1.0-alpha.3.md)、[alpha.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/releases/v0.1.0-alpha.2.md)、[alpha.1](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/releases/v0.1.0-alpha.1.md) | 各版本当时的功能和证据 |
| [原始下载调查](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/NATIVE-DOWNLOAD-RESULTS.md)、[离线后端](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/OFFLINE-BACKEND.md)、[早期研究](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/RESEARCH.md) | 日期内原始观察，不当作当前故障或平台限制 |

默认main的旧代码文档保留历史范围；当前操作以维护分支最新说明及成功生产回执为准。切勿为同步说明而直接推进开启中的生产分支。
