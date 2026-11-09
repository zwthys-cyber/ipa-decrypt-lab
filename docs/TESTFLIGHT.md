# TestFlight 公开邀请与当前取包边界

## 2026-11-09：A.I. 公开邀请检查

用户提供的 [公开邀请](https://testflight.apple.com/join/yoNuHexZ) 可通过无凭据 HTTPS GET 取得 HTTP 200 页面。Apple 页面标题为 A.I. beta，标注 iOS，并提供同一邀请码的 `itms-beta://testflight.apple.com/join/yoNuHexZ` 跳转。它没有在公开 HTML 中提供 IPA、构建编号或应用下载许可证。

该观察只证明公开预览入口可访问，不证明测试名额、设备条件、测试账号资格、当前有效构建或包下载可用。没有加入测试、接受条款、登录 Apple 或发起 IPA 下载。

## 当前实现状态

| 项目 | 结果 |
| --- | --- |
| 公开邀请页面识别 | 本次只读检查已识别 A.I. / iOS |
| 机器人 TestFlight 自动识别与任务提交 | 尚未接入，普通入口只支持 App Store |
| TestFlight 专用测试会话 | 仓库目前未配置 |
| TF 测试构建/版本解析 | 未完成 |
| TF IPA 获取 | 未取得 |
| TF 解密与完整明文校验 | 未验证 |
| TF 文件交付/安装运行 | 未验证 |

正常 App Store 会话使用的 DSID、密码令牌和 Cookie 不应当作已经验证的 TestFlight 会话。参考的独立客户端实现使用 TestFlight 账号标识以及 `X-Session-Id`、`X-Session-Digest` 查询邀请，再单独调用接受邀请接口；这说明认证/测试资格需要独立验证，不能从公开 join 链接推断已授权取包。当前没有向这些接口发送现有账号凭据，也没有要求用户公开会话头。

[Apple 官方说明](https://testflight.apple.com/)要求通过 TestFlight 接受开发者邀请，测试者访问其获准的构建。公开页面可打开不等于匿名 IPA 直链。参考 [独立会话实现](https://github.com/WenJiazhi/loon-testflight-autojoin/blob/main/scripts/testflight-autojoin.js) 仅用于协议研究，没有执行该第三方脚本或使用第三方解密服务。

## 不混淆 App Store 与测试版本

开发者在 [正式版页面](https://apps.apple.com/us/app/a-i/id6445896437) 的回复中公布了同一邀请，因此可关联到正式版 App ID `6445896437`。这个数字不是已经解析出的 TF 构建编号；下载正式版不能算取得该 TF 构建。

邀请 HTML 中的 `apple-itunes-app` banner 写的是 `899247664`，它是 TestFlight 客户端本身，不是 A.I.。不能把这个 banner ID 交给现有导出流程后声称完成了目标应用下载。

## 继续验证需要什么

先确认测试账号已经加入邀请、能够看到可用测试构建，再研究独立的 TestFlight 认证及构建读取。账号已经加入也不代表 GitHub 已有对应会话。会话等私有材料只能通过受保护配置处理，不进入聊天、源码、公共输入或日志。

取到实际测试包后，先核对构建、Bundle ID、架构、加密切片和授权材料，再判断现有模型是否兼容。未通过完整明文校验前不得宣称 TF 解密成功；也不能从 TF 包直接推广安装运行或修改到期限制的能力。

所有代码执行、测试和构建继续在 GitHub-hosted Actions，VPS 只运行已验证成品；本次没有改动运行代码、部署、原德国区/CN Secrets 或已有模型，也没有使用个人手机作服务端基础设施。
