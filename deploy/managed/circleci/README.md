# CircleCI on-demand runtime

## 当前生产证据（2026-11-27）

截至2026-11-27，生产已切换到原机器人 + Cloudflare Workers/D1 + 按需CircleCI macOS ARM64 + 私有Drive交付。[成功切换45918215266](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918215266)对应处理源码`185a52110922e0f67ac2c7dff4e1fa85b3b4c98e`。CircleCI75真实国区任务已完成下载、17镜像/120,976页严格验证、342,632,968字节私有上传及主人通知；新平台历史版本交付和新TF任务仍待分别真实验收。

当前操作步骤见[运行手册](../../../docs/OPERATIONS.md)，指令见[Telegram](../../../docs/TELEGRAM.md)。账号会话维护在main的既有工作流进行，新机器人处理源码来自upgrade/managed-runtime-v0.2，不能混用。维护分支上的文档整理不更新生产HEAD。

公共运行包以runtime-pins.json为准，目前为job62；不是下面历史job40/42的归档。/status已通过一次快照查询消除逐任务外部核对，用户截图约1秒。HOME/CFFIXED_USER_HOME绑定和真实Foundation回归已由CircleCI75实际任务验证。新入口仅主人私聊，完成通知是私有Drive链接；旧多用户、附件和五秒进度卡不在当前范围。

下方均为按时间保留的实现/切换检查点，不以旧“尚未生产”“等待恢复旧机”覆盖本节。不要因文档整理重新接受历史邀请、重复GoClub/红果漫剧下载或重发已确认通知。

## 生产切换及真实消息验收（2026-11-27）

[离线生产切换45913375750](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45913375750)已成功，初次运行源码aaa2278038b7f2d22bed459b647cccb0cba3e93f，脱敏收据artifact15161451437。完整读回29条历史任务、89条updates、14条metadata，2条pending保持held；原Go Club已完成任务、私有文件和确认通知保留。原TF历史邀请按pinned接受/确认记录构造防重tombstone并seal，未重新接受。新Token属于原机器人，旧Token已失效，5个旧派发/目录工作流保持disabled；新webhook和真实cron触发均取得回读，production_cutover:true。

用户随后提供IPAZaKe聊天截图：08:02:33发送/status，08:02:40收到Go Club“已核验，可用/get领取”和原失败任务“任务已结束”。真实入站及回复已确认，但约7秒延迟需优化。当前改为一次读取最新5条已提交状态，避免/status逐项调用完整核对与排队逻辑；外部终态由cron继续核对。新增真实workerd/D1查询预算回归，5条结果应在最多8次D1调用内完成，并隔离他人记录。每次源码升级也必须等该源码自己的cron观测回执，不能借上个版本的旧时间戳放行。

**运行分支upgrade/managed-runtime-v0.2必须与Cloudflare.RUNTIME_SOURCE_SHA一致，不能在入口开启时直接推送。**CircleCI checkout和GitHub凭据签发都引用该分支HEAD。维护从独立upgrade/managed-runtime-maintenance-v0.2准备并验证，先用已验证的原运行包关闭空闲入口且保留旧source/DB/Secrets，再将同一已验证commit推进运行分支，执行Offline managed runtime cutover并等待新source的真实cron。上线后的新收据是最终运行源码依据，不再直接为补文档改动运行HEAD。

旧机之后未保全的变化仍未知；不伪造物理停机或无缺口证明。旧offset/browser原样保留，切换前的消息持久隔离，不重放旧任务。计费入口保持关闭，无本地构建/项目测试或旧机SSH依赖。

## 历史决定：旧机不可用，转离线恢复（2026-11-26 23:38 UTC）

已从长期Secrets中的原加密源生成并验证离线恢复计划：[45912001065](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45912001065)。29条任务、89条更新、14条metadata（含offset/browser）和原TF状态得到保留，旧pending继续held；源接受账本不存在，不初始化。用户保留原机器人并更换Token，独立MANAGED_TELEGRAM_BOT_TOKEN已通过同bot身份与旧Token失效检查。5个旧导出/版本查询工作流已停用，无活动任务；新CircleCI工作流保持独立。

不再等待旧SSH恢复，但当前仍未安装新webhook或启用生产。下一步须落地离线D1交接与历史TF确认、隔离旧消息并启用后台调度；不能把过去有时限暂停快照当成现在的永久停机证明。恢复后的未知变化不重放，Go Club已完成交付不重复。下面关于源访问阻塞的章节仅为其所标时点的历史证据。

## 最新候选：版本目录与分页接线通过 GitHub 验证（2026-11-26）

/versions 的目录排队、默认/CN元数据专用凭据、缓存与分页、刷新、本人私聊消息绑定、整份列表单次选择和精确版本下载接线已实现。[控制端45910022331](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45910022331)通过81项集成与16项既有入口测试；Python接线9项、目录10项、凭据11项亦通过。目录任务不能领取模型、访问上传或调用导出接口。大版本ID保持文本/BigInt校验，避免JavaScript数字精度损失；旧任务表与真实交付记录不重建、不清理。

这是未部署到正式入口的候选代码与合成验证。Worker scheduled队列核对处理器已写好，最终切换时仍需安装并验证定时触发器。原运行环境当前被服务商暂停且不能再次临时恢复；最新加密快照已另存13段GitHub Secrets并独立读回，不能用曾恢复过旧服务的快照冒充最终交接。仍需最终状态/offset/历史浏览器及接受账本交接、旧poller永久停用、单入口激活和真实任务验收；正式入口仍关闭，未重复Go Club任务。最新证据见[项目状态](../../../docs/PROJECT-STATUS.md)。下方各节是其所标时点的历史证据。

## Go Club 真实 CircleCI 任务与私有交付通过（2026-11-26 17:20 UTC）

用户本次提供的美区 Go Club 链接对应 App ID `6739782103`。成功源码 `f3451dd2ba31ac9d9524da4ed7b6ad8f22c1346a`；[GitHub 验收 45866115288](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45866115288)、[默认账号签发 45866462237](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45866462237)、[CircleCI job72](https://app.circleci.com/workflow/aa787787-32bb-4c8f-a9de-5776666cc997/job/ef34d39f-955e-45a9-aee8-a6b60bb4a0ba) 均成功。逻辑任务 `pilot_267d28bb7688af8bbc132595f7009a07`，run `bc58f448-c0fc-438e-936e-46ecd97797dd`。

真实 macOS ARM 工作机完成默认账号登录、下载、解密、完整明文/归档验证、账号资料清理和私有 Drive 上传：**6 个加密镜像、8000 页、73,172,295 字节**。Cloudflare 独立核对 Drive 摘要、大小、名称与仅本人可见权限；机器人私聊链接取得 Telegram 回执，`telegram_notification_confirmed:true`。一次性凭据密文已清除；该凭据包 SHA-256 为 `1f765215b37e3ede8ddab9d2bb3a634c00400d1607771fd94a5e12a6a70cfd79`，不是应用文件摘要。公开产物仅有脱敏证明和加密的源状态快照，没有应用明文、模型、账号缓存或私有下载链接。真实用户文件保留在本人 Drive，未执行示例文件清理。此结果证明完整明文与私有交付，不是安装/运行或其他应用兼容性证明。

验收前实际暂停空闲旧服务并保存一致快照，29 条历史任务完整导入只读验收记录，其中 2 条 pending 保持 held，未重放。快照密文 SHA-256 `28654b814e6f38c7dddd0fdb79d5d2202aa8915c23db840c9792e6c2ed4b16dd`，加密备份及脱敏收据位于该 GitHub 验收的 artifact `15139574335`。执行窗口仅授权本次默认账号/最新版本/精确请求与目标，最长15分钟，工作机有独立截止看门狗；旧机另有20分钟兜底恢复。结束后验收授权已撤销、Cloudflare 恢复 staging 并关闭新导出/Telegram 入口，旧服务已恢复。**没有执行永久 webhook 切换。**

[恢复后只读检查 45867033676](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45867033676) 成功：健康记录新鲜、服务空闲、TF未完任务0、原会话密文匹配、原私有回传1条且未知0；源接受账本仍不存在，未初始化或重新接受历史邀请。

已接通的代码包含 owner-private 链接入口、默认/CN/TF 分流、手动精确版本、幂等提交、工作机凭据领取、完整证明、持久上传、取消与终态确认、跨源码版本的本人历史领取，以及一次性完成通知。三类执行接线与拒绝边界通过 GitHub 合成集成测试；本次真实业务验收仅证明默认账号 Go Club。新阶段仅更新 Python/控制端，复用已验证 job62 的原生包，无项目本地编译/测试，也无每任务原生编译。

首轮 [45864907910](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45864907910) / CircleCI job71 在公共资源预热时退出，尚未进入登录/下载。原生助手要求现有 `LAB_KBSYNC_CHILD=1` 子进程接口，单独预热调用曾遗漏；修复仅向该助手的最小环境设置此标记，未伪装 GitHub 环境或修改原生二进制。测试桩现复现真实门禁，并检查标记不泄漏给其他子进程。原失败记录保留，旧服务在两次验收后均恢复。

剩余迁移：永久冻结状态和历史接受账本交接、完整版本目录/按钮迁移、单一机器人日常入口切换。原运行环境 仍是日常生产入口；这次有时限验收不代表永久迁移完成。**不得自动重复 Go Club 下载或重发此已确认通知；后续继续工作应推进剩余交接。**


## 当前迁移状态（2026-11-26）

自动任务与凭据签发已完成真实云端验证：[控制端/工作机证明 45851572093](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45851572093)，[一次性签发 45851926514](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45851926514)。源码 `07701765cd5b7a011e9d27ae98dfbfb2eec24da8`，CircleCI run `edb6e561-752e-4e0d-b487-c425b37bca3d`。真实 macOS ARM 工作机下载固定公共运行包、领取并解开仅属于本任务的虚构凭据，服务端回读确认密文清除；SHA-256 `5e870ff3be84a7fe3a17bef9a6135be82bcd3d293ee8ba0517556d5670763e01`。没有 Apple 操作、上传或 Telegram 发送。已修复 GitHub App 项目名称误当仓库身份、签发者元数据读取，以及部署传播期间的源码版本绑定问题。同一逻辑任务的内部请求可恢复，外部派发意图只提交一次。

源状态已经加密保全并存入分块 GitHub Secrets：[在线备份 45842375113](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45842375113)，[Secrets 回读 45843176901](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45843176901)。归档 SHA-256 `3ec6f97fc70ca3e1aa187046a5d3f6bd76a23fd34b077af43de3b867eb23bc29`；验证了原虚拟 TF 会话、10 个文件、7 条 closed / 20 条 delivered / 2 条 pending。源历史接受账本不存在，保留这一事实。在线快照 `frozen:false`，不能当作最终冻结交接；两个 pending 不自动重放。

当前公共运行包已升级到成功的 CircleCI job62（源码 `2896fff82275ef791e3703cc17ed9473c77b151a`，workflow `1c28d9d9-f709-4cb4-b9ae-f5f4413208a5`），runtime-pins.json 是当前摘要来源，下面 job60/61 是历史证据。[工作机适配验证 45852931305](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45852931305) 已通过新增的私有交付回调和上传恢复测试，以及默认/CN/TF 原有回归。

私有上传真实闭环已通过：[GitHub 45855018329](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45855018329)、[签发 45855245169](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45855245169)、[CircleCI job68](https://app.circleci.com/workflow/9faf88d4-a820-412d-8d99-b9b022f76c02/job/51afdfd2-3a3a-43c0-9133-faff76471add) 均成功，部署源码 `b1b43141f1ef45c76a2aac1011f6302969ea7d24`。任务 `pilot_06a7bb734c08c9f9e673bf1678d9270c`，run `7c80f489-4749-4926-a6b9-bddd98ab0f48`。真实 macOS 下载 job62 的项目自有 5496 字节 ARM IPA（SHA-256 `85025bd1cfea42339ed38b09e9580e1094b2949153c83c81e66d9b1ad9043e93`），完整 CRC/SHA 校验后上传 Drive。Cloudflare 独立回读摘要、大小、名称和仅本人可见 ACL，确认注册后仅删除该示例文件，回读 404 确认清理。两端回读 `file_upload:true`、`fixture_cleaned:true`、`ciphertext_cleared:true`；凭据密文 SHA-256 `e1e007538b503357af7336e3c13c87a7c7f8d301ad7ed801cf556ba2ceebe83d`。测试文件没有发送到 Telegram；这不是实际 DRM 导出或大文件交付证明。

上传升级包括创建前持久化意图、同一会话断线续传、不可变内容绑定、服务端独立注册和测试清理日志。未知创建不重建；早先验证任务 job65/66/67 的失败记录保留，没有重置或重复它们的逻辑派发。真实 Google Location 带有 `fields` 和 `session_crd`，日志校验现已准确兼容：固定 Google HTTPS 路径、固定字段投影、有限长度的不透明会话参数，仍拒绝重定向/额外查询键。会话凭据只留在私有日志，公开证明不含 URL、参数值、Google token 或邮箱。新增长中文名称预算，保留版本与 Beta 文件标记。该次 GitHub 通过63项控制/OIDC/上传检查、16项旧入口回归、6项部署和6项上传适配检查；[工作机回归 45855018206](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45855018206) 包含17项默认/CN、6项TF、10项age与旧导出/归档校验。

[新源只读核查 45854611541](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45854611541) 成功：健康记录新鲜、观察到服务空闲、TF未完任务0、私有回传1条且未知0、原会话与固定密文匹配、源接受账本依然不存在。这次观察没有停止服务或冻结状态，不能替代切换前的最终快照。

尚未完成：真实任务入口与版本目录/取消闭环、历史状态与接受账本最终导入、冻结交接、费用限制核查、单一机器人入口切换，以及新链接的实际私有交付验收。控制端仍是 staging，真实 Apple 导出未开放；原运行环境 保持唯一机器人。所有编译和测试均在 GitHub/CircleCI 执行。

以下保留先前阶段的历史记录，后文“最新”仅指当时阶段。


## 新运行包独立 ARM 加载与 macOS 适配验证通过（2026-11-26，最新）

[CircleCI job61](https://app.circleci.com/workflow/b1d0deb7-f168-41a5-87f8-d5088f6d9023/job/02c0b8e6-ba26-4b9e-b38f-5c8b155a319d) 与 [GitHub 45839573020](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45839573020) 均成功，消费者源码 `92d8d4fbf9f7f4ec3aac48e0494fcc2f619f8fa3`。独立 ARM 主机实际下载 job60 的 base/CN/TF 三包并回读三份成功的 fetch receipt，核对固定摘要、源码输入、来源和 ABI；执行新的 TF 原生上下文自检，以及实际 macOS 上的13项默认/CN、6项TF虚构任务适配测试（真实 ZIP/age/进程取消）。消费者跳过 iOS 样例编译，断言没有 Swift/TF 构建树，不重新编译项目运行工具。新参数 `runtime_consumer: true` 显式选择该路径，普通推送保持不启动 macOS。

job60 的21项基础 Swift、29项CN Swift、24项TF CTest、Go/Python/Node 与重定位检查均已从公开日志核对。三个新归档与 pins 相符：base `36fe7378fd311a0d0603a31874119113a76c69576150d6804819722189aaf76b`；CN `7233e062ab3a20a3de15c601ed2d0557b46f586224800418ee2183ddce2d77b0`；TF `f4942727f1265c7399bd6cede28bf1404f1f3ea4b0be589526e618f97b8ad7f8`。之前的 job40/42 为历史成功证据，后续消费者使用新 pins。

独立的 [VPS 只读核查 45839765273](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45839765273) 未取得源状态，返回 source_audit_transport_failed；这不证明源服务停机或状态丢失。补充固定类别/退出码诊断后再次核查，不能以旧的 idle 观察替代新交接检查。未触碰原状态、没有安装候选账本、没有切换 Telegram 或开放真实 CircleCI 私密任务。当前执行适配/公共运行包已验证，真实凭据与源状态交接、任务入口和私有交付仍未完成。


## 默认/CN/TF 执行适配与新公共运行包（2026-11-26）

[GitHub 45838198217](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45838198217) 通过 13 项默认/CN 适配测试、6 项 TF 测试、10 项实际 age 交接、8 项旧导出与22项归档校验。适配复用现有完整明文报告、逐图像/页数、版本、库存、CRC 与账号资料清理，改用标准 age 加密；登录、下载、解密与加密子进程收到各自最小环境。取消/超时终止整个进程组，最终发布前失败不保留输出。测试使用虚构原生返回与账号资料，实际 ZIP/age/子进程操作，不是实际 Apple 导出成功证明。

CN 独立校验保存会话、国区、GUID、checkpoint 与模型，使用 resume-cn，不伪装 GitHub 标志、不增加密码/OTP或注册流程。TF 单独支持 CircleCI run/worker/source/期限原生门禁，原 GitHub main/首次尝试门禁保留。TF 恢复已验证的原虚拟身份，CircleCI 的拟用凭据类型仅包含任务加密的保存会话和 CN 模型，不包含交付长期私钥；实际会话尚未从 VPS 交接。已有成员路径不申请接受许可；新邀请在未接入持久许可代理时明确停止。

[CircleCI job60](https://app.circleci.com/workflow/cc64895c-dcb1-4e8c-861a-43731544d2f5/job/6ed40d3c-d26c-40b6-9ad6-9c73e2de911a) 已从源码 `f6c9f1c5c96553a7af4e78141a9b8ea68afd682d` 构建三包并通过验证，包含新的 TF 原生上下文自检。三包公共归档已独立下载计算 SHA-256，并更新 runtime-pins.json；共同源码指纹 `fa9a90e514db5e3e83e72669dbcadf4d8e81ee958625410d2cd74dabc549f968`。新的独立 ARM 消费者验证仍需单独记录，不能以这次 producer 成功代替。

[GitHub 45839095118](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45839095118) 通过新增 7 项真实 workerd/D1 历史接受账本测试，连同已有控制/调度/OIDC/lease 共35项与旧入口16项检查。候选账本保持历史 confirmed/intent/unknown，保存许可前先提交意图，过期/重启不重新授权，历史冲突不覆盖；邀请键使用 owner 范围的 HMAC。账本仅为候选模块，没有部署新接口或封存真实历史状态，不能报告交接完成。

生产仍由原 VPS 独占 Telegram 入口。剩余为真实凭据/TF 状态和历史账本交接、控制端实际任务路由、持久私有上传/取消/未知结果回查、费用设置确认与最终入口切换。当前服务器没有编译或执行项目测试。


## 真实临时加密交接已验证（2026-11-26，最新）

[GitHub 45834580675](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45834580675) 与 [CircleCI job 59](https://app.circleci.com/workflow/d6244a39-80f3-4f7c-a860-6613f9e3a520/job/a1f2c487-96b5-4ae2-8da7-6b9890f8584b) 均成功，源码 `021d212332810cae3962298ac18a43f208951388`。逻辑任务 `pilot_d32d8ee76ec8e4f32ced07ac249aaf39`，run `d6a6a2d1-91a6-48d4-ac6f-9cb749eb9013`。CircleCI 真实 OIDC 领取任务后生成临时 age 密钥，GitHub 将虚构凭据加密给该任务；控制端只存放密文，绑定 job/run/worker/source/recipient/nonce/期限，拒绝替换请求或密文。CircleCI 解密并检查完整上下文后回报完成。两端独立回读密文 SHA-256 均为 `94b94afd17fc80fc04cce453bcf92026263a77021422449d4be806b8594ddcbd`，D1 完成记录与密文清除标记均确认。bundle SHA-256 为 `47200f063a246ef10841808c41a1243612df9682ac5fe3aacbc22baa35ea6c56`。

CI 通过 6 项真实 workerd 路由/D1/OIDC 集成、6 项不透明密文状态测试、8 项调度恢复、8 项 OIDC 和 6 项部署检查，保留旧入口回归；独立 [age 契约 45834580742](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45834580742) 再次通过 10 项实际加密测试。公有产物和日志仅含脱敏证明，不保留临时私钥、明文或密文凭据包。完成时清除 D1 密文；过期读取会拒绝并清除密文，不能将其描述为无人访问时也会准时执行的定时清理。

此入口严格限定 `synthetic`，尚未启用真实 Apple 凭据交接或三类实际导出任务，生产切换仍未完成。下一步需要 CircleCI 原生适配现有 GitHub 专用导出/TF 会话与加密门禁，保持完整明文证明，不能通过伪装 `GITHUB_ACTIONS` 绕过。随后还需历史账本/会话交接、持久上传与取消/未知结果闭环、真实私有交付和单一机器人入口切换。VPS 仍是唯一线上机器人；没有 Apple 操作、重新接受历史邀请或重复发送历史文件。

后续普通推送默认不启动 macOS 样例；仅显式设置 `validate_arm64_archive: true` 或 `build_native_runtime: true` 才选择 ARM 工作流。已有运行期构建/消费者 marker 仅在显式选择 ARM 后生效。Linux 签名探针仍独立选择，不能启动 macOS。此门禁减少无关构建消耗，不证明账户当前配额、账单或自动充值设置已核实。


## 真实云端签名调度闭环已验证（2026-11-26）

[GitHub 45833846829](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45833846829) 在源码 `61e9bfa2ffd63814799b00943c537e369c4d9bf4` 通过 workerd/D1、OIDC 与旧入口回归，并部署独立控制探针。Cloudflare Worker 使用私有 CircleCI 调度令牌提交一次任务，CircleCI [job 57](https://app.circleci.com/workflow/864a2051-adc9-4a64-be61-5b4bb82593e7/job/417fd373-ae51-41ba-a781-75cbed05dcf2) 用真实 V3 OIDC 身份领取并完成回调；控制端从 CircleCI API 确认同源码 run `0e8fa45d-81b7-4ac2-b44e-3ad74a25def9` 成功结束，D1 持久完成记录已回读。逻辑任务 `pilot_5b2dfa4b32bc4414f788e6558eb69c55`，公共 bundle SHA-256 `fc2375da1dc6b586b74dc6a5fc06dbebadce93f22bc1a235bded367b48da1581`。

修复了 Workers 不支持 `redirect: "error"` 导致请求构造失败的问题：出站请求使用 `manual`，严格拒绝非预期 HTTP 状态，不跟随重定向；workerd 模拟接口先实际构造 Request，JWKS 重定向也有拒绝检查。早期无凭据空探针的不明确提交记录保留原始 unknown 意图，仅为该固定任务增加审计解决记录，未重置或重复提交旧任务。

[GitHub 45833797131](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45833797131) 通过 10 项实际 age 加密测试：一次性私钥、任务/run/worker/source/nonce/期限绑定、篡改/错误密钥/额外凭据拒绝、最小子进程环境。后续 opaque lease 集成仍只允许 synthetic 配置，真实跨云加密交接的通过证据需单独记录。

现有 Google 私有绑定、D1 及关闭的 Telegram/链接开关保持不变；VPS 仍是唯一生产机器人。本检查点没有 Apple 操作、IPA 上传、消息发送或生产切换。仍需完成三类实际任务的 CircleCI 适配、真实凭据/加密会话与 TF 历史账本交接、取消/未知结果闭环、私有 Drive 交付、费用门禁及单一入口交接。当前服务器未编译或执行项目测试。


## 三包构建与独立加载已验证（2026-11-26，最新）

同源码公共构建 [CircleCI job 40](https://app.circleci.com/workflow/ca2fe102-a78d-4284-a20f-321d5ccdfa1e/job/1e3c2e16-037e-47cd-8166-3096fc4cb817) 已成功，源码 `fa258c072f246011079affe7cecd369422ecef0d`，macOS 26.3.1 / ARM64 / Xcode 26.5。base 21 项 Swift、CN 29 项 Swift、TF 24 项 CTest，以及 Go/Python/Node 检查、三包库存/摘要与迁移后运行验证通过。base/CN 各 82 个文件，TF 12 个文件；版本与归档摘要已固定在 `deploy/managed/circleci/runtime-pins.json`。此前失败的部分产物不是这些已固定的成功包。

独立全新 CircleCI 机器上的 [job 42](https://app.circleci.com/workflow/e7d74048-1f20-4aa3-92c8-8ee2bad6bfb2/job/acbd80db-9744-4fde-b097-f103bc4a0309) 也成功，验证源码 `00ede25676b1e98aae9cc99b5660eb170295c55e`。未编译本项目，实际下载三包，核对成功 job/workflow/run、项目与源码、原生输入 Git 对象、固定 SHA-256、包内逐文件摘要及当前主机 ABI，再运行默认/CN CLI 与 TF 自检；三份 consumer JSON 已从 CircleCI 公开产物回读核对。

加载器拒绝失败/未结束/来源不符的 producer、原生输入变更、错误包类型、非许可下载地址、摘要不符或依赖版本变化。文档及独立消费者修改不强制重新编译；原生输入变化必须更新经过验证的 producer/pins。加载器对公开 CircleCI 仅作无令牌读取，运行前保留 CircleCI/ARM 主机门禁，不伪装 GitHub 环境。[GitHub run 45825545108](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45825545108) 通过 13 项包测试、8 项加载器测试和所有相关 shell 语法检查。

CircleCI API/真实 OIDC 身份及 D1 8 项恢复验证见下方历史检查点。这些底座已验证，**生产迁移尚未完成**：任务入口、凭据/加密会话与 TF 历史账本交接、取消和未知结果闭环、真实私有 Drive 上传与端到端交付、费用门禁及单一机器人入口切换仍需完成。没有切换线上机器人、操作新的 Apple 邀请或重复历史文件发送。当前服务器没有执行本项目编译或测试。


The owner uses this project personally and does not require a 24-hour worker. Production remains on the VPS until a verified single-controller handover. See [current status](../../../docs/PROJECT-STATUS.md) for completed and pending evidence.

## Public native producers

`[circleci-runtime-build]` or pipeline parameter `build_native_runtime=true` requests the full public producer. `[circleci-tf-runtime-build]` requests only the TestFlight producer for isolated diagnosis. Ordinary pushes run only the existing owned sample validation.

The macOS 26 / Xcode 26.5 / M4 Pro Medium producer builds pinned public sources without account credentials:
- `base`: default App Store Swift client and Go helpers.
- `cn`: separate CN session/catalog client using those same Go helpers.
- `testflight`: independent SDK client and its native libraries.

Artifacts use `public-arm64-native-runtime/<variant>/native-runtime.tar.gz` and `build-receipt.json`. Schema v2 requires the exact variant, source fingerprint, successful CircleCI source/workflow/job, ARM64 platform, toolchain and TF dependency versions. It rejects unexpected members, escaping paths, links, duplicate entries and digest changes. Every variant must pass relocation with its original build directory hidden. Failed jobs' partial artifacts are ineligible for production.

A future consumer must authenticate the successful job through CircleCI and compare the expected source contract and current runner ABI before executing any binary. The manifest cannot authenticate itself. Source-pinned CLI fetching and fresh-runner validation are implemented; production task entry points remain unconnected. Existing GitHub Intel runtime schemas and guards are preserved; never spoof `GITHUB_ACTIONS=true` on CircleCI.

## Runtime consumption

The reviewed `runtime-pins.json` selects the successful producer and exact archives. A consumer commit marker `[circleci-runtime-consumer]` selects `verify-runtime-consumer.sh`; no project compilation occurs in this mode. Public Homebrew dependencies are installed and must match the pinned ABI before binaries are executed. A runtime that expires or no longer matches must be renewed explicitly; ordinary tasks do not silently compile or substitute another package.

`fetch_runtime.py` compares native input Git objects with the pinned producer, authenticates successful source/project/run/workflow/job through public CircleCI metadata, checks the fixed archive digest and safely extracts through the variant-specific verifier. Redirects stay on approved HTTPS artifact hosts; no API/account credential is sent to download hosts. The current native input contract intentionally excludes documentation and standalone consumer code.

## API and job identity

The owner has already configured Actions secret `CIRCLECI_API_TOKEN`. Do not ask them to send it in chat or duplicate setup. The fixed-repository workflow `.github/workflows/circleci-connection-probe.yml` uses it only within GitHub, sends one synthetic API v3 run, stores the nonsecret acknowledged ID and polls that same run. Transient read 404s do not cause another POST. Only nonsecret source/request parameters reach CircleCI.

`oidc.mjs` verifies CircleCI V3 RS256 signatures against the fixed issuer's public JWKS, audience/time, owner, project, checkout and config sources/refs, definition/run/job and SSH-rerun flag. Expected run/job IDs must come from the trusted dispatch record and CircleCI metadata, never directly from the caller's JWT. Signed identity is only part of future authorization; Worker routes and credential release are not implemented by this probe. No raw JWT is stored or logged.

## Durable dispatch candidate

`dispatch.mjs` is **synthetic-only** and not wired into the bot. Apply its migration only to an isolated pilot D1 after the existing pilot jobs/link tables; it is not a migration for the production VPS journal. Never clear existing intents to retry a job.

The D1 intent precedes the sole external POST. Owner/job/source/request binding, unique jobs and a global active-run guard prevent duplicate/concurrent dispatch. Intent acknowledgement loss sends nothing; uncertain trigger outcomes stay blocked across restart without expiry. Successful API acknowledgement binds the run ID. Only source/project/definition-bound successful readback releases capacity; GET readback never triggers another run. Network operations have a 15-second bound.

`dispatch.integration.mjs` exercises real local workerd D1 through Miniflare with synthetic HTTP, including concurrent claims, restart, lost acknowledgements and timeout. It does not prove deployed cloud execution. All tests run in CI only.

## Remaining production work

Complete production entry points and state/credential handover, durable TF acceptance/cancellation/unknown-result records, private Drive upload receipts and limits, account credit bounds and single-poller/webhook cutover. Preserve App Store default/CN, available historical versions and owner-only TF. No new enrollment/security upgrade, historical invitation replay or old file resend is part of public builds.

References: [CircleCI API](https://circleci.com/docs/api/v3), [OIDC](https://circleci.com/docs/guides/permissions-authentication/openid-connect-tokens/).

## CircleCI 接入与持久化调度候选（2026-11-26，最新）

用户已配置 `CIRCLECI_API_TOKEN`，无需再次索要。令牌在 GitHub 密钥步骤内认证通过，账号与既有触发者一致，可读取固定项目/定义并提交任务。使用 API v3 创建 run；创建后查询接口可能短暂返回 404，只能重读同一 ID，绝不因此重复 POST。[完整调度与真实 OIDC 验证 45820517834](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45820517834)通过，源码 `cd3964da45324b59bf1f8d56a5a02a1c9bf5d649`。

真实 CircleCI run `a9e78112-ddff-41b3-aeb3-c1bd9a938c0f`、[job 33](https://app.circleci.com/workflow/91165577-39cf-4158-a323-809d36e54042/job/23f40104-d13f-4ef7-bd11-ad3707d8ad9a)通过 CircleCI OIDC V3 签名、公钥、issuer/audience、时效、账号、项目、配置/检出仓库及分支、definition/run/job 和非 SSH 重跑检查。公钥地址来自该 issuer 的 discovery，为 `/.well-known/jwks-pub.json`。不保存或输出原始 JWT；当前任务无需另建 context 即可取得 V3 token。11 项 Python 调度测试和 7 项合成签名测试通过。此证明不等于 Worker 已接入这些身份检查或已获得生产凭据。

新增 `deploy/managed/circleci/dispatch.mjs` 和独立迁移 `migrations/0001_dispatch.sql`，目前仅供合成任务，尚未接入实际机器人或应用到远程 D1。提交前持久化 intent，绑定 owner/job/request/source/run；全局串行，已有链接/取消/重复任务拒绝提交，未知结果不超时重置。POST/GET 限时 15 秒。只有来源和成功状态核对一致的 readback 才能释放下一任务。[D1 验证 45822528880](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45822528880)在实际本地 workerd/D1 上通过 8 个场景，覆盖并发、重启、意图或回执丢失、超时、防重提及错误 readback；CircleCI 传输为合成替身，不是真实云端 D1→CircleCI 提交证据。

公共运行包升级至 `circleci-native-runtime-v2`，区分 base/cn/testflight，并绑定源码、ARM64、工具链、TF 依赖版本和逐文件摘要。源码 `230af2f3cc169652b8c09e5b034526c1e5f1d2ff` 的 job 35 已通过 base 的 21 项 Swift 和 CN 的 29 项 Swift 测试、两包打包及隐藏原目录后的 CLI 运行；整个 job 因后续 TF Homebrew 安装失败而失败，这些产物不能当作成功生产包获取。13 项包校验测试通过。

TF 独立 ARM 构建已通过：[CircleCI job 39](https://app.circleci.com/workflow/39ffd3f2-5f09-491d-8fa0-aaf8913ca302/job/31d27271-8022-4fef-a3a8-9dd4d5e29d77)，源码 `2df098277cb266a5c5456c3fdd6b2e65cff7d38b`。显式更新 Homebrew 后依赖安装成功，24 项 CTest、打包校验和隐藏原构建目录后的三项 CLI 自检全部通过。schema v2 产物 12 个文件，归档 SHA-256 `a20265d58a46d2922ebadc36af6dfcc3006eba0950fc9ab63c05b6ad17863d56`，源码指纹 `f8c60a1b44f12ebe692b5baae34ad4e93fb34f9adad9f97481ab244231f01326`。已回读公开 receipt 核对来源和依赖。它仍依赖记录的 Homebrew ABI，并不证明干净机器无需依赖即可运行。三包同一源码的完整成功任务正在补做。

剩余：三包同源码成功来源证明、任务端受信运行包获取、凭据与加密会话交接、TF 接受/取消/未知结果的完整持久化、私有 Drive 上传与回执、费用上限以及单一机器人入口切换。原 VPS 继续承担生产；没有切换 webhook、执行新的 Apple 操作或重复历史邀请/文件发送。所有编译、项目测试和模拟 D1 执行均只在 GitHub/CircleCI，当前服务器仅做 GitHub/API 协调。

