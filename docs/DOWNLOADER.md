# 原始 IPA 下载模块

自研 Python 编排层，App Store 私有协议使用 MIT 许可的 majd/ipatool，固定提交 d9c0247daea564d3ec7d04a9b015d0a29af66b04；不是自研 FairPlay 算法，也不调用第三方下载网站。

原始依赖代码仅在 Actions 临时检出并从源码构建；保留其 LICENSE，不重新声明依赖版权。所有构建和试运行仅 GitHub-hosted。

## 使用

仓库 Settings → Secrets and variables → Actions：
- APPLE_ID：已配置 App Store 的专用账号。
- APPLE_PASSWORD：该账号密码。
- APPLE_2FA_CODE：需要时配置短期验证码。

不要在公开聊天、workflow inputs、源码或日志填写这些值。Actions → Original App Store IPA → Run workflow，target 默认 6599842047。首次无验证码时若收到 requires_2fa，需要更新验证码 Secret 后再手动运行；暂不支持在运行中输入验证码，排队过久可能导致过期。

仅支持 US storefront 的当前免费应用。执行下载前查询官方元数据并拒绝付费应用；登录返回0还必须通过 auth info。下载模块获取账号授权、调用苹果下载、由上游补充原始 SINF 授权文件，随后直接交给现有诊断器。包与候选文件不进入缓存或公开产物；不提供公开 IPA 下载链接。

真实下载需要上述账号配置。仓库没有账号时，只能完成编译、CLI兼容性和模拟认证测试，不得宣称真实下载已验证。下载与解密分别判断，downloaded=true 仍不代表 decryption_proven=true。

当前仍是诊断原型，无支付、商业分发或常驻服务。账号操作可能受地区、协议变化和验证码有效期影响。后续需验证真实账号下载，再决定长期凭据和私人存储方案。
