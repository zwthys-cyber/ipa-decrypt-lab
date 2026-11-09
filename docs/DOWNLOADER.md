# 原始 IPA 下载与当前生产入口

当前下载组件随 [v0.1.0-alpha.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.2) 发布。正式入口是 Telegram 管理员私聊，以及 GitHub 的 `private-delivery.yml`；历史列表使用 `version-catalog.yml`。2026-11-08 [X 完整导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2)已验证下载与解密恢复。

## 处理流程

1. 检查美区官方元数据、免费价格与容量约束。
2. 取得精确源码指纹和 macOS Intel 平台匹配的 CI 运行包。
3. 通过原生 Apple 登录完成 Store AMD/SP 验证；保留商店区域和系统配置请求上下文。
4. 请求免费许可，携带会话、完整 storefront、设备证明及账号绑定 kbsync，使用白名单 ent/download 接口获取原包。
5. 核对 App ID、bundle、请求版本及包结构，再执行模型复用、全部加密切片/页面校验与账号元数据清理。
6. 生成短期 age 密文和脱敏收据；常驻控制器在管理员私聊交付前再次复核。

Python 编排位于 `tools/native_store.py` 和 `tools/private_export.py`；Swift 兼容代码位于 `tools/StoreAMD.swift`、`tools/LabEntDownload.swift` 及原生 bag 桥接。账号、模型和真实应用不进入公共源码、构建缓存或 Release。

## 配置与验证范围

Apple Secrets 使用 `APPLE_ID`、`APPLE_PASSWORD`，需要时配置短期 `APPLE_2FA_CODE`；模型使用已有 `FAIRPLAY_MODEL_B64`，不为重试重新注册或生成模型。机器人和交付凭据见[VPS 部署](VPS-DEPLOYMENT.md)。编译及测试只在 GitHub-hosted 运行器执行，VPS 只运行成品。

登录、下载、明文校验和安装运行分别判断。X 的验证通过 32 个加密切片、86,704 页，`runtime_verified=false`；本轮没有增加安装运行或 Telegram 文件发送证据。

## 早期 Go 下载器与认证调查

`store-download.yml`（Original App Store IPA）保留为固定 ipatool 提交的受控研究入口，不是生产机器人采用的下载路径。旧 ARM 对照也不能推广成现有生产平台支持；当前生产仅允许 macOS 26 Intel 与 macOS 15 Intel。

早期 generic BadLogin、5002、空响应与 HTTP 拒绝没有证明密码错误、账号封禁或明确双重认证要求。Go 的 plist-compat 实验、首次 Swift 登录及 ent/download 历程，分别见[认证兼容](AUTH-COMPATIBILITY.md)、[原生对照](NATIVE-STORE.md)和[下载结果](../NATIVE-DOWNLOAD-RESULTS.md)。历史失败结论由[最新项目状态](PROJECT-STATUS.md)中的实测更新。


## 中国区账号的独立接入状态（2026-11-09）

中国区账号已通过实时验证码登录，并在新 GitHub 运行器上通过 Cookie 刷新下载免费原包；没有再次使用验证码。中国区独立模型、解密、历史版本与机器人地区路由仍未完成，当前正式任务保持原线路。原德国区账号、模型和安全设置未改动。详见 [中国区接入说明](CHINA-ACCOUNT.md)。
