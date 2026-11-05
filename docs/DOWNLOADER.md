# 原始 IPA 下载模块

本文记录早期 Go 下载器的实现与认证排查。当前使用的 Swift 下载、模型复用和 Telegram 交付流程见 [项目状态](PROJECT-STATUS.md)。

使用 Python 编写编排层，App Store 私有协议使用 MIT 许可的 majd/ipatool，固定提交 d9c0247daea564d3ec7d04a9b015d0a29af66b04；不是自研 FairPlay 算法，也不调用第三方下载网站。

原始依赖代码仅在 Actions 临时检出并从源码构建；保留其 LICENSE，不重新声明依赖版权。所有构建和试运行仅 GitHub-hosted。

## 使用

仓库 Settings → Secrets and variables → Actions：
- APPLE_ID：已配置 App Store 的专用账号。
- APPLE_PASSWORD：该账号密码。
- APPLE_2FA_CODE：需要时配置短期验证码。

不要在公开聊天、workflow inputs、源码或日志填写这些值。Actions → Original App Store IPA → Run workflow，target 默认 6599842047。首次无验证码时若收到 requires_2fa，需要更新验证码 Secret 后再手动运行；暂不支持在运行中输入验证码，排队过久可能导致过期。

仅支持 US storefront 的当前免费应用。执行下载前查询官方元数据并拒绝付费应用；登录返回0还必须通过 auth info。下载模块获取账号授权、调用苹果下载、由上游补充原始 SINF 授权文件，随后直接交给现有诊断器。包与候选文件不进入缓存或公开产物；不提供公开 IPA 下载链接。

真实下载需要上述账号配置。仓库没有账号时，只能完成编译、CLI兼容性和模拟认证测试，不得宣称真实下载已验证。下载与解密分别判断，downloaded=true 仍不代表 decryption_proven=true。

当时仅完成了诊断原型，还没有接入常驻服务。账号操作可能受地区、协议变化和验证码有效期影响。后续转向 Swift 客户端，完成了真实下载验证。

## 认证误判修正

固定的上游提交会把 MZFinance.BadLogin.Configurator_message 映射成 ErrAuthCodeRequired；该通用响应本身不足以证明 Apple 明确要求双重认证。通过构建补丁修正了这个分支，Go 回归测试直接调用上游响应解析器。Python 层不再以帮助文本中出现 auth-code 和 required 来推断需要验证码。

[修正后 Intel 验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41723998603)：回归测试、编译及无账号测试通过，真实登录返回 authentication_unresolved_generic_bad_login，未下载 IPA。该结果不等于密码一定错误，也不等于无需认证即可继续。

已增加 ARM/Intel 运行器选项，用于一次受控兼容性对照，不用于无限重复登录。Go 缓存仅保存依赖和编译对象，不保存 Apple 账号、会话或 IPA。未实现长期登录会话的保存和复用。

上方旧版说明中的 requires_2fa 不再用来解释该通用 BadLogin 响应。只有获得进一步可验证证据后，才可定位具体账号或协议问题。

[ARM 对照验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41725046970)同样通过回归测试和构建，真实登录仍返回 authentication_unresolved_generic_bad_login。切换这两种 GitHub 托管运行器未解决问题；不能由此宣称已排除所有网络或协议因素。在这次 Go 客户端对照中，仍未取得原始 IPA。需要替代认证实现或可验证的合法会话来源，不能靠修改状态名、禁用认证检查或无限重试获得真实授权。
