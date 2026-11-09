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
