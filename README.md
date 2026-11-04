# IPA Decrypt Lab

面向 Telegram IPA 服务的研发原型。**已验证原始 IPA 下载；尚未验证真实砸壳，也没有可收费的 TG 服务。**

## 当前结果

**已在 GitHub-hosted Mac 上生成非空 SIDB 系统授权状态文件；尚未恢复并验证可用模型，也没有已验证的砸壳产物。**

[增强后的 CommerceKit 试验](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41839179045)通过 95 项 Python、11 项 Swift 测试及原生检查。真实请求获得 keybag 和 diversitybag，HTTP 200、无业务失败码；服务端导入调用返回，后续同步从需要 diversitybag 变为不需要。管理员只读检查确认 `/private/var/db/fpsd/SC Info/SC Info.sidb` 从不存在变为非空普通文件。普通用户对该路径无读取权限，先前统一为 false 的检查无法区分权限不足和不存在，现已修正。

授权数量已纳入前后检查：最新完整试验 **2 → 3 台**，当前已确认占用 3 个名额。此前经用户明确同意，[单次全部解除授权](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41837099155)已确认 **5 → 0 台**；之后三次受控试验共占用了三个名额。不会把全部解除授权作为重复试验的清理方式。Apple 的五台上限与一年一次全部解除限制仍适用。[官方说明](https://support.apple.com/en-us/118292)。

| 环节 | 已验证结果 | 仍待完成 |
| --- | --- | --- |
| Swift 下载器登录 | 签名登录成功，真实账户摘要可读 | 原生 Music/AuthKit 登录失败仍是独立问题 |
| 电脑授权管理 | 实际数量读取成功；用户批准后单次解除成功；新授权前后检查已接入 | 不提高或绕过 Apple 的服务端数量上限 |
| CommerceKit 机器授权 | GUID、账号、令牌、User-Agent、Cookie 绑定通过；keybag 和 diversitybag 已取得 | 单向导入调用本身没有完成结果 |
| 系统授权状态 | 管理员确认 SIDB 从缺失变为非空；只读库存检查已区分权限和缺失 | 尚未确认 SIDB 格式、账号记录及 IPA 许可能用于模型恢复 |
| 原始 IPA | App ID 6599842047 已成功下载，检查到 62 个加密 Mach-O 切片 | 原始包仍是加密包 |
| 离线引擎 | 固定版本 UnfairPlay 已构建并通过合成测试 | 尚无匹配模型通过完整真实 IPA 校验 |
| Telegram / 收费服务 | 暂不接入 | 没有可交付的收费砸壳服务 |

[首次完整流程](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41841347693)通过 122 项 Python、20 项 Swift 测试及 Go/原生检查，实际完成一次授权、生成非空 SIDB、下载原始 IPA、提取候选应用包，但返回 `model_recovery_rejected`。没有产生模型、模型 Secret 或已验证砸壳包。旧错误摘要混入了恢复进度中的 SIDB/SINF 关键词，不能据此确定具体失败阶段。

后续已改为**下载并检查全部 IPA 许可后，再决定是否授权**；新增 `input-inspection` 模式只检查输入，不调用电脑授权。错误报告仅输出固定错误类别及阶段，不公开上游错误正文。传给恢复器的仍是 IPA 解出的候选应用包，没有声称它已安装或运行；上游格式与认证检查不被放宽。目前先运行不消耗新授权名额的输入检查。

原始账号、SINF、SIDB、IPA、模型及候选明文不会以明文进入仓库、日志或 artifacts。仅在模型与完整 IPA 校验通过后，模型才会封装为 GitHub 仓库公钥加密的 Secret 传输数据；这不包含可直接使用的模型明文。当前尚未产生该传输数据或配置 `FAIRPLAY_MODEL_B64`。

[完整研究记录与局限](OFFLINE-BACKEND.md)。较早的 AMS 直接导入错误、原生解密 EPERM、AuthKit/Music 登录失败以及 CommerceKit 3002 记录均作为历史证据保留，不代替上方最新结果。

## 当前阻塞：SIDB 与原始 IPA 已取得，但模型恢复被拒绝

现有下载器创建临时账号会话并生成下载用 kbsync；这条代码路径不创建离线引擎需要的系统 FairPlay enrollment 状态。

接入的 UnfairPlay 从已有的 Mac App Store 注册状态恢复模型。已核对的获取流程需要：在项目用 Mac 上登录原生 App Store，安装并打开一个兼容的 iPhone/iPad 应用，再使用匹配的原始 IPA 恢复模型。模型生成后可用于 Linux 离线解密；这不意味着模型的初次生成已能在无注册状态的 Linux 或 GitHub 运行器上完成。

Apple ID 密码、下载会话 token、SINF 文件和 kbsync 数据都不能直接作为该模型传入。同一 Apple ID 也不能代替对实际 IPA 与 enrollment 是否匹配的验证。

目前没有经过真实 IPA 校验的匹配模型。原生 UI 登录及独立 AuthKit 路径此前未成功；AMS 直接导入曾失败，但后续 CommerceKit 服务路径已经取得授权数据并生成 SIDB。生成文件仍不等于完整首次注册或模型恢复完成。keybag 返回、原生导入、模型恢复和真实 IPA 完整验证是分别检查的阶段，前一阶段成功不能代替后续证据。[源码依据与验收条件](OFFLINE-BACKEND.md#enrollment-bootstrap-source-review)。

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
| Confirmed all-computer deauthorization | 默认无网络预览；另设需明确确认的单次全部解除操作及前后数量检查 | 用户明确同意后真实执行一次，已确认数量从 5 变为 0；影响所有电脑且有一年一次限制 |
| Private Store computer authorization count | 默认无账号预检；查询模式使用下载器签名登录会话，只读当前电脑授权数量 | 已实际读到 5 台；不会解除授权，账号会话和响应正文不公开 |
| Private official Music account count | 默认无账号预检；查询模式单次完成邮箱、密码提交并尝试读取明确的当前授权数量 | 真实登录目前返回未知错误；未读到数量，不执行任何解除授权，不输出原始界面或认证日志 |
| Account-free official account-management UI capability | 启动官方音乐应用，检查 URL 处理程序、现有界面访问权限及固定菜单标签 | 无 Secrets、不登录、不点击菜单操作、不申请权限；界面可访问不等于已完成账户管理 |
| Account-free CommerceKit keybag prerequisite | 双架构固定测试值、普通用户/root 对照；检查客户端初始化与系统服务回复 | 不传入 Apple 账号，不提交服务器授权或导入；不输出同步数据 |
| Account-free CommerceKit invalid import observation | 固定无效数据、调用前后服务响应、状态标志与有界日志摘要 | 无账号；仅无效合成导入，不把调用返回当作成功 |
| Account-free CommerceKit request construction | 构造固定测试身份的请求，检查地址、方法与字段保留 | 无账号；不发送返回的授权请求 |
| Account-free keybag import rejection probe | 双架构无效 keybag/diversitybag、文件访问、普通用户/root 与超时清理检查 | 不传入账号、不发送授权请求 |
| Account-free FairPlay state visibility | 只读比较普通用户和管理员视角的固定状态文件及有界目录库存 | 无账号，不读取文件正文，报告缺失、权限不足及扫描限制 |
| Private same-runner model bootstrap | 先构建测试，再下载并检查输入；`trial` 才继续一次授权、恢复与完整校验 | 最新真实恢复被拒绝；`input-inspection` 不提交电脑授权；只有完整校验成功才生成加密模型传输数据 |
| Private native machine enrollment trial | 最多一次授权请求；可选 AMS 直接导入或 CommerceKit 系统服务；后者要求普通用户、登录 User-Agent 和 Cookie | 先运行无账号预检，最后一步使用 Apple Secrets；服务调用返回不代表导入成功 |

在 Independent Swift Store trial 中选择：

- `native`：下载原始 IPA 并执行 macOS 原生诊断。工作流成功可以只表示下载和诊断完成，不能据此认定砸壳成功。
- `offline`：下载后调用离线验证器。必须先配置匹配模型的 `FAIRPLAY_MODEL_B64` Secret；缺少模型时在登录、下载与依赖编译前退出。通过编码检查也不等于模型匹配。

真实 IPA、模型、账号信息和候选明文在运行器内部处理，不发布为仓库文件、公开日志或 Actions artifact。当前试验没有可领取的 IPA 下载产物；已准备的模型传输仅为不可由公众解密的 GitHub Secret 密文，不是公开模型或 IPA artifact。

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
