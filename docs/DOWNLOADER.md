# 原始 IPA 下载与当前生产入口

> 文档范围更新（2026-11-27）：本页在main保留旧代码/研究/发行历史。当前生产处理源码来自upgrade/managed-runtime-v0.2，已切换Cloudflare/D1 + CircleCI ARM64 + 私有Drive；main仍用于账号维护和旧Intel发行。[当前同名文档](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/DOWNLOADER.md) · [运行手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md) · [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。不要按历史VPS说明重启旧poller或重新启用5个退休派发工作流。

当前下载组件随 [v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5) 发布。正式入口是 Telegram 管理员与白名单私聊，以及 GitHub 的 `private-delivery.yml`（外区）、`china-private-delivery.yml`（中国区）和主人专用 `testflight-private-delivery.yml`；历史列表分别使用 `version-catalog.yml`（外区）与 `china-version-catalog.yml`（国区）。2026-11-08 [X 完整导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2)已验证下载与解密恢复。

## App Store 处理流程

1. 依据链接选择账号；国区检查中国区元数据及 CNY 免费价格，外区保留原美区预检，并核对容量。
2. 取得精确源码指纹和 macOS Intel 平台匹配的 CI 运行包。
3. 通过原生 Apple 登录完成 Store AMD/SP 验证；保留商店区域和系统配置请求上下文。
4. 请求免费许可，携带会话、完整 storefront、设备证明及账号绑定 kbsync，使用白名单 ent/download 接口获取原包。
5. 核对 App ID、bundle、请求版本及包结构，再执行模型复用、全部加密切片/页面校验与账号元数据清理。
6. 生成短期 age 密文和脱敏收据；常驻控制器在对应授权用户私聊交付前再次复核。

Python 编排位于 `tools/native_store.py` 和 `tools/private_export.py`；Swift 兼容代码位于 `tools/StoreAMD.swift`、`tools/LabEntDownload.swift` 及原生 bag 桥接。账号、模型和真实应用不进入公共源码、构建缓存或 Release。

## 配置与验证范围

Apple Secrets 使用 `APPLE_ID`、`APPLE_PASSWORD`，需要时配置短期 `APPLE_2FA_CODE`；模型使用已有 `FAIRPLAY_MODEL_B64`，不为重试重新注册或生成模型。机器人和交付凭据见[VPS 部署](VPS-DEPLOYMENT.md)。编译及测试只在 GitHub-hosted 运行器执行，VPS 只运行成品。

登录、下载、明文校验和安装运行分别判断。X 的验证通过 32 个加密切片、86,704 页，`runtime_verified=false`；本轮没有增加安装运行或 Telegram 文件发送证据。

## 早期 Go 下载器与认证调查

`store-download.yml`（Original App Store IPA）保留为固定 ipatool 提交的受控研究入口，不是生产机器人采用的下载路径。旧 ARM 对照也不能推广成现有生产平台支持；当前生产仅允许 macOS 26 Intel 与 macOS 15 Intel。

早期 generic BadLogin、5002、空响应与 HTTP 拒绝没有证明密码错误、账号封禁或明确双重认证要求。Go 的 plist-compat 实验、首次 Swift 登录及 ent/download 历程，分别见[认证兼容](AUTH-COMPATIBILITY.md)、[原生对照](NATIVE-STORE.md)和[下载结果](../NATIVE-DOWNLOAD-RESULTS.md)。历史失败结论由[最新项目状态](PROJECT-STATUS.md)中的实测更新。


## 中国区账号的独立接入状态（2026-11-09）

中国区独立模型、跨运行器复用与保存状态重放均通过完整明文验证。`tools/cn_private_export.py` 使用专用会话、GUID、检查点和模型，以非交互 Cookie 刷新取得当前设备证明，再复用公共导出校验/清理/加密流程。`/cn/` 链接自动选择该固定工作流，中国区支持最新版及可获取的历史版本，其他链接仍使用原账号。普通国区任务不挂载外区凭据，不收验证码，不进行模型恢复或电脑授权；会话失效由管理员走独立维护流程。原德国区凭据、模型和安全设置保持原样。详见 [中国区接入说明](CHINA-ACCOUNT.md)。

## TestFlight 独立处理流程（2026-11-09）

TF 邀请由主人私聊提交，使用 `tf_` 请求与独立持久会话；先检查实际成员资格，必要时先记录接受意图、最多接受一次，再取得可用 iOS 构建。它不使用 App Store 免费许可或正式版作为替代。任务加载独立源码/ABI匹配的 TF SDK 与既有 CN 模型，严格验证全部加密页面并清理账号数据，最后通过原交付器发送 `名称_Beta_版本.ipa`。

[CapyPlayer 实际导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) 验证46个镜像、17,724页，用户截图确认收件。已有资格不重复接受；普通任务不密码重登、不初始化模型或新增授权。额外协议、会话失效、限流和明文校验失败时停止。详见 [TF 证据与限制](TESTFLIGHT.md)。
