# TestFlight 自动处理与验证记录

2026-11-27当前TF入口已接入Cloudflare/D1 + CircleCI，原独立会话密文、历史接受确认tombstone及已确认私有回传去重已完成离线交接；原运行环境退出派发。没有重新接受原邀请或重复旧文件发送。具体见[操作手册](OPERATIONS.md)。

新平台真实TF请求尚未单独验收；下文2026-11-09的CapyPlayer/A.I.下载解密与Telegram附件回执属于旧平台证据，不能直接写成CircleCI上已经重测。新入口只有主人，外部任务号为pilot_，完成后通知私有Drive链接；tf_是内部请求前缀。

## 原运行环境状态与真实证据（2026-11-09，历史）

主人在机器人私聊中发送完整 Apple TF 邀请链接，即进入独立的 `tf_` 任务队列。后台恢复已保存的独立虚拟 Mac 会话，查询资格；必要时先持久记录接受意图，再发送一次接受请求，并通过账号目录核对实际成员资格。已有资格时不重复接受。随后获取可用 iOS 测试构建，校验目标、解密全部受保护页面、清除账户数据，并交给原有主人私聊交付链路。

这条路线不使用 App Store 正式版替代测试包。普通任务不重新输入账号密码，不获取新验证码、不恢复新模型或新增电脑授权。白名单其他用户暂不开放 TF；指定 App Store 历史版本不适用于此入口。

| 验证 | 结果 |
| --- | --- |
| 持久会话 | [42703942768](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42703942768) 保存原 SDK 身份与 TF 上下文的私有 age 密文，零 Apple 请求、零新身份 |
| 新链路只读资格验证 | [42705631442](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42705631442) HTTP200、成员资格通过，没有接受、下载或发文件 |
| 通用 worker 实际导出 | [42712411043](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42712411043) 完整明文验证；没有新接受邀请、电脑授权或文件发送 |
| 最新控制器部署 | [42714903713](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714903713) Beta 命名、运行包/真实导出门禁和部署健康检查通过 |
| 真实新用户请求 | [42714371079](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) CapyPlayer 46镜像/17,724页通过，用户截图确认收到文件 |

用户提供的 Telegram 截图已确认一条真实新请求收到 `CapyPlayer_1.1.7.ipa`。对应 [42714371079](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) 的请求 `tf_8e5cbf63015f20a321641f38f42833bc` 完成46个加密镜像、17,724页的严格明文验证；已有成员资格，没有新接受邀请或电脑授权。截图是文件接收证据，worker 的 `delivered=false` 仅表示它本身不负责 Telegram 发送。

TF 文件名现包含英文 `Beta`，例如 `CapyPlayer_Beta_1.1.7.ipa`；只改变未来 Telegram 文件名称，不修改应用包内容，App Store 命名保持原样。[部署42714903713](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714903713) 在源码 `d53f7defdc65fb11e5b3c04ac3e612990ed6430c` 通过两套 Mac 运行包、CN运行包及 [无重复发送导出42716962584](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42716962584) 门禁，服务健康检查通过。本次没有重发此前IPA。

安装运行、所有 TF 应用的模型兼容性和到期限制处理均未验证。

会话密文持久保存在 VPS 私有状态目录，Apple 明文上下文只在 GitHub worker 临时目录中解封；VPS 状态助手不解密 Apple 状态，也不调用 Apple。原有 CN/外区 Secrets、模型和授权数量不变。私有 IPA、进度和结果 artifact 仍只保留一天，公共原生运行包保留30天；普通任务只加载来源、平台、ABI匹配的成品，不重新编译 SDK。

失效会话、限流、需要额外协议、资格不明或明文验证失败都会停止，不自动密码重登、换身份、重复接受或伪造明文证明。接受意图即使超时也不自动失效重发；先查资格，再由主人处理异常。必须保留原邀请意图以及 VPS 接受/发送记录。

下面保留当天的研究过程。历史段落中的“尚未实现”按当时日期与阶段理解，不代表当前状态。


## 2026-11-09：早期 A.I. 公开入口检查（历史）

用户提供的 [公开邀请](https://testflight.apple.com/join/yoNuHexZ) 可通过无凭据 HTTPS GET 取得 HTTP 200 页面。Apple 页面标题为 A.I. beta，标注 iOS，并提供同一邀请码的 `itms-beta://testflight.apple.com/join/yoNuHexZ` 跳转。它没有在公开 HTML 中提供 IPA、构建编号或应用下载许可证。

该观察只证明公开预览入口可访问，不证明测试名额、设备条件、测试账号资格、当前有效构建或包下载可用。没有加入测试、接受条款、登录 Apple 或发起 IPA 下载。

## 早期检查时的实现状态（历史）

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

用户已明确要求由机器人后台账号自动接受邀请、取包、解密并回传；不要求请求用户逐条手动加入。现在按后台认证 → 查询邀请 → 有界接受 → 读取构建 → 取包 → 校验解密的完整链路验证。日常邀请接受已获授权；账号初始化中的验证码或新条款仍须各自实际触发后处理，不能假装已具备有效会话。会话等私有材料只能通过受保护配置处理，不进入聊天、源码、公共输入或日志。

取到实际测试包后，先核对构建、Bundle ID、架构、加密切片和授权材料，再判断现有模型是否兼容。未通过完整明文校验前不得宣称 TF 解密成功；也不能从 TF 包直接推广安装运行或修改到期限制的能力。

所有代码执行、测试和构建继续在 GitHub-hosted Actions，VPS 只运行已验证成品；本次没有改动运行代码、部署、原德国区/CN Secrets 或已有模型，也没有使用个人手机作服务端基础设施。

## 后台自动化验证

`testflight-prototype.yml` 当前先做无凭据公共预检：读取 GitHub Mac 的真实原生标识及机器证明，构建固定提交的 TestFlight SDK，并测试协议/传输。没有真实标识时拒绝用示例 iPhone 或随机硬件值替代。后续后台测试拟使用独立国区账号会话，保留原德国区路线；真实邀请接受、安装包与解密结果分别记证据。

## 2026-11-09：原生报告修复与实际能力边界

[预检 42644646891](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42644646891) 在源码 `2af2dd9343ac107478c56b0a2965df0d51e38e3b` 上通过 6 项报告测试、3 项 CN 会话结构测试及 16 项 CTest。上游固定版本本身未注册测试；此前的 ctest 显示 “No tests were found”，仅证明编译成功。本次显式启用 CTest，增加无效会话不得发起网络请求及传输参数长度的合成校验，并要求零测试时报错。测试通过不证明真实 TF 认证或内容解密。

发现并修复报告序列化问题：Objective-C 对比较表达式直接装箱会生成整数，导致 Python 的严格布尔校验拒绝整个报告。现在显式通过 BOOL 装箱，Python 保留严格类型要求。新增诊断只发布预设阶段、退出码、输出大小和受限字段类型，不输出原始 stdout/stderr、标识或证明头。

格式修复后的真实报告为 `tf_native_context_unavailable`：AuthKit 标识字符串长度 36，不能由当前适配器识别为 SDK 要求的 hardware20；Mac 型号可读，机器证明头不可用。不能将 UUID 任意填充或截断后冒充已验证身份，也不能把缺少证明头理解成登录成功。原生就绪门禁按预期停止任务；本次没有挂载账号输入、登录 Apple、接受邀请、取包或交付。

后续需要验证受支持的 Mac 身份映射与机器证明获取方法，再接独立 TestFlight 认证。当前 App Store 机器人运行路线没有修改。原德国区/CN Secrets、FairPlay 模型与授权数没有改变。

## 2026-11-09：原生接口扫描与邀请适配器

[接口验证 42646358995](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42646358995) 在源码 `f2162fbd535962de4f625b64be189b3d1fd0a130` 完成 13 项 Python 测试和 16 项 CTest；原生能力门禁仍按预期失败，因此不能将整个运行标为成功或声称已认证。凭据无关的发现程序自检通过，公开信息仅含类型/长度、框架可用性及框架自身的类/选择器名，不含真实标识、账号或原始框架日志。

实际检查到 AuthKit 字符串长度 36、AMS deviceGUID 字符串长度 12，均不匹配 SDK hardware20。StoreServices 框架可加载，但该运行环境未找到所查 SSDevice 接口。TestFlightCore 可加载，读取了设备/标识相关的 Objective-C 接口元数据；这次有界扫描未找到可直接取得 hardware20 的方法。不据此断言所有原生或其他平台路径都不可能。

另纠正当前前置探针的适用范围：固定 SDK 的 `StoreSession::testflight_context()` 明确要求 `macos_accounts` 会话，并从会话内的 machine_id 注入 X-Apple-AMD-M。它不是要求在账号登录前从 AMSAnisette 获取这个头。现有 Configurator 会话不能直接作为该 Mac Store 会话。因此旧探针缺少该头不单独证明平台无法认证；它只是当前探针未建立完整环境。

`.github/ops/tf_invitation.py` 新增离线请求计划与 SQLite 接受意图记录：严格限定 Apple join 链接与固定 API 地址；POST 前持久化意图，重启/任务号变化后不自动重复接受；2xx 仅标记需要校验，绝不当作已加入或已下载。4 项邀请测试覆盖伪装域名、路径/查询注入、响应分类及跨连接重启恢复。实现未接机器人、未签名或发送真实邀请请求，未复用抓包会话头。

当前 GitHub 原生路径仍缺可验证的 TF hardware20 与独立 Mac Store 会话。SDK 文档公开支持虚拟设备身份，但项目当前约束要求原生身份；在这项约束改变前，不将虚拟配置伪称成原生设备，也不挂载账号去运行该替代路线。两条路线的认证、邀请、取包、解密与交付仍需分别提供真实证据。没有修改既有账号 Secrets、模型、授权数或 VPS 部署。

## 2026-11-09：独立虚拟 Mac 路线与真实验证码要求

用户确认继续评估 SDK 的虚拟身份路线。此路线使用明确标注的独立虚拟配置，不代表恢复了真实硬件标识，也不使用个人手机作后端。

- 公共预检 [42650011477](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42650011477) 通过 10 项 Python 与 17 项 CTest，包含虚拟状态加密恢复、错误密钥拒绝和平台绑定检查。
- 初次认证 [42650873653](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42650873653) 完成 GSA 设备预配，登录失败；独立状态只保留为固定既有收件人的 age 密文。
- [42652233101](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42652233101) 校验原运行、源码、ZIP 摘要及密文摘要后成功恢复同一身份，实际错误分类为 transport_timeout。没有新建替代身份。
- 无账号网络对照 [42653392877](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42653392877) 中，系统及 SDK curl 的 GSA lookup 都迅速返回 HTTP 401，公开 bag 返回 200；未观察到 HTTP/1.1、IPv4 或两种 curl 的差异。
- 机器头只读对照 [42654419361](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42654419361) 复用相同虚拟身份，命令行 curl 与 SDK lookup 都返回 200，未挂载 Apple 账号或密码、未发送账号登录请求。它证明该查询可用，不证明账号或完整 Anisette 已认证。
- 分阶段认证 [42655279948](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42655279948) 实际进入 verification_required，HTTP 200。该版本检测到要求后退出，未保持可提交验证码的进程；之后收到的聊天验证码没有提交，也没有写入公开记录。
- 保持进程等待的实现已通过 19 项 Python、2 项 Node 中继控制以及 17 项 CTest；[42656943897](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42656943897) 的真实尝试则在 gsa_srp_complete 超时，尚未产生等待请求。后续尝试同样必须以真实等待请求为准，不能盲目使用聊天中的旧验证码。

`tf_virtual_live.py` 复用现有维护中继的运行/源码/nonce/五分钟有效期协议。只有 SDK 的实际验证码回调才能发布等待请求；同一进程保持 stdin 等待，最多接收一次验证码。新的中继密文仅能投递到该请求对应的临时 `tf-virtual-code-<run>-<nonce>` 分支 `relay.json`，内容为 age 密文和非秘密绑定信息；runner 解密并校验后才写入原进程。原始验证码不得进入源码、工作流输入、公共 artifact 或日志，使用后清理中继文件。

截至这些证据，尚未取得 GSA 账号令牌、Mac Store/TestFlight 会话；没有接受 yoNuHexZ 邀请、下载 beta、证明 TF 内容解密或交付文件。原 DE/CN Secrets、FairPlay 模型、授权计数与 VPS 成品部署未改动。独立状态密文 artifact 保留一天；缺失/过期时必须显式失败，不能暗中新建身份冒充恢复。

### 本轮最终受限重试

[42657854276](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42657854276) 在相同源码 `39999fb59146e6a1954a89db264676a05a340037`、相同恢复身份下完成两次受限运行，公共检查均通过；实际认证均为 `last_request_stage=gsa_srp_complete`、`transport_timeout`、HTTP 状态 0、未取得 Apple 错误码。没有产生可提交验证码的等待请求，没有中继文件投递，没有使用聊天验证码。先前一次实际进入验证要求的证据仍然有效，但不能推广成稳定登录成功。

目前没有活跃验证码会话，GSA/Mac Store/TF 会话仍未取得。后续若继续，先区分 SRP 完成请求的协议兼容与服务响应问题；不要继续凭旧验证码或普通重试宣称修复。只有新的真实等待请求建立后才能要求新验证码。

## 2026-11-09：真实验证码中继与 GSA 令牌取得

[新连接对照 42660282023](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42660282023) 记录各段独立连接，SRP 完成请求 379ms 返回 200；真实等待请求发布后，新的验证码通过 source/run/nonce/期限绑定的 age 密文进入同一进程。随后响应处理失败，不能凭 HTTP 200 声称验证通过。中继文件及本地临时明文均已清理。一次对照不足以证明此前所有超时均由连接复用造成。

对固定 SDK 另加两项独立兼容修复：每次 SRP 交换复用相同机器证明/CPD；验证码校验识别 Response/Status 包装，仍要求明确的整数 ec=0，拒绝缺失、非零、布尔/字符串成功值及冲突状态。新增原生合成控制证明两段 CPD/头一致，错误服务器 M2 证明仍被拒绝。对照参考 [SideInstaller 实现](https://github.com/FrizzleM/SideInstaller/blob/main/ish/sideinstaller.py)，未运行第三方服务或放宽密码/证明校验。

[42662277216](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42662277216) 在源码 `084ad0d0ce7ac83610515a8418483034ee5a0ba0` 通过 26 项 Python、2 项 Node 与 18 项 CTest。真实验证码已送入绑定进程，验证响应为顶层明确整数 ec=0，随后 SRP 重新认证取得 GSA 令牌（gsa_authenticated=true）。本次真实响应未触发新增的 Response 包装分支，不能把实际成功单独归因于该兼容分支。

之后 Mac Store 阶段返回 HTTP 429，尚未取得 Mac Store 或 TF 会话。包含 GSA 令牌的独立状态已 age 加密，artifact 为 tf-virtual-sealed-42662277216-attempt-1，ZIP/密文摘要在恢复器中固定。原虚拟身份 origin 仍是 42650873653 / 19244adbe73f71156a91a5c1cb20965925928054，不把新的状态载体误作新设备。

下一控制使用已验证 GSA 会话，先检查 PET 绑定和有效期，再在本地 600 秒冷却策略后恢复 Mac Store 步骤；该等待值是未记录到 Retry-After 时的本地保守策略，不是已观测的 Apple 指令。恢复工作流不挂载 Apple 密码、不重新执行 GSA 密码登录，过期即停止。后续响应会记录受限的 Retry-After 数值以遵守服务端等待要求。没有 TF 邀请接受、下载、内容解密或文件交付证据。


## 2026-11-09：短期 PET 到期与会话恢复控制

[保存会话恢复 42665103395](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42665103395) 在本地有效期检查处停止，没有向 Apple 发送请求。[离线会话检查与设备预配 42667404119](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42667404119) 通过 33 项 Python、2 项 Node、18 项 CTest；确认账号/PET 绑定匹配、到期字段是整数，但 PET 已过期。按取得令牌与到期时间推算，其有效期约五分钟，不能跨越先前十分钟的冷却等待。

会话中仍有应用令牌交换所需的根密钥、挑战和 IDMS 令牌。Store 设备预配直接命中已存 ADI 状态，无网络请求；这尚未证明 Store SAP 签名准备或账号登录成功。

源码 `84d707a7f39cc866517bdb9f5575ded06d68c2cb` 增加独立控制：先在同一 Client 进程完成 Store SAP 签名准备，再以保存的根会话仅请求固定 PET，并立即尝试 Store 登录。新增合成控制检查请求范围/HMAC、AES-GCM 解密以及篡改标签拒绝；这些测试不证明 Apple 允许本次根会话刷新 PET。工作流不挂载账号密码或验证码；拒绝即停止，不自动退回密码登录。原账号 Secrets、模型、授权计数和 VPS 部署保持原样，真实 TF 邀请、取包与解密仍未验证。

[固定 PET 刷新 42670588627](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42670588627) 通过 33 项 Python、2 项 Node、19 项 CTest，实际应用令牌请求返回 HTTP 200、Apple 错误码 -22413。未取得新 PET，没有执行密码或验证码登录；不能仅凭此判定是不支持该 scope 还是根会话失效。

进一步源码检查发现 SDK 的通用 provision_store 默认选用 android_music，而 PET 登录显式使用 macos_accounts。修正源码固定校验 client.cpp，并为 Mac 选择后者，确保准备与登录共享实例。此前命中的缓存设备状态不能作为 Mac SAP 签名成功证据；后续先运行不挂载账号数据的签名控制。

[明确 Mac 路由的签名控制 42670934355](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42670934355) 通过 33 项 Python、2 项 Node、19 项 CTest；实际完成 Mac SAP 签名准备，最终 HTTP 200，没有账号登录。SAP 会话只保存在内存，不能把密文设备快照当作签名会话持久化。下一次显式独立维护会在同一 Client 内先完成签名准备，再执行密码/SRP 和真实验证码维护，并立即使用新 PET 登录 Store。仅在发布有效的真实等待请求后要求新验证码，不重用聊天旧码。


## 2026-11-09：当前调度阻塞

源码 `637da0b6683f0f3e2115d7fafaaf821cc54f659b` 已把显式完整认证调整为同一 Client 内先准备 Mac SAP、后执行密码/SRP，并把诊断 transport 传入 TF 客户端。这一新的完整顺序尚未实际运行验证，不能拿此前签名控制的成功替代完整认证证据。

[42672190788](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42672190788) 与确认无执行后的一次有界重试 [42672595272](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42672595272) 均没有生成 job/runner，注释明确为 GitHub `Internal server error`。第二次源码为 `610e5ccc95ee1b07dbc0cbd1a26e6c7d75f29df1`。未执行私有步骤、密码认证或验证码投递；当前没有有效验证码等待请求，聊天旧码不会使用。调度恢复后继续显式独立维护，不根据服务器内部错误连续盲目提交重试。TF 会话、邀请接受、beta 获取、内容解密及交付仍未验证，原 Secrets、FairPlay 计数和 VPS 未改动。


## 2026-11-09：调度恢复、缓存验证与 Store 响应定位

[42675996429](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42675996429) 已正常启动并取得新 GSA 令牌，没有验证码要求；Store 阶段返回429，并实际记录 Retry-After18秒。随后无密码恢复 [42676403958](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42676403958) 因重新编译耗时，开始私有步骤时 PET 已过期24秒，本地门禁停止，未发送 Apple 请求。

为避免继续耗尽五分钟窗口，公共构建 [42677280328](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42677280328) 保存了账号输入之前的已验证构建缓存。缓存严格匹配源码/SDK、Mac平台/架构、Xcode和依赖版本；只保存 tf-sdk-build，账号状态仍在独立临时目录和一天有效的 age 密文中。每次复用重新运行全部19项 CTest，Python/Node检查照常执行；改变构建命令/选项须升级缓存版本。

[新 runner 42677692634](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42677692634) 实际命中缓存、跳过编译并通过19项 CTest，再次取得 GSA 令牌；Store 返回429/Retry-After17秒。新的恢复载体及摘要已固定到恢复器，保留原虚拟身份绑定。

[无密码恢复 42677924391](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42677924391) 遵守冷却时间，令牌绑定有效且还剩221秒，已实际进入 Store 步骤。最后响应是HTTP200，随后发生未分类错误；仍没有 Store/TF 会话。旧报告只给出 other_apple，尚不能断定最后响应来自 SAP准备还是账号认证，也不能认定限流已完全解除。后续补充固定阶段和错误类别，只做公共验证；不公开原始响应、不自动重试账号登录。当前没有验证码等待请求，邀请接受、取包、TF内容解密及回传仍未完成。


### 已确认账号认证接口，尚未建立 Store 会话

[诊断公共构建 42678311930](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42678311930) 通过隐私/状态检查及19项 CTest，缓存对应的新程序，没有执行账号步骤。[42678760191](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42678760191) 在新 runner 命中该缓存并重新通过19项 CTest，签名及 GSA 认证成功，无验证码回调；固定请求形状将最后HTTP200明确定位到 store_authentication。

随后仍发生未分类处理错误，没有建立 Store 会话。“Mac Store authentication rejected”固定类别没有匹配，所以不能断言具体服务器拒绝信息或解析原因。下一步应先补充受限的响应格式/字段结构及明确解析错误类别，再开展新的账号控制；不公开原始正文或错误文字，不放宽签名、plist和会话校验，不继续盲目重复登录。

本轮解决了调度阻塞与跨运行重新编译耗尽令牌的问题，实际证明可在剩余221秒时恢复保存令牌；还未完成 Store/TF 会话、邀请接受、测试包获取与解密回传。目前没有验证码等待请求。最新独立状态仍只保留一天的 age 密文，原账号 Secrets、模型、授权计数和部署未改动。


## 2026-11-09：修复 Store 布尔类型并取得真实 TF 会话

真实响应诊断确认 Store 返回可解析 XML/plist、整数 status=0，账号和令牌字段存在；故障定位为本地 Cookie 校验。无账号的原生合成测试复现：SDK 将 CFBooleanGetValue 返回的 Boolean 字节直接转为 JSON 整数。固定源码摘要后显式转为 C++ bool，保留真假值，同时继续拒绝整数冒充布尔和外域 Cookie。原生20项检查通过。类型定义可核对 [Apple CFNumber.h](https://github.com/apple-oss-distributions/CF/blob/main/CFNumber.h) 和 [CFBase.h](https://github.com/apple-oss-distributions/CF/blob/main/CFBase.h)。

[离线检查42686722193](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42686722193) 只解密已绑定快照，确认账号匹配、10个保留 Cookie 的类型/域名/路径等约束均正确，没有调用 Apple 登录。原始响应和后续 TF 响应仅在 runner 私有目录及既有收件人的 age 密文中，公开报告只含固定类别/布尔/受限数字。旧快照缺少可选异常文本时明确记录缺失，不伪造错误；回放保留 Cookie 原到期时间。

Store 会话重建通过后，最初 TF 创建返回401；新鲜登录也验证了 Store 成功而 TF401，不能只归因于 Cookie 过期。后续显式统一虚拟 Mac 模型/名称，并让 TF 客户端标识与已认证 Mac Store 上下文一致。源码核对确认：初始认证请求体本来就来自 Mac 机型头，SDK的 iPhone 默认值出现在后续上下文，不能把先前401归因于“请求体发送了 iPhone”。

[实际成功42688988859](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42688988859) 在源码 `a3bea18007b49f806ac26b9d24b3b7c3f3a4cd18` 命中精确公共缓存并通过36+4项 Python、2项 Node、20项 CTest。此前 Store429 要求的16秒等待已过；恢复时 PET 绑定有效且剩208秒，无密码重登或验证码。本次完成真实 Store 登录、TF会话创建和账号目录查询，HTTP200。多个条件共同改变，暂不单独归因于某一项修复。

新的恢复器固定成功运行、源码、ZIP和密文摘要，并额外要求 TF与目录证明；保留原独立虚拟身份。下一控制仅查询 `yoNuHexZ` 邀请，不挂载账号密码，不接受邀请；新增原生测试限定 GET、空请求体、固定 Apple 地址及既有会话签名。邀请接受、实际 beta、内容解密及文件回传仍未证明，原 Secrets、FairPlay授权数和 VPS部署保持不变。


## 2026-11-09：邀请 OPEN 与一次性接受请求

[邀请 GET42689737849](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42689737849) 返回200；[离线检查42690498519](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42690498519) 确认状态OPEN、名称匹配A.I.，当时尚无可匹配目录记录。接受适配器参考 [AutoJoinTF 的直接实现](https://github.com/Yuheng0101/X/blob/main/Tasks/AutoJoinTF.js)，只使用其空请求体 POST 路径，未使用抓包凭据、第三方认证/解密服务或其重复轮询加入逻辑。

[一次性工作流42692803345](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42692803345) 通过公共验证及22项原生检查；先发布绑定运行/源码/nonce/有效期的 age 意图包，再由代理校验实际等待运行及摘要，在仓库中创建持久密文记录，之后同一 attempt1 才能发送一次接受请求。记录只含不可逆绑定和运行元数据，不含原始账号、凭据或TF会话；失败或结果不明时不可删除/覆盖它来自动重发。私有SQLite意图也先于POST提交。

该唯一的接受POST返回200，响应目标为A.I.，但最初的目录匹配未通过，所以回执仍为“加入结果未确认”，没有重复POST。随后只读检查显示：v4目录只给出7个应用概览ID，不含Bundle字段，不能据此直接断言未加入。下一步沿用SDK的appDetails元数据查询，把目录概览与接受回执中的Bundle ID/应用编号绑定；这是读元数据的请求，不是再次接受邀请。实际构建、测试包、完整解密和回传仍待验证。


## 2026-11-09：加入已验证，取包停在安装元数据

[只读验证42694923538](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42694923538) 已通过账号目录 appDetails 将 A.I. 的 Bundle ID 和应用编号与接受回执对应，确认已加入测试。此验证没有再次发送接受邀请请求，永久意图记录继续保留。

[首次取包42696261040](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42696261040) 通过22项原生检查，并重新验证目标绑定。安装接口返回HTTP200，但SDK因安装元数据缺少非空 url/dpInfo 而中止，尚未下载IPA。[离线诊断42697014857](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42697014857) 在零Apple请求下确认了这个固定错误类别。HTTP200不能作为已取包证明。

后续受限诊断将固定安装端点的原始响应仅保存到runner私有目录和既有收件人的age密文中；公开部分只给出允许字段的类型与计数，不输出下载地址、密钥或账户数据。保留原下载字段校验。TF实际IPA、完整内容解密、私有文件回传和生产自动路由仍未完成。


## 2026-11-09：真实 beta 取包成功

安装响应实际有非空下载地址和 SINF，`dpInfo` 明确为 null。兼容分支只对这个明确值接收原始ZIP，并保留目标绑定、归档规范化、SINF与CRC检查；加密传输路径不变，无效密钥不会降级绕过。

[取包42698306052](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42698306052) 通过50+4项Python、2项Node、23项CTest后，下载并验证了真实A.I.测试包：764,970字节、30个成员、1个加密Mach-O。仅保留给既有收件人的密文和受限回执，一天后过期。尚未证明内容解密或文件回传。

[离线模型验证42699070274](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42699070274) 将使用摘要固定的这个包、来源验证的既有CN运行时及已保存模型，不登录Apple或新增电脑授权。兼容性必须由原有完整明文哈希验证证明；在结果出来前不能称为解密成功。


## 2026-11-09：完整解密和主人私聊回传已验证

[离线诊断42699765568](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42699765568) 已确认：现有CN模型与这次TF包的选择器匹配，完整SINF验证通过，不需要新模型或电脑授权。后续失败定位到ZIP目录复制兼容性；规范化8个空目录项时，逐个比较全部30个成员的内容SHA256、大小、CRC和模式，确认没有修改应用内容，也没有放宽任何密码学检查。

[完整解密42701117321](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42701117321) 通过56+4项Python、2项Node、23项原生检查，复用来源验证的既有CN运行时和保存模型，完成1个加密镜像、148页的原始明文哈希验证。随后完成账户数据清理、归档/清单验证和收件人密文封装。全程零Apple请求、零新增电脑授权，原Secrets和模型保持不变。

[私有回传42701908536](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42701908536) 先通过4项来源、去重、文件校验与日志隐私测试，再经固定SSH将已测试的一次性发送器交给VPS。它以原服务用户运行，复用现有官方本地Bot API和主人配置，重新校验密文/明文摘要、IPA结构、CRC及账户信息清理，并在发送前提交持久意图。Telegram已确认主人私聊收到完整403,501字节文件，状态为`telegram_file_delivered`。没有重启或升级主机器人，没有在VPS编译/测试，也没有把Apple模型转移到VPS。

这次固定邀请的真实“加入—取包—完整解密—私有文件回传”已经完成；没有安装/运行验证。永久邀请意图和VPS一次性发送记录必须保留，不能通过删除记录重发。通用TF链接自动路由、持久会话保存与生产集成尚未部署，实验密文仍只有一天保留期。
