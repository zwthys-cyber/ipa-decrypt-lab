# 项目进展

## TestFlight 自动任务已接入生产（2026-11-09）

主人私聊中的 TF 邀请链接现进入独立 `tf_` 队列，后台恢复持久会话、检查并在必要时接受一次邀请、下载可用 iOS 测试构建，完整明文验证后交给原有私聊交付链路。其他白名单用户仍仅使用 App Store 路线；两条既有地区账号与历史版本行为保留。

[修正版部署 42710092658](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42710092658) 通过 Ubuntu/Debian 13 各492项 Python（各1跳过）、Node/Go、真实 systemd 凭据挂载及运行包门禁，并确认服务健康。此前首版部署漏导入了 `app_from_run`，新增自动交付集成测试发现并修复；不要把首版健康检查当成自动交付已验证。修正版生产控制器源码为 `f6ace388a5a25aa75df3781455fade18c6553851`。

[最终通用 worker 验证 42712411043](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42712411043) 在源码 `c60aff3648cecf0b315a112c102f9e92ca25db84` 通过15项 TF 专项与4项 Node 检查后，实际恢复会话、确认资格、下载并完成1个镜像/148页的明文证明。没有新接受邀请、电脑授权或重复发文件。自动接收器的合成集成检查覆盖正确主人投递、错误邀请/账号拒绝，以及仍加密输出的拦截；本轮没有伪造 Telegram 用户新消息来再发一次旧文件。

[会话持久化 42703942768](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42703942768) 沿用原独立虚拟 Mac 身份，VPS 只保存会话/SDK身份的私有 age 密文，Apple 明文只在 GitHub 任务中解封，原有模型仍在 GitHub。普通任务只加载验证过的成品，不重新编译或密码重登。异常、额外协议、限流、取消及未知接受结果都不会触发自动重复接受。

用户提供的 Telegram 截图已确认一条真实新请求收到 `CapyPlayer_1.1.7.ipa`。对应 [42714371079](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) 的请求 `tf_8e5cbf63015f20a321641f38f42833bc` 完成46个加密镜像、17,724页的严格明文验证；已有成员资格，没有新接受邀请或电脑授权。截图是文件接收证据，worker 的 `delivered=false` 仅表示它本身不负责 Telegram 发送。

TF 文件名现包含英文 `Beta`，例如 `CapyPlayer_Beta_1.1.7.ipa`；只改变未来 Telegram 文件名称，不修改应用包内容，App Store 命名保持原样。[部署42714903713](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714903713) 在源码 `d53f7defdc65fb11e5b3c04ac3e612990ed6430c` 通过两套 Mac 运行包、CN运行包及 [无重复发送导出42716962584](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42716962584) 门禁，服务健康检查通过。本次没有重发此前IPA。

安装运行、全部 TF 应用兼容或到期限制处理尚未验证。详见 [TF 记录](TESTFLIGHT.md)。

## 当前限制：国区专属应用的地区许可响应

2026-11-09 的真实国区任务 [42566676227](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566676227) 对抖音 `1142110895` 完成国区元数据检查、匹配运行包加载、保存模型/检查点验证和 Cookie 登录刷新，但在申请免费许可证时失败；没有下载或解密到应用。用户确认同一国区账号在 App Store 可以正常下载该应用。

[脱敏原生响应对照 42569885848](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42569885848) 在私有输入前查询的运行器出口国家为 **US**。免费许可接口返回 HTTP 200 字典，但没有正常购买成功标记；购买与直接授权下载两条路径的 Apple 提示均被固定词表归类为 `storefront/unavailable`，并出现提示对话框。没有验证码、令牌过期或原生 StoreAMD 失败证据。仅有 HTTP 200 不代表业务授权成功。

这些结果符合境外出口导致地区限制的现象，但没有完成“同一客户端、同一账号、仅改变为中国大陆出口”的对照，**尚不能把原因确定为 IP，也尚未修复抖音下载**。仍需区分 Apple 对运行环境的限制与客户端地区上下文兼容；没有配置可用的大陆代理/出口 Secret。下一步需要管理员提供可信大陆出口，正常 Apple TLS、目标主机限制和账号隔离继续保留。外区线路保持原样。

对照中跳过重复购买、直接请求既有授权的路径同样未返回有效安装包，不能据此上线“忽略许可”的改动。没有放宽响应、应用/版本、签名或明文验证，没有生成或发送该应用文件。中国区路由和两个已验证样本的模型证明仍有效，不能推广成全部中国区应用都可下载。

`cn-download-diagnostic.yml` 默认为无账号 `preflight`；诊断客户端只在 GitHub 编译、测试后使用，不替换普通运行包，不保存到生产 Swift 缓存。公开材料仅为关闭字段集合中的数字、布尔值和语义类别，原生消息、对话框文字、Cookie 和网络地址不公开。旧诊断中的 `native_license_failed/native_version_resolution_failed` 可能被诊断标记词触发；[分类隔离修正](https://github.com/zwthys-cyber/ipa-decrypt-lab/commit/b8790b7fc8035ab83a4fc13886af881bd7d91c22) 已排除这些标记，分析应优先使用真实阶段、结构和地区类别，不能据旧标签断言版本错误。


## 2026-11-09 按链接选择中国区或原外区账号

用户要求按 App Store 链接识别地区。main 已实现 `/cn/` 自动选择独立中国区最新版工作流，其他地区链接和纯数字 App ID 保留原外区账号；中国区历史请求明确停止，不跨账号回退。编号、固定工作流、进度与回执绑定账号，SQLite 重启恢复、取消、取文件及白名单配额保持隔离。普通国区任务不恢复模型、不申请电脑授权、不接收验证码；会话失效转管理员维护。

[链接与隔离回归 42564779892](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564779892) 通过 480 项主 Python（1 跳过）、68 项隔离 Python 与 5 项 Node 检查；[主分支复核 42564839403](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564839403) 也通过。[双 Intel 运行包 42564839454](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564839454) 已成功，包含本轮公共导出流程复用及账号回执绑定。国区独立客户端、真实导出和 VPS 上线分别验证，后续完成记录单列，不把合成检查当作真实 Telegram 收发。

保存模型的独立新运行器复用 [42563127722](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42563127722) 与保存状态重放 [42563352128](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42563352128) 均对另一款国区应用 1530340312 完成 6 切片、164 页验证，状态/GUID 正确，授权数保持 3，无验证码或新增授权。原模型的 LocalSend 31 切片、11,744 页证明继续有效；旧 Intel 配置仍保存在专用备份。

alpha.5 文档和发布流程包含链接分区，安装/运行、中国区历史和收费仍待实现。原德国区账号 Secrets、模型和安全设置未修改。实际导出、部署与公开发布以完成记录为准。见 [中国区操作说明](CHINA-ACCOUNT.md)。


## 正式导出、部署与发布完成

- [国区独立客户端 42565388618](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565388618) 在 macOS 26 Intel 通过 29 项 Swift、Go 密封/原生前置条件及重定位，普通任务成功按精确指纹取包。
- [国区真实普通导出 42565938868](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565938868)：App ID 1530340312，6 个加密切片、164 页完整明文验证，清理后 2,061,272 字节，4 份固定数字进度快照。账号已清理，仅留 age 密文及绑定 `account_profile=cn` 的回执；ZIP、密文摘要、运行/源码/地区回执均已核验。未发送 Telegram 文件，不等于安装运行或一次真实用户国区收发。
- [外区预检 42565489090](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565489090) 在最终源码正确加载新默认运行包及固定公共资源，没有加载 Apple 凭据。
- [服务器 build-only 42565464660](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565464660) 和 [正式部署 42566050391](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566050391) 均通过 Ubuntu/Debian 13 各 480 项 Python（各跳过 1 项）、3 项 Node、Go、大容量加密、systemd 凭据和包检查。部署返回 `persistent_service_ready_verified`，保留原 SQLite、白名单、六项运行凭据和单轮询进程。
- [alpha.5 发布 42566052613](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566052613) 校验 24 份 Markdown、精确源码/指纹、产物摘要、清单与许可证后发布 3 个组件包、8 个附件。[下载 v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。

本轮发布/部署运行源码为 `48ad5b75eb61a6cc5f01ffb539f06a33055adc9a`。后续提交只补齐事实与文档，不改变运行代码或重新部署。原德国区 Secrets、安全设置及旧 CN Intel 备份未改动，没有新增电脑授权、线上测试用户或额外测试文件发送。

## 2026-11-09 中国区独立模型已恢复

用户批准的一次额外 ARM 初始化 [42562058217](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42562058217) 成功，授权数量 2 → 3。中国区 LocalSend 的 31 个加密切片、11,744 页同时通过模型恢复和独立完整明文校验；配套模型/状态/GUID/会话已核验并保存为 CN 专用 Secrets。临时批准和验证码 Secret 已删除，旧 Intel 档案继续保存在 GitHub 专用加密备份中，德国区和 alpha.4 默认服务未变。

该阶段后已完成保存模型跨运行器复用和保存状态重放，链接路由的后续进展见本页开头；中国区历史版本仍不支持；没有额外发 Telegram 文件或验证安装运行。此前同日阻塞与准备章节保留为历史阶段，最新结果见 [中国区说明](CHINA-ACCOUNT.md)。

## 2026-11-09 中国区地区绑定修正与 ARM 对照

[原生地区构造对照 42560593505](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42560593505) 发现 ARM/Intel 默认美区 storefront；显式中国区上下文保持正文、设备标识和签名头不变。CN 流程已补齐该上下文并验证拒绝外国地区/控制字符；这还不能证明它就是旧检查点密钥校验失败的原因。

[ARM 准备 42559393924](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42559393924) 完整构建和测试通过；[实际 ARM 重放 42560812625](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42560812625) 登录、下载和精确记录匹配通过，授权数仍为 2，无验证码、无新授权，但许可证首块仍校验失败。中国区独立模型、完整解密和正式路由尚未完成。

现有检查点、配套 GUID 和会话已经加入 GitHub 专用加密备份及读回核验流程。额外一台 ARM 原生初始化对照已准备为受限入口，尚未获准或执行；需要用户明确同意一次新增授权，保留旧备份，并通过源码/标识/有效期/任务去重/实时数量检查。德国区账号和 alpha.4 默认服务保持原样。详情见 [中国区说明](CHINA-ACCOUNT.md)。

## 2026-11-09 历史阶段：旧 Intel 状态的许可证首块失败

中国区登录、跨运行器刷新、免费原包下载和授权数量查询已通过；独立模型及机器人地区路由仍未完成。

- 初始化 [42554044136](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42554044136) 数量 1 → 2，已保存独立 CN 检查点、配套 GUID 和受保护会话。原生单向导入没有完成回执，不能把调用返回写成模型成功。
- 之后两个中国区样本重放均在 `sinf_class_rejected` 停止，没有再次授权。LocalSend 原包下载和输入绑定通过，原历史样本在中国区不可用，因此没有跨区回退。
- [离线诊断 42556247417](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42556247417) 通过 51 项 Python、2 项 Node、全套 Go 测试/静态检查/竞争检测后，确认授权数据库认证和许可证精确记录匹配通过，随后许可证首块校验失败。具体算法或平台原因尚未确定，没有生成 CN 模型，也没有完整解密或明文证明。
- 最新会话密文已核验保存；授权数仍为 2，没有使用验证码、撤销授权、部署 VPS 或发送 Telegram 文件。已有 CN 检查点时仅重放，不重复初始化。

原德国区账号、模型和 alpha.4 默认服务保持原样。操作和阶段成功的边界见 [中国区状态](CHINA-ACCOUNT.md)；本页后续同日各节按历史阶段保留，不能作为最新阻塞结论。

## 2026-11-09 真实普通用户收发验证

已核对一位管理员已授权的真实普通用户及其现有请求，没有重复提交或发送文件，也没有更改既有每日额度。受检账号不是管理员，已授权且每日额度为 3 次；具体 Telegram 用户 ID、授权表、消息 ID 均保持私有。

- [真实任务 42543990293](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42543990293) 对 App ID `544007664` 成功导出，8 个加密切片、50,780 页全部验证，清理后明文 147,146,888 字节；7 份有效数字进度快照。`plaintext_verified=true`、`runtime_verified=false`，明文未公开。
- [只读权限检查 42544362020](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42544362020) 确认受检账号为普通已授权用户，目标请求在其私有作用域中已记为 delivered。该状态只在文件发送回执和接收私聊校验通过后写入。
- [最终进度检查 42544535030](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42544535030) 确认该任务与管理员作用域分离，进度为 done，完成耗时已冻结且消息标识已私有保存；服务 ready、当前无活动任务。输出仅为固定状态和布尔值，不含实际用户、任务或消息标识。

诊断器先在 GitHub-hosted runner 通过 5 项合成测试，再经固定 SSH 主机校验只读查询已验证的 VPS 运行源码和 SQLite。没有部署、重启服务、修改白名单或调用 Telegram 发送接口。目标数据仅经有时效的临时 Secret 传递，工作流参数只有不含身份信息的随机 nonce；远端私有临时文件和该 Secret 在检查结束后删除，没有上传私有诊断附件。

该证据补齐了一个真实普通用户的提交、进度和发送确认；跨用户越权拒绝及各种故障/恢复边界仍主要由此前真实临时 SQLite 的合成回归覆盖，不能把本次检查说成已在生产尝试所有攻击或进行了安装运行验证。


## 2026-11-09 多用户白名单

alpha.3 已在 [42541919654](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42541919654) 发布，完整提供进度和提速成品。随后本轮加入管理员白名单，alpha.4 已包含本轮功能并完成部署、发布，最终证据见下方记录。

- 固定管理员通过 `/allow 用户ID [每日额度]`、`/deny 用户ID`、`/users` 管理授权；默认只保留管理员有权限，不公开注册，不开通收费。最多 50 名已授权普通用户，私有身份历史有界。
- 普通用户默认每日 3 次，管理员可设为不超过服务总额度的值；全服务默认每日 20 次。所有人共用串行准入，历史查询另有全局每滚动 24 小时 20 次上限。已有缓存不消耗远程查询额度。
- 文件取回、后台查找、重试、取消和发送要求用户私有任务记录，已知任务编号不能跨用户取文件。回调、列表缓存、进度和恢复记录分别隔离，管理员也只通过普通取回入口访问自己的文件。
- 撤权和取消意图、待终止工作流占位写入私有 SQLite；重启不自动交付已撤权或取消的任务。取消结果不明时保留全局占位，不盲目重试。
- 旧管理员的任务 hash 作用域、全局更新游标和六项凭据保持兼容；只有一个常驻轮询进程，备份覆盖整库。

[首轮服务器构建 42542616482](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42542616482) 已在 Ubuntu/Debian 13 各运行 466 项 Python 测试（各跳过 1 项），其中新增 15 项使用真实临时 SQLite 的多用户隔离/撤权/取消/恢复测试；另有 Node、Go、systemd 凭据和包检查。合成身份没有写入线上白名单，没有向额外 Telegram 用户发送测试消息或 IPA。随后已经补充一个真实普通用户的私聊请求和交付证据，见本页最新验证记录；合成测试与实际收发证据分别记录。

使用步骤见[白名单说明](MULTI-USER.md)，版本范围见[alpha.4](releases/v0.1.0-alpha.4.md)。





### 最终验证、部署和公开成品

- [alpha.3 发布 42541919654](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42541919654)：先将进度与提速改动打包公开，保留旧版本。
- [双平台生产 42542616831](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42542616831)：源码 `12ca5e2f3f65e7b2adbd42cb5dabbea6efdae874`，两平台各运行 466 项 Python 测试（各跳过 2 项）、2 项 Node 测试、21 项 Swift 测试和 Go/独立启动检查。
- [最终服务器 build-only 42543061196](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42543061196) 与[实际部署 42543133206](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42543133206)：发布/部署源码 `b92dc1575123e1b7eab2283b62d355539fc71e4d`。Ubuntu 与 Debian 13 各运行 466 项 Python 测试（各跳过 1 项），Node、Go、大容量加密/systemd/包检查通过；安装后实际返回 `persistent_service_ready_verified`。
- [普通任务取包预检 42543135884](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42543135884)：默认 macOS 26 成功获取精确匹配的运行包并准备固定公共资源，未进行 Apple 账号导出或 Telegram 文件发送。
- [alpha.4 发布 42543237386](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42543237386)：检查 22 份 Markdown、生产来源、平台、源码指纹、artifact/package 摘要与清单后公开 3 个组件包和 8 个附件。[下载 alpha.4](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.4)。

本轮未向线上白名单加入任何额外用户，也没有向其他用户发送测试消息或 IPA。当前管理员可在私聊中自行授权真实用户；后续真实第二位用户的提交和交付已单独记录在本页最新验证节。后续文档提交没有改变已验证的运行源码/指纹或重新部署服务。

## 2026-11-08 X 导出加速：移除重复压缩

用户截图中的任务 [42444653313](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42444653313) 已完整交付，卡片总耗时 2 分 54 秒。其 GitHub 原生作业为 03:54:55–03:57:03 UTC，共 128 秒；其中复核阶段约 40.45 秒。复核原先用 Python 逐项解压、重新压缩整个 IPA 来删除账号元数据，重复了上游解密后已经完成的打包工作。

当前源码 `2f8494980894c857e89db13c5c3cb1a4d34c92b7` 使用 Go 标准库的 [zip.Writer.Copy](https://pkg.go.dev/archive/zip#Writer.Copy)，直接复制保留成员的压缩数据，重新生成 ZIP 目录并排除 SC_Info、iTunesMetadata.plist、sinf/supf/supp。输入、成员数、路径、解压容量与输出大小均有边界；临时文件为 0600，完整关闭后以不覆盖既有文件的方式发布。新 scrub 命令只供 GitHub 导出使用，VPS 仍仅允许解开交付密文。

原始解密报告、候选摘要、最终 Mach-O 清单、无加密标志、每个 ZIP 成员 CRC、版本与交付摘要检查全部保留。原始压缩数据复制本身不校验 CRC，必须通过后续完整 verify_output 才能加密或发布；不能把 Copy 成功当作明文校验成功。

| 相同 App ID 333903271 的单次对比 | 原任务 | 优化后 [42445425200](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42445425200) |
| --- | --- | --- |
| 下载原包 | 11.30 秒 | 13.70 秒 |
| 解密并验证页面 | 30.92 秒 | 22.35 秒 |
| 复核（包含账号清理和全量 CRC） | 40.45 秒 | 13.80 秒 |
| GitHub 原生作业总时长 | 128 秒 | 103 秒 |
| 清理后 IPA 大小 | 271,261,630 字节 | 279,312,733 字节 |

复核约减少 66%，作业总时长约减少 20%。保留上游原压缩流后，包比 Python 重新压缩版约大 3%，保留成员的内容不变。本次运行器准备反而约多用 13 秒；下载、解密、排队和网络会浮动，不能把这组单样本结果当作固定速度或承诺。用户的全程 174 秒还包含服务器取回、交付复核和 Telegram 上传；本轮只重复了后端导出，没有额外发 Telegram 文件，因此没有声称新的全程交付耗时。

新导出仍验证 32 个加密切片、86,704 页，8 份有效进度快照；只公开一天有效的 age 密文和数字进度，未公开明文或验证安装运行。[双平台生产](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42445031389) 均通过 451 项 Python 测试（各跳过 2 项）、2 项 Node 测试、21 项 Swift 测试、Go 和独立启动检查。[无账号合成对比](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42445037747) 的 33,650,763 字节 ZIP 清理从 0.985567 秒降到 0.027210 秒，保留内容一致且全量 CRC 通过；该步骤的倍数不代表整条任务的倍数。

这是 GitHub 下载/导出运行包升级，现有 VPS 无需重启。普通任务自动获取匹配的新包；公开 alpha.2 附件仍保持原版本快照。

## main 进度卡升级

本轮为进度显示增加明确标注的流程步骤比例、真实下载字节计数、总耗时和本阶段耗时。总耗时覆盖排队到交付，重启按原始任务时间恢复；只有 Telegram 发送回执可完成整体 100%。没有可靠计数的解密内部阶段和 Telegram 远端上传不伪造字节百分比或预计剩余时间。

后台以一天有效的小型数字快照补充 Checks，上报只包含绑定任务/run/源码的固定阶段、时间和计数，VPS 使用已有 Actions 权限读取。合成探针、双平台构建、实际导出和控制器部署均已通过，具体证据见下方“进度升级验证与部署”。公开 alpha.2 成品仍是进度升级前的快照。


当前公开成品版本：[v0.1.0-alpha.4](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.4)。alpha.4 加入白名单，alpha.3 已打包进度与导出加速；此前各节按各自版本和日期保留历史范围。下载、构建与发布步骤见[成品包说明](RELEASES.md)；完整文档导航见[文档索引](DOCUMENTATION.md)。旧版公开 Release 不再作为下载入口，历史构建与失败记录仍按各自日期保留。



## 2026-11-08 进度升级验证与部署

- [控制器部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443436341) 对应源码 `d59f3eb8ebd6f8ce0c98bfb0909817bc4345ac22`：Ubuntu 和 Debian 13 各运行 449 项 Python 测试（各跳过 1 项），通过 Node 边界测试、Go 检查和真实 systemd 凭据挂载检查；VPS 安装后返回 `persistent_service_ready_verified`。计时刷新与下载计数限流的竞争问题已有专门回归覆盖。
- [最新双平台运行包](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443706492) 对应源码 `3c695191364daeb13951e77cd65327c92a1409f0`：两个 Intel 平台各通过 449 项 Python 测试（各跳过 2 项）、2 项 Node 测试、21 项 Swift 测试、Go 检查及脱离构建目录启动验证。
- [新版数字快照探针](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443707998) 无 Apple/Telegram 凭据，成功读回 6 份快照与 0、512、1024 / 1024 的真实合成计数。
- [X 的实际导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42444399936) 成功，生成 9 份有效数字快照。读取到原始下载计数 51,137,136 和 360,254,064 / 502,257,799 字节（约 10.2% 和 71.7%），随后依次进入审计、解密、复核、加密和就绪阶段；所读快照的 artifact SHA-256 均匹配。最终验证 32 个加密切片、86,704 页，清理后明文 271,261,630 字节；只保留一天的 age 密文和数字快照，没有额外发送 Telegram 文件，也未测试安装运行。

官方 Actions 已统一固定到 Node.js 24 版本：checkout v7.0.1、setup-go v7.0.0、cache v6.1.0、upload-artifact v7.0.2。进度上传显式保留 ZIP 归档和隔离输出文件。新 downloader、两个原生生产任务、进度验证、服务器构建和本轮实际导出的注解数均为 0；历史运行的 Node.js 20 警告不会被改写。

当前线上控制器的 Python 服务源码仍为上述 d59f3eb 提交；后续 3c69519 仅更新 GitHub Actions 依赖、上传参数和对应测试，没有再次重启服务。[最新服务器构建](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443709848) 同样通过 Ubuntu/Debian 13 验证。公开 `v0.1.0-alpha.2` 附件保持原快照，本轮没有重发该 Release。

## 2026-11-08 最新状态：真实下载与解密已恢复

[正式完整导出 42439908718（第 2 次运行）](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2) 在默认 macOS 26 Intel 成功完成：

- 应用 `333903271`（X）：账号登录、免费许可请求、原包下载、解密、完整性验证、账号数据清理和 age 加密导出均完成。
- 32 个加密切片、86,704 页通过校验；清理后明文 IPA 为 271,261,630 字节，`plaintext_verified=true`、`runtime_verified=false`。
- 只保留一天的加密交付文件和脱敏收据；明文未公开。本次没有额外向 Telegram 发送消息或文件，也没有验证重签名、安装及实际运行。
- 该运行不加载临时观察器或 DYLD 适配器，使用已通过 CI 的正式运行包。第一次运行在产物发布前因 `validated_runtime_missing` 停止，未读取 Apple 凭据；第二次才执行完整导出。

修复包括：保留 Apple 广告的原生认证路径，使用 Configurator 2.21；由本机 AppleMediaServices 生成 Store AMD 证明并处理单次 SP 挑战；识别 `AMSURLAction` 的真实重试动作；为固定认证/许可/下载接口添加源站绑定的证明。系统 bag 请求改用固定 Apple Configurator 公共配置，保留原始 NSURLProtocol 上下文与 `X-Apple-Store-Front` 商店区域字段，同时清除账号认证字段。删除区域字段会造成系统 bag 校验失败，不能把它当作账号令牌清理。

[双平台正式运行包 42439002658](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439002658) 已成功：两个平台执行 440 项 Python 测试（各跳过 2 项）、21 项 Swift 测试、Go 检查和脱离构建目录的独立启动验证。新增回归覆盖原始请求上下文、区域元数据保留、Cookie/Authorization 清理、凭据和证明的固定目标地址，以及只有无错误的原生 retry 动作可重试登录。

机器人现有控制器调用 main 分支工作流，后续任务自动获取匹配的运行包，本次无需重新部署 VPS。构建流程默认仍验证两个 Intel 平台；新增手动指定单个平台的完整构建入口，以便其他池排队或失去响应时恢复已验证平台。它不会让未验证平台复用其他平台产物或放宽检查。

下文中“登录尚未恢复”“SP 注册阻塞”属于此前的历史排查状态，已由上述正式运行结果更新。


更新于 2026-11-07。

目前已跑通 GitHub 上的原始 IPA 下载、模型恢复与复用、完整解密校验，以及 Telegram 私聊交付。机器人在 Debian 13 VPS 上常驻运行，现通过管理员白名单接入多用户；收费尚未接入。

## 登录服务故障处理

2026-11-07 的任务 [42322326229](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42322326229) 在登录阶段停止；独立诊断 [42322926702](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42322926702) 复现 HTTP 503。该响应表示服务暂不可用，不能据此判定密码错误。

登录流程对 HTTP 502/503/504 和明确的临时连接故障最多尝试三次，间隔 5 秒、10 秒，每次最多 45 秒。密码、验证码、限流及未分类错误不自动重试。最新版导出与历史版本列表共用该逻辑；日志只保留固定类别、HTTP 状态和尝试次数。Telegram 显示等待重试阶段，耗尽重试后明确说明登录服务暂不可用。此处理不能保证 Apple 服务持续故障时仍可下载。

可用 `store-login-diagnostic.yml` 单独验证登录，不下载 IPA，也不上传账号日志。首轮修复通过 438 项 Python 回归测试，并完成 [VPS 部署](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42323311571) 和 [两种 macOS 运行包构建](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42323310919)。

真实应用复测 [42323329697 / attempt 2](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42323329697/attempts/2) 返回 HTTP 403，程序未重试，也未开始下载。401/403 单独分类为访问被拒绝，不能据此认定密码错误、账号封禁或出口 IP 被封。当前已解决临时故障立即失败及原因不透明的问题；Apple 登录是否恢复仍需后续实测，不能标记为下载已恢复。

## 当前实现

| 部分 | 当前实现 |
| --- | --- |
| Telegram | 最新版、指定旧版、按需加载的历史列表、任务查询、取消和文件取回 |
| 服务器 | Debian 13、非 root systemd 服务、私有 SQLite、异常重启、开机自启 |
| macOS 任务 | 默认 macOS 26 Intel，备用 macOS 15 Intel |
| 运行包 | 两个平台分别构建，普通任务直接获取约 28 MB 的成品包 |
| 应用范围 | 美区免费应用，账号必须具备下载许可 |
| 文件大小 | 最多 2,000,000,000 字节，不分卷 |
| 结果校验 | 加密切片、可用页面哈希、归档结构、摘要和版本绑定 |
| 交付 | GitHub 只保留一天 age 密文；VPS 校验后发到管理员私聊 |

日常入口见 [Telegram 说明](TELEGRAM.md)，部署操作见 [VPS 说明](VPS-DEPLOYMENT.md)，成品下载见 [Releases](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases)。

## 模型恢复与复用

最初使用 App ID **6599842047** 做固定样本。下面三次都完成了 62 个加密切片、12,524 页的明文校验：

| 路径 | 记录 | 电脑授权 |
| --- | --- | --- |
| 首次恢复模型 | [41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942) | 当次新增一次，观测数量从 3 到 4 |
| 在另一台运行器复用模型 | [41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) | 没有新增授权 |
| 从检查点重放 | [41847775765](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41847775765) | 没有新增授权 |

这些数量来自样本，代码不会把它们当成固定通过条件。每个任务都要按实际 IPA 检查全部加密切片。

模型保存在 `FAIRPLAY_MODEL_B64`，SIDB/IOMAC 检查点保存在 `FAIRPLAY_STATE_B64`。两者都是私有 Secrets，不随源码或成品包发布。日常任务直接复用模型，不重新占用电脑授权名额。

需要手动验证时，可运行 `native-store.yml` 的 `offline` 模式；需要从现有检查点重新推导模型时，可运行 `model-bootstrap.yml` 的 `checkpoint-replay` 模式。初始 `trial` 会涉及机器授权，不用于日常重试。

最后一次实测的授权数量是 4/5，这是历史记录，不是实时查询。此前只做过一次全部解除授权，记录为 [41837099155](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41837099155)；后续没有把它当作清理或重试步骤。

## 下载与交付记录

| 内容 | 结果与记录 |
| --- | --- |
| 完整 IPA 加密导出 | [41856194867](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41856194867)：92,118,013 字节，62 切片、12,524 页通过 |
| Telegram 大文件交付 | [41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056)：取得 92,118,013 字节文件的发送回执 |
| macOS 26 实际样本 | [41876940427](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41876940427)：App 1530340312，6 切片、164 页 |
| QQ 流式审计和导出 | [41907705194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907705194)：19 切片、131,440 页，341,766,793 字节 |
| QQ 9.3.55 指定旧版 | [41931938986](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41931938986)：20 切片、126,580 页，324,952,532 字节 |
| 历史列表与按钮 | [41941057460](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941057460)：列出 App 6749145363 的 3 个版本；点击后产生的 [41941946764](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941946764) 已完成导出 |
| QQ 历史列表 | [41941095718](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941095718)：335 个标识，时间预算内查到 33 个版本 |

分别记录“工作流导出成功”和“Telegram 发送成功”，上表只有明确拿到发送回执的项目才算交付完成。安装和实际运行是另一项验证，目前还没完成。

## 预编译加速

重复的 Go 安装、原生编译、Swift 构建树恢复和测试套件，已移至 `native-runtime-build.yml`。它在源码变动时构建两个 Intel 平台的运行包，普通下载和目录查询只取成品。

包内包含四个程序、必要的公开 Swift 资源和许可证。清单记录源码指纹、系统平台、生产提交、运行编号及逐文件 SHA-256。消费端只接受成功的 main 分支构建，下载后再次校验，不使用不匹配的旧包。

| 验证 | 结果 |
| --- | --- |
| [构建 41946086966](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41946086966) | 两个平台均通过 414 项 Python 测试（各跳过 2 项）、10 项所选 Swift 测试和 Go 检查；原构建目录移走后启动正常 |
| [全新机器 41947134774](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41947134774) | 两个平台获取并校验运行包约 3–4 秒 |
| [My BVF 41947479965](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41947479965) | 包准备 8 秒，公共资源准备 24 秒，导出处理约 42 秒；总计约 1 分 49 秒 |
| [历史查询 41947789366](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41947789366) | 包准备 4 秒；总计约 1 分 43 秒，得到全部 3 个返回版本 |

My BVF 之前的 [41935307617](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41935307617) 用了约 4 分 2 秒，两次样本相差约 55%。这不是固定速度承诺，也没有把 Telegram 上传时间计入这次对比。

Actions 运行包保留 30 天，每周重建一次。改动 tools/、tests/ 或构建工作流后，要先等新包构建成功。缺包或过期时任务会在读取 Apple 凭据前停止；手动运行构建流程即可补包。公开 Release 是版本快照，普通任务目前仍从 Actions 获取匹配包。

## 公共资源与历史列表加速

四个固定 Apple 公共资源使用精确路径和固定键缓存，每次恢复后仍检查长度和 SHA-256。缓存保存发生在读取账号凭据之前，不包含账号会话、授权模型、IPA 或整个用户目录。

[冷缓存准备 41951203095](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41951203095) 和 [另一平台恢复 41951409995](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41951409995) 均成功。后一次恢复约 5 秒、校验约 1 秒；此前重新准备资源的样本为 24–71 秒。

历史列表改为每批最多核对 10 个标识，以排他游标加载更早版本，单个应用最多展示 200 项。缓存扩大为 50 个应用，24 小时内直接使用，未满 7 天的旧缓存先显示并在空闲时刷新。已加载页面的翻页不启动 GitHub；按钮有效期仍为 6 小时。远程查询仍受每滚动 24 小时 20 次限制，包含首屏、刷新和加载更早版本。

[构建 41952137194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41952137194) 的两个 macOS 平台各通过 424 项 Python 测试（各跳过 2 项）、11 项所选 Swift 测试及 Go 检查。[服务器构建 41952137779](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41952137779) 在 Ubuntu 和 Debian 13 各通过 424 项 Python 测试（各跳过 1 项）。

实测 QQ 历史目录仍返回 335 个标识：

| 查询 | 结果 | 工作流作业耗时 |
| --- | --- | --- |
| [首批 41952989754](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41952989754) | 10 项，从 9.3.80 到 9.3.35；元数据步骤约 102 秒 | 2 分 22 秒 |
| [下一批 41953354529](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41953354529) | 另 10 项，从 9.3.30 到 9.2.85；元数据步骤约 41 秒 | 1 分 2 秒 |

两批标识不重叠，第二批从首批返回的排他游标继续。旧目录样本 [41941095718](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941095718) 用时 8 分 32 秒、返回 33 项；新首屏返回项数更少，因此这是“更早看到可选列表”的对比，不是同等完整目录吞吐量的对比。以上不包含 Telegram 展示延迟，Apple 响应波动仍明显。

[My BVF 导出 41953586939](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41953586939) 作业总计约 59 秒：运行包 7 秒、资源恢复及校验 8 秒、完整导出步骤 27 秒；22 个加密切片、704 页校验通过，明文大小 10,251,249 字节。此前预编译版同应用样本约 1 分 49 秒。本次只核实 GitHub 加密导出，没有把 Telegram 发送或安装计入验证。

## 历史查询连接复用

历史目录的一批查询和指定显示版本号的搜索，现在各自复用一个禁止重定向的 HTTP 连接池，并只获取一次经过白名单校验的公开下载端点。连接池只存活于本次搜索，结束时关闭；版本请求仍然串行执行，每次重新生成签名，并使用当前账号令牌和 Cookie。元数据解析、版本绑定、时间预算和连续失败上限保持不变。

日志只记录公共配置请求、连接池和签名请求的数量，不记录端点响应、账号数据或签名内容。[QQ 首批实测 41956106639](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41956106639) 确认有 2 次公开配置请求、1 个查询连接池和 11 次签名请求。标识发现仍单独请求 Apple；10 个版本逐一请求，签名没有被复用。

同一首批 10 个版本的标识、显示版本和下一页游标均与上轮一致。本次工作流作业约 55 秒，元数据步骤约 36 秒；上轮分别为 2 分 22 秒和 102 秒。[下一批 41956309828](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41956309828) 同样返回原来的另外 10 项，游标保持一致；工作流作业约 1 分 3 秒，元数据约 50 秒，上轮则为 1 分 2 秒和 41 秒。因此重复准备开销确实减少，但两组样本并不能支持“所有查询都按固定比例提速”。

[构建 41954739130](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41954739130) 的两个 macOS 平台均通过 424 项 Python 测试（各跳过 2 项）、11 项所选 Swift 测试及 Go 检查，并完成成品包搬移后的启动验证。这轮只更新 GitHub 原生运行包，无需重启 VPS；后续任务自动获取匹配的已验证运行包。

[指定旧版导出 41956478397](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41956478397) 使用 App 1448246447、Apple 版本标识 830508655，约 49 秒完成 GitHub 作业；5 个加密切片、820 页通过校验，明文 8,436,045 字节。验证范围是指定版本绑定和完整加密导出，本轮没有重新发送 Telegram 文件或验证安装运行。

## 服务器与容量

在 [42145258538](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42145258538) 部署了简洁首页和选中版本后收起列表，运行代码提交为 `957783d42f0d605bb455384827c01e7a73037027`。Ubuntu 和 Debian 13 各通过 430 项 Python 测试（各跳过 1 项），以及 Go、systemd 和部署健康检查。服务器只安装经过 GitHub 验证的成品，没有在服务器编译或执行测试。

IPA 审计采用分块临时文件和只读映射，避免把大程序整体读进内存。2,000,000,000 字节的加密、解密和摘要比对，以及超出 1 字节的拒绝行为，已在 [41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129) 用合成数据验证；尚未把 2000 MB 的真实游戏交付计为已验证。

服务器保留 current 和 previous 两版程序。正常传输结束会删除临时文件，异常残留在下次启动时清理；数据库和恢复备份保留。发送结果不明的任务不会在重启后自动重发。

## Telegram 界面

首页仅显示“下载旧版本”和“使用帮助”，不显示今日次数；二级页在原消息中切换并可返回。命令菜单保留首页、进度和取消，原有其他指令仍可手动使用。

版本选择通过任务检查后，整组版本与导航按钮收起为“已选择版本”提示。收起状态持久保存，后台刷新只更新缓存，不重新展开。再次发送 `/versions AppID` 可打开新列表。菜单导航不能提交任务，仍只接受管理员私聊。

## 接下来要做的事

- 补齐重签名、安装和实际运行测试，目前 `runtime_verified=false`。
- 扩大应用和账号样本，验证更多历史版本及接近容量上限的真实文件。
- 完成多用户、计费和正式运营所需的管理功能。
- 完善异地备份；现有数据库备份仍在同一台服务器。
- 继续锁定和审查传递依赖。现有包有构建来源与摘要，但不等于已经实现可复现构建。

早期原生接口失败、认证排查和模型恢复过程，保留在 [OFFLINE-BACKEND.md](../OFFLINE-BACKEND.md)、[原始下载记录](../NATIVE-DOWNLOAD-RESULTS.md) 和 [研究记录](RESEARCH.md)。旧版本文档可从 Git 历史查看。

## 2026-11-07 登录故障复核

- [账号核对与 macOS 15 登录](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42324867557)：在任务内部比较用户提供的账号与 `APPLE_ID`，结果一致；仅输出布尔值，比较用临时 Secret 已删除。用户确认该账号在手机端可以登录并下载。
- [默认地址诊断](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42325115683)：配置查询成功，日志中出现旧认证地址；登录返回 HTTP 204，没有可用的账号响应。
- [内置新版地址对照](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42326093664)：显式选择 `auth_route=native` 后仍返回 HTTP 403。不能据此认定密码错误、账号封禁或某个出口 IP 被封；也不能宣称切换地址已解决问题。生产任务保持默认地址，未启用此实验选项。
- 错误处理已部署：[42324205594](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42324205594)，439 项 Python 测试通过，Ubuntu/Debian 各跳过 1 项，服务健康检查通过。
- 最新运行包：[42325368672](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42325368672)，两个 macOS 平台构建成功，14 项 Swift 测试通过，包含地址选择和不可信地址拒绝测试。

**当前状态：重试与错误可见性已修复，真实账号登录尚未恢复，下载交付未完成。** 需要进一步区分认证服务响应、运行器访问条件和程序请求兼容性；不要无差别重复提交登录或把持续失败写成成功。


## 2026-11-08 原生认证路由与 Store AMD 注册复核

**真实登录仍未恢复；没有下载、解密或交付成功的新增证据。**

- 旧版复现：[42428836142](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42428836142)，旧认证地址返回 204，随后返回 404 HTML，没有账号错误码。
- 上游新线索：[ipatool #642](https://github.com/majd/ipatool/issues/642)。其个人机器上的登录成功不能证明未注册的 GitHub Intel 运行器可用。
- 已修正 Configurator/2.21 标识、保留 bag 返回的原生路径和查询参数、限制凭据及证明的目标地址、校验 AMD 字段、处理当前 macOS 的 AMSPromise 异步结果。保留 SAP 对实际请求体的签名，不启用账号安全升级。
- 原生 SP 挑战至多交给系统框架处理一次。失败明确停止，不清除加密标记、不重复启用或修改账号设置。
- [运行包构建 42430873538](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42430873538)：macOS 26 Intel 和 macOS 15 Intel 均通过构建、Python/Go 检查、17 项所选 Swift 测试及独立运行包启动验证。
- 无账号检查证明公开的 Store 证明接口返回异步对象，等待后得到的字典没有 AMD 字段；直接传入空 action data 没有完成注册。
- [最新真实诊断 42431580087](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42431580087)：已发起原生 POST，程序进入只由 `X-Apple-AMD-Action: SP` 触发的分支，系统注册处理返回失败（固定标记 `store_device_provisioning_failed`），没有可用证明或账号会话。该响应在原有 parseResponse 日志之前处理，因此 HTTP trace 缺少 POST 状态，不能解读成没有收到响应或确定网络中断。

后续需核实原生 Store SP 注册的 bag 配置、异步错误及响应对象约定，在相同 GitHub 运行器上取得有效的 AMD 证明，再分别验证登录、原应用下载、解密和私人交付。现有证据不能确定密码错误、账号受限或出口 IP 被封。源码与运行包已更新，机器人自动使用匹配运行包；没有重新部署 VPS 控制器，没有额外发送 Telegram 消息或 IPA。


## 2026-11-09 历史阶段：中国区账号初始接入

以下为初始阶段记录，后续模型、路由和部署已完成，最新事实见本页开头。

**中国区登录、跨运行器 Cookie 刷新和免费原包下载已验证；中国区模型、解密及正式机器人路由尚未完成。**

- 实时中继 [42547699795](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42547699795) 与登录 [42547602116](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42547602116) 成功：同一原生会话提交验证码，真实 storefront 为中国区。独立会话 Secret 已保存，临时验证码 Secret 已删除。
- 新运行器 [42548840372](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42548840372) 携带 Cookie 正常刷新认证，未再次输入验证码，下载到 App ID `1530340312` 的 2,500,837 字节中国区原包并验证包身份。原包已清理，未解密、未发 Telegram 文件；刷新后的会话已独立保存。
- 独立客户端生产任务 [42548393225](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42548393225) 通过 26 项 Swift、Go 封装工具及运行包重定位检查。合成隔离检查增加到 29 项 Python 与 2 项 Node；这些检查不替代实际下载和解密证据。
- 原令牌跨运行器下载曾在设备证明环节失败，新增 Cookie 刷新路径解决了这个样本的下载。不能承诺永久免验证码。
- 授权数量摘要接口经默认入口、认证节点和刷新会话检查仍返回 HTTP 500。原生证明客户端 [42549339540](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42549339540) 通过 29 项 Swift、Go 工具和重定位检查；实际原生查询 [42549763524](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42549763524) 在 Cookie 刷新后仍收到 HTTP 500。当前停在模型初始化所需的授权数量前置检查；没有初始化中国区模型、占用或撤销电脑授权，也没有加载德国区模型。

德国区账号、alpha.4 服务、默认线路、现有模型和安全设置保持原样。操作及证据边界见 [CHINA-ACCOUNT.md](CHINA-ACCOUNT.md)。


## 2026-11-09 历史阶段：中国区授权数量兼容问题定位

- [客户端标识对照 42550766669](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42550766669)：同一保存会话的账号摘要查询改用 Configurator/2.17 后返回 200，实际授权电脑数为 0；2.21 登录和下载路径保持原样。修复后的固定查询 [42551097522](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42551097522) 通过，取代上一阶段“接口 500 阻塞”的当前结论。
- 模型基础工具 [42551095068](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42551095068) 通过独立构建、原生构造预检、29 项 Swift、Go 密封及重定位检查。中国区模型与状态 Secret 使用独立目的地，未挂载或替换德国区材料。
- 中国区模型任务已增加可用数量、原包结构和设备绑定检查，以及初始化后的受保护检查点和显式重放路径。带实时验证码等待的模型客户端仍需完成匹配运行包验证后再运行真实任务；当前没有新的模型初始化或撤销证据。

中国区模型、解密和正式机器人路由尚未完成。最新操作边界见 [CHINA-ACCOUNT.md](CHINA-ACCOUNT.md)。


## 2026-11-09 中国区首次原生授权与保存回归

[42552374488](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42552374488) 完成实时二次认证和原生绑定，真实授权返回 200，数量 0 → 1；原生导入后观察到 fpsd SIDB。检查点因新增流程的临时目录前缀不匹配而被拒绝保存，运行器已结束，模型及检查点均未保存。没有执行撤销，不将该任务写成模型成功。

目录调用已修复，无账号验证 [42552915716](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42552915716) 通过 45 项 Python、2 项 Node 和实际 sudo 检查点保存/读取契约。真实任务在提交授权前必须重复该契约并核对原生硬件标识；当前已有 1 台授权占用，不盲目重复失败初始化。
