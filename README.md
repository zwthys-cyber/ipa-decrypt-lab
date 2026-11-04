# IPA Decrypt Lab

**已在 GitHub-hosted macOS 上恢复 FairPlay 模型，并验证指定应用的原始 IPA 解密。** Telegram 接入、应用安装运行及收费服务尚未完成。

## 当前结果

[完整成功试验 41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942)在全新 GitHub 运行器上完成：

1. 下载 App ID **6599842047** 的原始 IPA，并检查许可格式。
2. 提交一次 CommerceKit 电脑授权，取得 keybag / diversitybag，并生成受保护的 SIDB。
3. 从系统授权状态和提取的候选应用包恢复模型。
4. 使用恢复出的模型再次检查完整 IPA：**62 个加密切片、12,524 个页面通过明文校验**。
5. 将模型及有界的授权检查点分别封装为仓库公钥密文，保存到 `FAIRPLAY_MODEL_B64` 与 `FAIRPLAY_STATE_B64` GitHub Secrets。

最终状态为 `model_recovered_and_verified`，`model_recovered=true`、`decryption_proven=true`、`plaintext_verified=true`。恢复器自身检查和独立完整 IPA 复核均通过；不是仅修改 `cryptid` 或以编译成功代替解密成功。

成功流程通过 140 项 Python、20 项 Swift 测试及 Go/原生检查。私有检查点另通过 [GitHub Linux 上的 29 项 Python 和加密合约测试](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41845171020)。

[全新运行器复用验证 41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302)也已通过：读取保存的模型、重新下载原始 IPA，再次校验 **62 个加密切片、12,524 页**。该流程不调用机器授权；同时通过 273 项 Python、9 项 Swift、4 项 C 测试及 Go 检查。

| 环节 | 已验证结果 | 边界 |
| --- | --- | --- |
| 原始下载 | Swift 签名登录与真实 IPA 下载成功 | 需要账号对目标应用拥有下载许可 |
| 电脑授权 | 真实数量读取、经批准单次全部解除、新授权均成功 | 最新实测 **3 → 4 台**；不提高服务端上限 |
| 授权状态 | 管理员读取到非空 SIDB，并用于成功模型恢复 | CommerceKit 单向导入调用本身仍没有完成回执 |
| 模型恢复 | GitHub macOS 上真实恢复并保存加密模型 | 未声称已安装或运行候选应用 |
| IPA 解密校验 | 指定原始 IPA 的 62 个加密切片、12,524 页通过 | 尚未独立验证 Apple CMS 信任或应用安装运行 |
| 模型复用 | 已在全新运行器使用 Secret 再次完成真实 IPA 校验 | 不推断所有账号、应用、版本都兼容 |
| Telegram / 收费服务 | 按当前要求暂不接入 | 没有已部署的收费服务 |

此前经用户明确批准，[单次全部解除授权](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41837099155)已确认 **5 → 0 台**，之后四次授权试验合计占用四个名额。不会把全部解除授权作为重复清理方式。Apple 的五台上限和一年一次全部解除限制仍适用。[官方说明](https://support.apple.com/en-us/118292)。

## 验证范围与私有数据

成功路径使用 GitHub-hosted macOS、CommerceKit 系统服务和从原始 IPA 提取的候选应用包。没有使用个人 iPhone / TrollStore、单独的实体 Mac、原生 App Store UI 登录或第三方解密服务。

模型与授权检查点的明文只在 GitHub 运行器私有临时目录中处理。公开日志仅包含固定结果和 GitHub 仓库公钥密文；只有 GitHub 保存的私钥能解开这些传输数据。两种 Secret 的用途和格式分别校验，模型必须通过完整 IPA 复核后才保存。

`FAIRPLAY_STATE_B64` 仅包含固定 SIDB/SIDS 文件和必要硬件标识，不包含 IPA、Apple 密码或登录会话。它用于复用授权状态研究兼容性，不能单独当作已验证模型。实际检查点捕获和加密已成功；从该 Secret 重建状态的真实重放正在验证中。

本次候选明文在验证后删除，没有公开可下载的砸壳 IPA；`runtime_verified=false`。源码中已有真实解密后端，但生产交付、私有下载存储、计费及 Telegram 接入是后续工作。

较早的同运行器试验曾返回 `model_recovery_rejected`。成功版本调整了下载/授权顺序、改进了诊断并加入检查点，也更换了运行器；这些不是单变量对照，尚不能把第一次失败归因于某一个变化。[完整研究记录](OFFLINE-BACKEND.md)。

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
| Private Store computer authorization count | 默认无账号预检；查询模式只读当前电脑授权数量 | 查询机制已验证；最新完整授权试验读到 4 台，原始账号会话和响应正文不公开 |
| Private official Music account count | 默认无账号预检；查询模式单次完成邮箱、密码提交并尝试读取明确的当前授权数量 | 真实登录目前返回未知错误；未读到数量，不执行任何解除授权，不输出原始界面或认证日志 |
| Account-free official account-management UI capability | 启动官方音乐应用，检查 URL 处理程序、现有界面访问权限及固定菜单标签 | 无 Secrets、不登录、不点击菜单操作、不申请权限；界面可访问不等于已完成账户管理 |
| Account-free CommerceKit keybag prerequisite | 双架构固定测试值、普通用户/root 对照；检查客户端初始化与系统服务回复 | 不传入 Apple 账号，不提交服务器授权或导入；不输出同步数据 |
| Account-free CommerceKit invalid import observation | 固定无效数据、调用前后服务响应、状态标志与有界日志摘要 | 无账号；仅无效合成导入，不把调用返回当作成功 |
| Account-free CommerceKit request construction | 构造固定测试身份的请求，检查地址、方法与字段保留 | 无账号；不发送返回的授权请求 |
| Account-free keybag import rejection probe | 双架构无效 keybag/diversitybag、文件访问、普通用户/root 与超时清理检查 | 不传入账号、不发送授权请求 |
| Account-free FairPlay state visibility | 只读比较普通用户和管理员视角的固定状态文件及有界目录库存 | 无账号，不读取文件正文，报告缺失、权限不足及扫描限制 |
| Private same-runner model bootstrap | `preflight` 无账号测试；`input-inspection` 检查许可；`trial` 授权并恢复；`checkpoint-replay` 复用私有状态 | 真实恢复和完整 IPA 校验已通过，模型及状态 Secret 已保存；真实检查点重放尚待验证 |
| Private native machine enrollment trial | 最多一次授权请求；可选 AMS 或 CommerceKit 系统服务 | 单独授权试验不验证模型；优先使用已保存模型，避免重复占用名额 |

在 Independent Swift Store trial 中选择：

- `native`：下载原始 IPA 并执行 macOS 原生诊断。工作流成功可以只表示下载和诊断完成，不能据此认定砸壳成功。
- `offline`：使用已配置的 `FAIRPLAY_MODEL_B64`，下载后调用离线验证器。若 Secret 缺失，会在登录、下载与依赖编译前退出；实际成功仍必须通过完整 IPA 校验。

真实 IPA、模型、账号信息和候选明文在运行器内部处理，不以明文发布为仓库文件、公开日志或 Actions artifact。当前没有可领取的 IPA 下载产物；模型和授权检查点已通过仓库公钥密文传输并保存为 GitHub Secrets。

较早的原生 UI、AuthKit、Anisette、路由、Cookie、会话创建与正文令牌对照保留在 [OFFLINE-BACKEND.md](OFFLINE-BACKEND.md)。这些早期失败不能代替上方最新成功的模型恢复与完整 IPA 校验记录。

用户提供的 [fairplay-decrypt](https://github.com/EthanArbuckle/fairplay-decrypt) 是可在 Linux / macOS 使用的离线解密器，但其凭据获取工具要求越狱设备及已安装应用；仅编译工具不能生成匹配的 16 字节账号凭据。它未用于本次已验证的 GitHub-only 模型恢复路径。

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
