# IPA Decrypt Lab

面向 Telegram IPA 服务的研发原型。**已验证原始 IPA 下载；尚未验证真实砸壳，也没有可收费的 TG 服务。**

## 当前结果

| 环节 | 已有证据 | 尚未完成 |
| --- | --- | --- |
| 下载客户端账号登录 | Swift 签名下载路径已成功登录，无需本次输入 OTP | 不代表系统 FairPlay 注册完成 |
| 原生 App Store 首次注册研究 | ARM 与 Intel 均完成原生表单提交；精确登录窗口已观察到 Anisette 获取及初始化失败 | 原生登录仍被拒绝，预期 SIDB/SIDS 未生成，未得到模型 |
| 独立 Anisette 与原生接入 | Linux / ARM Mac 初始化及复用成功；原生代理回调契约通过 | 实际 AuthKit 调用返回 XPC 4099，数据提供器未被调用，未生成模型 |
| 原生 keybag 前置条件 | ARM / Intel 已创建 FairPlay 上下文，生成合成 kbsync，构造并检查设备授权请求 | 尚未验证 Apple 签发、导入及模型恢复；合成请求不提交授权 |
| 原始 IPA 下载 | 目标 App ID 6599842047 已成功下载并检查到 62 个加密 Mach-O 切片 | 原始包仍然加密，不是砸壳产物 |
| macOS 原生实验 | 62 次实际调用均返回 EPERM；已区分路径、文件布局和调用前检查 | 没有生成已验证明文；不能仅凭 EPERM 确定原因 |
| 离线解密引擎 | 固定版本 UnfairPlay 在 GitHub Linux x86_64 编译成功，相关 Go 测试及 52 项 Python 测试通过 | 缺少匹配的私有 FairPlay enrollment 模型，未验证真实 IPA 解密 |
| Telegram / 支付 / 交付 | 尚未实现 | 不应据此开通收费砸壳服务 |

可复查记录：

- [真实下载与原生诊断](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41736203256)：下载成功，原生解密未成功。[详细结果](NATIVE-DOWNLOAD-RESULTS.md)。
- [离线引擎构建与合成测试](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41737576446)：编译与测试成功，不涉及真实账号、IPA 或模型。[离线后端说明](OFFLINE-BACKEND.md)。

用户已说明该目标应用此前没有下载过。购买接口的通用 5002 响应仍标记为未确认，不能解释成“账号已经拥有此应用”。

## 当前阻塞：解密授权材料

现有下载器创建临时账号会话并生成下载用 kbsync；这条代码路径不创建离线引擎需要的系统 FairPlay enrollment 状态。

接入的 UnfairPlay 从已有的 Mac App Store 注册状态恢复模型。已核对的获取流程需要：在项目用 Mac 上登录原生 App Store，安装并打开一个兼容的 iPhone/iPad 应用，再使用匹配的原始 IPA 恢复模型。模型生成后可用于 Linux 离线解密；这不意味着模型的初次生成已能在无注册状态的 Linux 或 GitHub 运行器上完成。

Apple ID 密码、下载会话 token、SINF 文件和 kbsync 数据都不能直接作为该模型传入。同一 Apple ID 也不能代替对实际 IPA 与 enrollment 是否匹配的验证。

目前没有匹配模型，也没有在现有 GitHub-only 条件下验证成功的首次注册实现。原生 UI 实验已证明 GitHub ARM 与 Intel macOS 运行器都能够操作 App Store；当前卡在原生账号登录被拒绝。后续将日志缩小到提交凭据后的 14 秒，观察到 Anisette 初始化失败及 -7018 与下层 Anisette 错误同条出现。独立 Anisette 组件现已在 GitHub Linux 和 ARM Mac 成功初始化；自定义提供器的本地原生回调已验证。一次受限 AuthKit 认证在系统进程通信处返回 XPC 4099，尚未调用提供器，未完成系统登录或生成 FairPlay 状态。仅重新编译、重复登录或重跑已失败的原生调用不会补齐这些材料。[源码依据与后续验收条件](OFFLINE-BACKEND.md#enrollment-bootstrap-source-review)。

## GitHub 验证入口

所有项目编译、测试和运行只允许在 GitHub-hosted Actions。

| 工作流 | 用途 | 账号及模型 |
| --- | --- | --- |
| Native engine feasibility | C 引擎跨平台编译、合成解析与调用对照 | 不使用账号 |
| Independent Swift Store trial | 手动执行原始下载及后续诊断 | 使用 Actions Secrets 中的 Apple 账号 |
| Offline engine contracts | 编译离线引擎并测试适配器 | 不使用真实账号或模型 |
| Native enrollment environment probe | 原生 App Store UI 探测与日志过滤测试 | 不传入账号 |
| Native App Store enrollment login trial | 有界限的原生账号登录研究 | 使用现有 Apple Secrets；未完成登录返回失败 |
| Independent Anisette prerequisite probe | 独立初始化、私有状态复用；Mac 上另查 AuthKit 接口元数据 | 不传入 Apple 账号，不发布认证数据 |
| Native Anisette callback contract | 用合成数据验证原生代理回调与缺失数据处理 | 不传入 Apple 账号 |
| Native AuthKit independent Anisette trial | 一次临时认证调用；通过私有管道按需获取新数据 | 仅最后一步使用 Apple Secrets；拒绝可选安全升级 |
| Account-free AuthKit transport diagnosis | 检查服务查找、客户端标识、进程权限与实际代理错误 | 不传入 Apple 账号；限时诊断 |
| Account-free native keybag prerequisites | 双架构检查 FairPlay 上下文、合成 kbsync、公开授权地址与请求边界 | 不传入真实账号，不提交授权请求 |
| Private native machine enrollment trial | 复用下载会话，检查身份后最多发起一次设备授权请求并单独检查 keybag 导入 | 最后一步使用 Apple Secrets；不导出会话或 keybag |

在 Independent Swift Store trial 中选择：

- `native`：下载原始 IPA 并执行 macOS 原生诊断。工作流成功可以只表示下载和诊断完成，不能据此认定砸壳成功。
- `offline`：下载后调用离线验证器。必须先配置匹配模型的 `FAIRPLAY_MODEL_B64` Secret；缺少模型时在登录、下载与依赖编译前退出。通过编码检查也不等于模型匹配。

真实 IPA、模型、账号信息和候选明文在运行器内部处理，不发布为仓库文件、公开日志或 Actions artifact。当前试验没有可领取的 IPA 下载产物。

[精确时间范围的原生诊断](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41746379142)：23 项检查和编译通过，登录仍被拒绝。[独立前置条件 Linux 试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41747047524)与[ARM Mac 复测](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41747343222)均成功，每次 7 项检查通过，均未使用 Apple 账号。后续[原生回调试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41748357798)已通过；[真实认证试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41749424573)的 16 项测试与编译通过，但认证调用返回 XPC 4099，提供器调用次数为 0。未启用双重认证升级，未得到 FairPlay 模型。[详细证据与边界](OFFLINE-BACKEND.md#native-callback-contract-and-private-authentication-trial-2026-11-04)。

[最新通信诊断](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41751601120)通过 13 项检查与原生编译。普通用户及管理员的 6 次实际请求都成功找到认证服务端口，随后返回 XPC 4099；另 2 次桌面上下文启动命令未执行成功，不能算成有效认证对照。[内部权限声明试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41750678118)中，自有程序两次被 SIGKILL 终止，该变体已移出后续工作流。本轮没有重新提交账号登录，尚未找到可用的首次模型生成方案。[证据与局限](OFFLINE-BACKEND.md#authkit-service-signing-and-caller-scope-controls-2026-11-04)。

[原生 keybag 前置验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41755075728)已在 ARM 和 Intel 上通过每架构 11 项 Python 检查及原生正反例。系统能创建 FairPlay 上下文，公开配置返回设备授权地址；合成会话请求可构造，但没有签发或导入 keybag，也未生成 SIDB/SIDS。真实会话试验另外执行，结果不得与此前置检查混同。[接口证据及候选项目核对](OFFLINE-BACKEND.md#native-keybag-prerequisites-and-upstream-candidates-2026-11-04)。

## 固定约束

- 直接通过 GitHub API 修改源码；不在 Debian 服务器或编辑工作环境构建、安装项目依赖、测试、执行项目代码或部署服务。
- 不使用用户个人 iPhone / TrollStore，不调用第三方解密服务。
- 公开仓库仅保存源码和合成测试材料。Apple 密码、账号密钥、模型、Telegram token、授权文件及真实 IPA 禁止公开。
- 用户拒绝可选的双重认证升级，不自动接受升级；通用登录错误不冒充确定的 2FA 提示。
- `cryptid=0`、返回码为零、文件内容变化、编译成功均不足以证明解密成功。
- 离线验证要求完整加密切片覆盖及可用的 CodeDirectory 加密前页面哈希匹配；这些检查不等于独立 Apple CMS 信任验证，也不证明应用可安装运行。
- Actions 仅用于限时研发验证，不是 TG 商业服务的长期运行主机。尚未部署生产服务。

## 模块与详细记录

- [下载接口实现](ENT-DOWNLOAD.md)：Swift 登录、ent/download、kbsync 辅助程序。
- [原生实验结果](NATIVE-DOWNLOAD-RESULTS.md)与[后续分析](IOS-DECRYPTION-FOLLOWUP.md)。
- [离线引擎、模型要求与上游许可](OFFLINE-BACKEND.md)。
- [旧版 Go 下载器说明](docs/DOWNLOADER.md)：保留作早期实现记录；当前已验证的下载路径是上述 Swift 工作流。
- [项目执行约束](AGENTS.md)。

C 解析器、IPA 审计器、编排层及接口适配由本项目实现；下载与离线后端使用锁定提交的开源组件。现阶段不能把整个方案描述为“无第三方解密库”。

接口与格式参考：[Apple XNU](https://github.com/apple-oss-distributions/xnu)、[GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。上游组件与许可见各模块文档。
