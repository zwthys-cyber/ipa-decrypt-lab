# 认证兼容与故障诊断

> 文档范围更新（2026-11-27）：本页在main保留旧代码/研究/发行历史。当前生产处理源码来自upgrade/managed-runtime-v0.2，已切换Cloudflare/D1 + CircleCI ARM64 + 私有Drive；main仍用于账号维护和旧Intel发行。[当前同名文档](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/AUTH-COMPATIBILITY.md) · [运行手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md) · [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。不要按历史VPS说明重启旧poller或重新启用5个退休派发工作流。

当前版本为 [v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。2026-11-08 的[正式 X 导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2)已验证原生登录、下载及完整解密恢复；不要再把历史 204/403/SP 失败写成当前运行状态。

## 当前 App Store 生产链路

客户端以固定提交的 ApplePackage 为基础，由仓库构建补丁接入本机 AppleMediaServices。使用 Configurator 2.21，保留 Apple 配置返回的原生认证路径和查询参数，不强制改写为 `/fast/`；仍对实际请求体生成 SAP 签名。

新接口需要 Store AMD 证明 `X-Apple-AMD` / `X-Apple-AMD-M`，它们与 AuthKit 的 `X-Apple-I-MD` 系列不同。SP 挑战交给系统框架处理，识别 `AMSURLAction` 的无错误 retry 动作，至多注册并重试一次。许可和 ent/download 请求同样带新生成的证明，目标限制为固定 Apple 主机及路径。

原生桥接 `tools/StoreBagTransport.m` 在进程启动时初始化并保留系统 bag，配置请求使用固定 Apple Configurator `bag.xml?ix=6`。必须复用原请求上下文并保留 `X-Apple-Store-Front` 区域信息；清理 Cookie、Authorization、账号令牌和证明字段时不能一并清除区域配置。完整配置仍由系统解析，保留 trustedDomains 与 TLS 检查，不手工伪造注册结果。

## 诊断入口与判断

GitHub Actions 的 `store-login-diagnostic.yml` 只执行有界登录及清理，默认 `auth_route=bag`、`runner=macos-26-intel`；备用为 `macos-15-intel`。它先取得与源码和平台精确匹配的成功构建包，再读取 Secrets。默认生产验证不加载临时 DYLD 适配器。

| 现象 | 可确定的范围 |
| --- | --- |
| `validated_runtime_missing` | 运行包缺失、过期或源码指纹不匹配；先完成原生构建，不应重设账号 |
| 空 204、HTML 403/404、301 无 Location | 认证协议或服务响应异常；不能单凭状态码判定密码错误或 IP 被封 |
| SP 挑战 | 需要 Store 设备注册；不等于密码错误或已成功登录 |
| generic BadLogin | 原因仍不明确，不据此断言账号开启双重认证 |
| `plaintext_verified=true` | 已通过完整切片/页面校验；安装运行仍须另测 |

账号和模型只放 GitHub Secrets；诊断只输出固定类别、状态和计数，不公开原始响应、证明、Cookie、密码或会话。不要自动同意可选安全升级或新增条款，也不要遍历接口无限重试。

## 历史 plist-compat 实验

早期比较过固定 AssppWeb 与 ipatool 请求模板，`plist-compat` 只调整 plist Content-Type 和 attempt 值；没有证明这项调整单独恢复登录。它是 `store-download.yml` 的受控 Go 客户端对照，不是当前生产修复。历史运行与版本范围见[下载调查](DOWNLOADER.md)、[Swift 初次对照](NATIVE-STORE.md)及[项目状态](PROJECT-STATUS.md)。


## 中国区账号的独立接入状态（2026-11-09）

中国区模型恢复、跨运行器复用、保存状态重放和独立真实导出均通过。`/cn/` 链接使用国区账号，其余链接和数字 ID 使用原外区账号；国区支持免费最新版及可获取的历史版本。普通国区任务不挂载外区凭据、不预填验证码、不新增电脑授权；会话需要验证时由管理员维护。原德国区账号、模型和安全设置保持原样。详见 [中国区接入说明](CHINA-ACCOUNT.md)。

## 国区单应用许可失败的边界

抖音任务 [42566676227](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566676227) 的国区登录已经成功，失败发生在免费许可请求，不能将其当作验证码失效、密码错误或模型解密失败。出口 US 与地区不可用响应支持网络/地区兼容排查，但仍缺大陆出口对照。诊断标记不应进入原生错误启发式分类；固定响应类别和验证边界见 [当前国区限制](CHINA-ACCOUNT.md)。

## TF 使用独立保存会话（2026-11-09）

TF 普通任务恢复原独立虚拟 Mac 会话，不能把 App Store Cookie 当作已经验证的 TF 会话。Apple 明文仅在 GitHub worker 临时解封，VPS 状态助手保存会话密文及持久接受意图。普通任务不走密码/GSA登录，不重建身份、不使用聊天旧验证码、不新增 FairPlay 授权。会话拒绝或限流后明确停止，不能以自动重登、换身份或重复接受来掩盖失败。独立会话、实际取包与明文/交付证据见 [TF 记录](TESTFLIGHT.md)。
