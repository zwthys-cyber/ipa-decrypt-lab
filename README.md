# IPA Decrypt Lab

面向 Telegram IPA 服务的研发原型。**已验证原始 IPA 下载；尚未验证真实砸壳，也没有可收费的 TG 服务。**

## 当前结果

最新只读结果：[下载器会话查询](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41834443913)已成功读取账号实际授权电脑数量：**5 台**。Swift 登录成功，账户摘要接口返回 HTTP 200 和 `authorizations.authorizedComputers = 5`；Linux/macOS 各通过 20 项 Python 测试，另通过 11 项 Swift 测试。无需用户另备电脑，也不依赖失败的“音乐”原生登录。**只查询了数量，没有申请新机器授权或解除任何授权，仍未取得模型或验证砸壳。** [详细证据](OFFLINE-BACKEND.md#downloader-session-account-summary-2026-11-04)。

此前的 [CommerceKit 真实试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41778198600)完成 59 项 Python、11 项 Swift 测试及原生检查。真实登录成功，原生 GUID 与下载器一致，账号、令牌、User-Agent 和 Cookie 已绑定；服务器返回 HTTP 200，但正文包含业务失败码 **3002**，并提到“五台电脑”。**没有 keybag，没有执行导入，也没有模型或已验证的砸壳产物。**

这比早先仅出现“五台电脑”措辞的成功发包响应更明确，强烈指向电脑授权数量限制；后续只读账户摘要已确认实际数量为 5；仍未取得各电脑的明细或归属，不能据此确定每个名额来自哪次试验。此前五次返回 keybag 的临时运行器试验可能计入授权，现有摘要无法确认。暂不重复真实授权请求，不自动撤销现有设备授权。Apple 官方说明最多同时授权五台电脑，可在 Mac/Windows 的“音乐”或 Apple TV 账户设置中核对数量；“全部解除授权”影响所有电脑，且一年只能使用一次。[官方说明](https://support.apple.com/zh-cn/118292)。

此前发现的会话绑定缺口已在[双架构检查](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41777147010)和[实际客户端预检](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41777899832)中补齐。原生 GUID 未被重写，绑定后同步数据、令牌和 needDiv 均保持一致。[最终无账号回归](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41778381405)在两个架构各通过 55 项 Python 检查及原生检查；无完成回调的服务后端不能被标记为直接导入成功。[完整证据](OFFLINE-BACKEND.md#commercekit-session-binding-and-server-refusal-2026-11-04)。

| 环节 | 已有证据 | 尚未完成 |
| --- | --- | --- |
| 下载客户端账号登录 | Swift 签名下载路径已成功登录，无需本次输入 OTP | 不代表系统 FairPlay 注册完成 |
| 原生 App Store 首次注册研究 | ARM 与 Intel 均完成原生表单提交；精确登录窗口已观察到 Anisette 获取及初始化失败 | 原生登录仍被拒绝，预期 SIDB/SIDS 未生成，未得到模型 |
| 独立 Anisette 与原生接入 | Linux / ARM Mac 初始化及复用成功；原生代理回调契约通过 | 实际 AuthKit 调用返回 XPC 4099，数据提供器未被调用，未生成模型 |
| 原生 keybag / 机器授权 | 统一登录与授权身份后，服务器返回 keybag 和 diversitybag；已补齐两步导入及文件访问诊断 | keybag 为 -42023、diversitybag 为 -42032；root 下仍失败，未取得模型 |
| App Store 守护进程 FairPlay 接口 | 双架构接口存在，固定零值和非零值对照完成 | 均返回 ASDErrorDomain 505，错误提到 entitlement，未生成请求数据 |
| CommerceKit 系统服务路径 | 双架构会话绑定和实际客户端预检通过；真实登录及 GUID/账号/令牌/User-Agent 校验通过 | 新授权返回业务错误 3002 并提到五台电脑；未发放 keybag，未进入导入 |
| 原始 IPA 下载 | 目标 App ID 6599842047 已成功下载并检查到 62 个加密 Mach-O 切片 | 原始包仍然加密，不是砸壳产物 |
| macOS 原生实验 | 62 次实际调用均返回 EPERM；已区分路径、文件布局和调用前检查 | 没有生成已验证明文；不能仅凭 EPERM 确定原因 |
| 离线解密引擎 | 固定版本 UnfairPlay 在 GitHub Linux x86_64 编译成功，相关 Go 测试及 52 项 Python 测试通过 | 缺少匹配的私有 FairPlay enrollment 模型，未验证真实 IPA 解密 |
| Telegram / 支付 / 交付 | 尚未实现 | 不应据此开通收费砸壳服务 |

可复查记录：

- [真实下载与原生诊断](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41736203256)：下载成功，原生解密未成功。[详细结果](NATIVE-DOWNLOAD-RESULTS.md)。
- [离线引擎构建与合成测试](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41737576446)：编译与测试成功，不涉及真实账号、IPA 或模型。[离线后端说明](OFFLINE-BACKEND.md)。

用户已说明该目标应用此前没有下载过。购买接口的通用 5002 响应仍标记为未确认，不能解释成“账号已经拥有此应用”。

最新进展：[真实机器授权试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41764672563)首次取得服务器返回的 keybag。该次试验在正文 xToken 已绑定、Cookie 已携带的基础上，使授权请求使用与登录相同的 User-Agent；服务器返回 HTTP 200，未含业务失败码，keybag 非空。23 项 Python、11 项 Swift 测试及原生合成检查通过。

[补齐 diversitybag 的真实试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41768524362)通过 37 项测试，确认服务器同时返回两份数据。客户端按 macOS 原生顺序分别导入，结果为 keybag `-42023`、diversitybag `-42032`，未触发重试。

[最新 root 对照](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41770295634)通过 40 项测试及原生检查。无账号对照先发现 ARM 普通用户存在 `EACCES`，root 下对应打开操作成功；但真实 root 试验中的两步导入仍返回上述错误，未生成已确认的授权状态或模型。文件访问诊断只覆盖指定函数，不能据此排除全部存储或权限问题。

该次响应还出现“五台电脑”相关措辞。现有关键词摘要不能确定已超限，也没有保存原始消息；暂不重复真实授权请求，不撤销其他设备授权。[最终无账号检查](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41770552591)在两个架构各通过 19 项 Python 测试及原生检查，包括 root 子进程超时清理。[完整证据与局限](OFFLINE-BACKEND.md#bounded-native-import-file-io-observations-2026-11-04)。

另有[App Store 服务对照](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41767422349)：接口存在，但固定测试值均返回 ASDErrorDomain 505，错误提到 entitlement，没有生成请求数据。这与 AMS 导入错误分开记录。**尚未取得模型，也没有已验证的砸壳产物。**

最新无账号进展：[CommerceKit 系统服务验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41774463734)在 ARM、Intel 各通过 7 项 Python 检查及原生检查。修复初始化调用的 ARC 所有权问题后，又根据系统实现改用受支持的 Configurator 客户端标识；两个架构的普通用户进程均成功创建合成账号、发出请求并收到非空测试用同步数据，回复要求 diversitybag。root 对照未通过接口检查，未发送生成请求。该次没有使用 Apple Secrets，没有提交服务器授权请求或导入 keybag，四个预期非空 SIDB/SIDS 标志仍为 false。**这是服务调用前提验证，尚不是账号注册、模型获取或真实解密成功。** [详细证据](OFFLINE-BACKEND.md#commercekit-service-prerequisite-2026-11-04)。

后续[无效导入与日志对照](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41775774340)在两个架构各通过 17 项 Python 检查及原生检查。无效数据的导入调用也会返回，服务之后仍能生成同步数据；ARM 日志窗口记录到两条导入失败消息，固定错误码摘要包含 `-42018`，Intel 没有匹配日志。四个预期状态标志均未变化，故仍记为 `submission_unverified`。

[未发送请求的构造检查](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41776353497)在双架构各通过 17 项测试：系统服务构造了目标地址正确的 HTTPS POST，保留固定同步数据、测试令牌和 needDiv，并加入六字节格式 GUID。但目标账号的 ownerDsid、X-Dsid 和 Configurator User-Agent 检查尚未通过；ARM 存在两项预期 Anisette 头，Intel 不同时具备。这些字段的存在不证明认证有效。这项较早的构造检查尚未绑定真实会话；后续绑定和真实服务器结果以上方最新记录为准。

用户目前没有可用电脑。官方“音乐”界面自动化已在 GitHub ARM、Intel Mac 上跑通：能够处理首次启动提示，进入“账户 → 登录”，并填入、清空未提交的合成邮箱。[双架构预检](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41828237601)通过。进一步的[真实登录诊断](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41830015849)完成邮箱和密码提交，但官方窗口显示“未知错误”，未确认登录成功。受限日志观察到服务端认证失败、SRP 服务端证明缺失（M2 missing）、AKAuthenticationError -7012 和 AppleIDAuthSupport 2；不能仅凭这些记录认定密码错误或双重认证已启用。**该原生 UI 路径尚未进入账户设置，也未执行解除授权。** 后续通过下载器会话直接读取账户摘要，已确认实际数量为 5；原生 UI 登录本身仍未修复。最新两个架构各通过 20 项 Python 测试、原生检查及无账号预检。手机端仍可通过 [Apple 支持](https://support.apple.com/zh-cn/contact)请求核对授权数量，但不保证能够重置限制。[研究详情](OFFLINE-BACKEND.md#official-music-ui-navigation-and-private-account-query-2026-11-04)。

## 当前阻塞：已确认 5 个电脑授权名额用满，模型仍未取得

现有下载器创建临时账号会话并生成下载用 kbsync；这条代码路径不创建离线引擎需要的系统 FairPlay enrollment 状态。

接入的 UnfairPlay 从已有的 Mac App Store 注册状态恢复模型。已核对的获取流程需要：在项目用 Mac 上登录原生 App Store，安装并打开一个兼容的 iPhone/iPad 应用，再使用匹配的原始 IPA 恢复模型。模型生成后可用于 Linux 离线解密；这不意味着模型的初次生成已能在无注册状态的 Linux 或 GitHub 运行器上完成。

Apple ID 密码、下载会话 token、SINF 文件和 kbsync 数据都不能直接作为该模型传入。同一 Apple ID 也不能代替对实际 IPA 与 enrollment 是否匹配的验证。

目前没有匹配模型，也没有在现有 GitHub-only 条件下完成首次注册。原生 UI 登录及独立 AuthKit 路径此前未成功；直接机器授权路径现已推进到服务器返回 keybag，但本机导入失败。keybag 返回、原生导入、模型恢复和真实 IPA 完整验证是分别检查的阶段，前一阶段成功不能代替后续证据。[源码依据与验收条件](OFFLINE-BACKEND.md#enrollment-bootstrap-source-review)。

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
| Account-free native authorization code inspection | 双架构检查指定原生函数的机器指令及令牌/认证类型来源 | 不传入账号，不读取私有运行时状态 |
| Account-free native request signing policy | 检查公开配置及原生 Mescal 签名策略；不发送授权请求 | 不传入账号 |
| Account-free App Store FairPlay service probe | 双架构检查本地 App Store FairPlay 服务能否为固定测试值生成请求 | 不传入 Apple 账号，不提交授权或导入 |
| Account-free official Music sign-in navigation | 识别欢迎页和可选提示，进入官方登录窗口，报告固定界面标签 | 不使用账号或提交凭据；不点击订阅、授权或安全升级 |
| Public Apple account frontend inspection | 从 Apple 公共配置跟踪账户摘要前端及只读查询格式 | 无账号，不执行前端脚本，不调用账户变更接口 |
| Private Store computer authorization count | 默认无账号预检；查询模式使用下载器签名登录会话，只读当前电脑授权数量 | 已实际读到 5 台；不会解除授权，账号会话和响应正文不公开 |
| Private official Music account count | 默认无账号预检；查询模式单次完成邮箱、密码提交并尝试读取明确的当前授权数量 | 真实登录目前返回未知错误；未读到数量，不执行任何解除授权，不输出原始界面或认证日志 |
| Account-free official account-management UI capability | 启动官方音乐应用，检查 URL 处理程序、现有界面访问权限及固定菜单标签 | 无 Secrets、不登录、不点击菜单操作、不申请权限；界面可访问不等于已完成账户管理 |
| Account-free CommerceKit keybag prerequisite | 双架构固定测试值、普通用户/root 对照；检查客户端初始化与系统服务回复 | 不传入 Apple 账号，不提交服务器授权或导入；不输出同步数据 |
| Account-free CommerceKit invalid import observation | 固定无效数据、调用前后服务响应、状态标志与有界日志摘要 | 无账号；仅无效合成导入，不把调用返回当作成功 |
| Account-free CommerceKit request construction | 构造固定测试身份的请求，检查地址、方法与字段保留 | 无账号；不发送返回的授权请求 |
| Account-free keybag import rejection probe | 双架构无效 keybag/diversitybag、文件访问、普通用户/root 与超时清理检查 | 不传入账号、不发送授权请求 |
| Private native machine enrollment trial | 最多一次授权请求；可选 AMS 直接导入或 CommerceKit 系统服务；后者要求普通用户、登录 User-Agent 和 Cookie | 先运行无账号预检，最后一步使用 Apple Secrets；服务调用返回不代表导入成功 |

在 Independent Swift Store trial 中选择：

- `native`：下载原始 IPA 并执行 macOS 原生诊断。工作流成功可以只表示下载和诊断完成，不能据此认定砸壳成功。
- `offline`：下载后调用离线验证器。必须先配置匹配模型的 `FAIRPLAY_MODEL_B64` Secret；缺少模型时在登录、下载与依赖编译前退出。通过编码检查也不等于模型匹配。

真实 IPA、模型、账号信息和候选明文在运行器内部处理，不发布为仓库文件、公开日志或 Actions artifact。当前试验没有可领取的 IPA 下载产物。

较早的原生 UI、AuthKit、Anisette、路由、Cookie、会话创建与正文令牌对照保留在 [OFFLINE-BACKEND.md](OFFLINE-BACKEND.md)。这些历史试验尚未获得 keybag；最新进展以上方真实机器授权记录为准。

用户提供的 [fairplay-decrypt](https://github.com/EthanArbuckle/fairplay-decrypt) 是可在 Linux / macOS 使用的离线解密器，但其凭据获取工具要求越狱设备及已安装应用；仅编译工具不能生成匹配的 16 字节账号凭据。它没有补齐当前 GitHub-only 首次授权缺口。

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
