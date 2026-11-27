# 项目进展

## 当前生产与真实国区交付（2026-11-27）

截至2026-11-27，生产已切换到原机器人 + Cloudflare Workers/D1 + 按需CircleCI macOS ARM64 + 私有Drive交付。[成功切换45918215266](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918215266)对应处理源码`185a52110922e0f67ac2c7dff4e1fa85b3b4c98e`。CircleCI75真实国区任务已完成下载、17镜像/120,976页严格验证、342,632,968字节私有上传及主人通知；新平台历史版本交付和新TF任务仍待分别真实验收。

[CircleCI75](https://app.circleci.com/workflow/2ae89675-bc82-451c-b290-4ee63c2c360a/job/a1e13406-0c02-43ec-a679-5a5bfa77fd53)排队约49.9秒，执行约212.8秒，全程约262.7秒；脱敏收据decryption_proven/file_upload/telegram_send/production均为true。签发[45918580709](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918580709)成功。安装及实际运行仍未验证。此前73/74为独立失败请求，未自动重放；75是主人重新提交的新请求。

国区维护[45917018396](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45917018396)及原生会话复用[45917154187](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45917154187)均通过，没有使用验证码或新增/撤销电脑授权。HTTP401不足以单独证明原CircleCI失败根因；新诊断确定74为account_cache_unavailable。HOME/CFFIXED_USER_HOME修复通过[真实Foundation检查45917974219](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45917974219)，并由75验证实际成功。

/status截图约1秒回复。当前入口只有主人权限、pilot_任务编号和私有Drive通知；旧白名单、附件发送、五秒计时卡未迁入新入口，详见[操作手册](OPERATIONS.md)及[Telegram指令](TELEGRAM.md)。2条旧pending和源丢失后的未知变化继续held；source_disabled_verified仍为false。

运行分支必须固定到控制面源码。此次仓库/文档整理只提交维护分支和默认分支导航，不改变上述生产HEAD、不重跑Apple任务。9个旧分支已在archive/branches/2026-11-27/标签逐一归档后删除；保留main、生产和维护3分支。[仓库审计](REPOSITORY-AUDIT.md)记录548文件/27份原有Markdown的检查结论。

以下为按日期保留的检查点。其中“当前”“最新”“尚未上线”只适用于当时记录；以本节及最近成功切换回执为准。

## 国区会话维护及原生缓存目录修正（2026-11-27，上线前记录）

用户已单独授权维护原国区会话。GitHub45917018396成功以原账号/GUID登录，无验证码；密封会话按run/source/摘要/收据和仓库公钥绑定更新APPLE_CN_SESSION_B64。原生只读复用检查45917154187成功，随后保存其最新刷新会话；未下载、授权/撤销电脑或更换模型。旧摘要接口HTTP401仅说明该请求被拒绝，不能单独认定CircleCI失败根因。

上一轮诊断上线45917262453于源码6e619dc72b7d1766d1af1eb6cb04d3553a5e39f5成功。用户重新发送后，CircleCI74及签发45917712478使用相同源码，原生诊断明确account_cache_unavailable，仍未下载。Apple CoreFoundation CFPlatform.c的目录解析优先顺序为CFFIXED_USER_HOME、passwd账号目录、最后HOME；只设置HOME不能确保FileManager使用临时账号缓存。

维护候选在所有私有原生子进程环境同时绑定HOME与CFFIXED_USER_HOME，且覆盖任何继承值，原缓存读取/销毁和账号绑定要求不变。新增真正macOS Foundation回归，在隔离目录读取合成缓存并验证清理；现有模拟原生runner也必须断言相同目录绑定。仅GitHub执行测试，无本地运行、原生源码更改或账户操作。原失败任务73/74不自动重放，成功发布后由用户提交新请求验收。

## 国区真实任务与会话诊断（2026-11-27）

该检查点生产切换45915238970已成功，当时运行源码73c62183dc61984869ebaec98349a32ba99331df；用户08:16:32→08:16:33的/status截图确认约1秒回复。该运行分支保持不变，以下诊断改进只在维护分支准备。

用户实际发送红果漫剧6745890963后，CircleCI73成功取得cn角色凭据（GitHub45916424720），在resume-cn阶段失败，未开始下载、解密或上传。cn_session_requires_maintenance只是通用退出错误，不能单独证明会话过期或验证码挑战。随后只读检查[45916808829](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45916808829)验证了保存会话结构与国区绑定，但Apple返回HTTP401；未登录、使用验证码、授权/撤销电脑、下载或更新Secret。需要维护原会话，不能自动重放这次失败任务。

维护候选增加原生退出结果的固定词汇分类及私有缓存目录权限，原始stdout/stderr、账号、路径和链接均不公开；分类仍不能把ambiguous_bad_login说成明确验证码挑战。回归覆盖一次失败后不重试、不调用login/download、清除缓存和脱敏输出。会话替换须获得单独授权，保留原GUID、模型、checkpoint与历史意图；未获授权前不执行登录维护。

## 生产切换及真实消息验收（2026-11-27）

[离线生产切换45913375750](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45913375750)已成功，初次运行源码aaa2278038b7f2d22bed459b647cccb0cba3e93f，脱敏收据artifact15161451437。完整读回29条历史任务、89条updates、14条metadata，2条pending保持held；原Go Club已完成任务、私有文件和确认通知保留。原TF历史邀请按pinned接受/确认记录构造防重tombstone并seal，未重新接受。新Token属于原机器人，旧Token已失效，5个旧派发/目录工作流保持disabled；新webhook和真实cron触发均取得回读，production_cutover:true。

用户随后提供IPAZaKe聊天截图：08:02:33发送/status，08:02:40收到Go Club“已核验，可用/get领取”和原失败任务“任务已结束”。真实入站及回复已确认，但约7秒延迟需优化。当前改为一次读取最新5条已提交状态，避免/status逐项调用完整核对与排队逻辑；外部终态由cron继续核对。新增真实workerd/D1查询预算回归，5条结果应在最多8次D1调用内完成，并隔离他人记录。每次源码升级也必须等该源码自己的cron观测回执，不能借上个版本的旧时间戳放行。

**运行分支upgrade/managed-runtime-v0.2必须与Cloudflare.RUNTIME_SOURCE_SHA一致，不能在入口开启时直接推送。**CircleCI checkout和GitHub凭据签发都引用该分支HEAD。维护从独立upgrade/managed-runtime-maintenance-v0.2准备并验证，先用已验证的原运行包关闭空闲入口且保留旧source/DB/Secrets，再将同一已验证commit推进运行分支，执行Offline managed runtime cutover并等待新source的真实cron。上线后的新收据是最终运行源码依据，不再直接为补文档改动运行HEAD。

旧机之后未保全的变化仍未知；不伪造物理停机或无缺口证明。旧offset/browser原样保留，切换前的消息持久隔离，不重放旧任务。计费入口保持关闭，无本地构建/项目测试或旧机SSH依赖。

## 离线恢复与原机器人 Token 交接（2026-11-26 23:38 UTC）

用户明确原运行环境无法使用，迁移改用保全的加密备份，不再等待SSH恢复；用户选择保留原机器人并更换Token。新Token仅存MANAGED_TELEGRAM_BOT_TOKEN，不覆盖旧工作流的TELEGRAM_BOT_TOKEN。

[离线恢复45912001065](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45912001065)在源码bbf92311d908916834c27555d2df120a3cf4a5b4成功：重新认证并读回同一份378022字节源密文，完整保存29条任务（closed7/delivered20/pending2）、89条updates（unfinished0）、14条metadata，包括offset与version_browser，以及6个Telegram状态文件的索引。原私有回传1条confirmed、未知0，原接受账本仍不存在。恢复清单加密后再解密比对，SHA-256为675f966d71e0dd432a19f6a585d5fef637bc6da0c478a7e02ba74104887448da；artifact15160242814仅包含加密计划和脱敏收据。原加密源仍长期保存在独立13段Secrets，计划可从其重新生成。7项公开合成测试覆盖篡改/账号绑定、未知更新和接受结果保留、Token更换与旧工作流退役边界。

真实Bot API只读身份检查已确认replacement_same_bot_verified:true、old_token_rejected:true；未发送消息，未提交新的Apple任务。5个旧工作流已在确认无运行任务后停用，并由独立GitHub运行重新核对disabled_manually、active_runs0：private-delivery.yml、china-private-delivery.yml、testflight-private-delivery.yml、version-catalog.yml、china-version-catalog.yml。已核对原运行环境实际安装源码b70d0f3730651ebcc03c8d4ca31e9e5d4bd84c51：启动时先要求private-delivery.yml active，再启动本地Bot API与恢复任务；同时停用所有旧派发入口，防止旧机继续提交下载。未撤销共用GitHub派发凭据，未停用新CircleCI签发/验证工作流，未清除历史记录。退役清单见deploy/managed/circleci/legacy-dispatch-retirement.json，启用前仍需新鲜读回。

这是离线恢复准备与凭据更换验证，尚未写入正式D1交接、安装新webhook或启用生产。旧机是否停机仍未证明，恢复清单正确保留source_disabled_verified:false、telegram_isolation_verified:false、permanent_handoff:false。上次快照后旧服务曾恢复，无法保证其后全部变化可取回；缺口必须明确保留，两个pending及未知操作不重放。后续应实现独立的离线交接凭证（新Token/旧工作流隔离、历史数据逐项读回、旧消息隔离和后台调度），不能伪造旧机stopped_at或把有时限快照改成最终冻结证明。TF历史接受 tombstone 仍须按原公开证据重建后才能启用新接受权限。Go Club任务、文件和已确认通知不重复。

## 版本目录、分页与选择下载已接通（2026-11-26）

候选源码5b25f0298ff0e16ddfd10d084fcac0cf3ab632d6已接通 owner-private /versions、目录排队、默认/国区专用元数据凭据、分页按钮与精确版本选择。该源码的[控制端验证45910022331](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45910022331)成功：81项控制端/OIDC/D1/交付集成测试和16项既有入口测试全过；包含默认/CN目录实际签发协议、禁止目录任务访问上传/导出接口、消息确认、翻页与整组列表单次选择、缓存、刷新、独立查询配额、终态核对后队列推进。Python执行接线9项及既有工作机验证在[45909860642](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45909860642)通过。目录原生传输测试10项、age凭据测试11项保持通过。均为 GitHub 合成验证，不是新的真实账号查询或应用下载。

控制器新增关联表记录目录子类型与不可变分页结果，不重建原runtime_jobs或删除已有Go Club任务、文件/通知记录。目录与导出共享串行调度；目录凭据只有登录/保存会话字段，不能访问模型、检查点、上传或解密路径。每日目录查询20次，初次/刷新间隔60秒、续页5秒；新鲜缓存24小时；每页最多10条、最多20页。菜单仅本人私聊，绑定机器人消息编号与6小时期限；选中后整组各页关闭；重复同一选择沿用固定导出请求；不同版本不能借旧列表再提交。通知先记意图，仅确认正确私聊回执后启用按钮；未知回执不自动重发，新命令可以重新打开缓存。

增加runtimeTick与Worker scheduled处理器，核对已知CircleCI终态后推进等待队列。**当前未安装生产定时触发器、未部署本轮候选到正式入口、未setWebhook。**最终启用时仍需安装定时触发器并验证单入口，不能让无人点击/status时的等待队列停住。原运行环境仍被服务商暂停，最终冻结/状态差异/offset/历史浏览器及接受账本交接、旧poller永久停用仍未完成。不得把旧有时限快照作为最终交接凭证，也不得自动重跑Go Club或历史pending。

附带修复 ARM 容器验证的清理竞争：原流程使用 detached --rm，停止返回时卷仍可能被异步删除中的容器引用；现在明确stop并rm本次测试容器，再删除自己的临时卷。GitHub [45910269227](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45910269227)（源码eb5acb39259cb79db959192ab01759088a7b23c6）全部通过，包括ARM状态服务两次启动/鉴权、镜像导入以及两个架构归档验证。没有在当前服务器或VPS上构建、安装测试依赖或执行项目测试。

## 原运行环境 停服与最新加密快照长期保留（2026-11-26 23:08 UTC）

用户截图显示 KiwiVM 无法再次临时恢复服务（721104），与最新 GitHub SSH 超时一致。旧机最后暂停快照的原 artifact15139574335 会在2026-12-03 17:19:40 UTC到期，早于旧页面显示的12月5日流量重置日。因此已将**同一份378,022字节 age 密文**另存到仓库 Secrets：CIRCLECI_CANARY_45866115288_01 至 _13，以及 _INDEX。通过 GitHub API 在内存中校验固定来源/归档和完整摘要后分段保存；未解密、未创建本地文件、未覆盖早期13段基线备份或 TF 原会话。

[独立读回45908994642](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45908994642)成功；源码2ab7f09a4d0fb87d635ec00b537ad67d2bece624，SHA-256仍为28654b814e6f38c7dddd0fdb79d5d2202aa8915c23db840c9792e6c2ed4b16dd，13段完整重组，readback_verified:true、permanent_handoff:false、apple_operation:false。该流程只读 Secrets，不领取管理令牌、交付身份或账号凭据。原artifact到期不再影响此副本，长期保留依赖仓库和这些Secrets仍存在。

这是旧服务上次有时限暂停时的备份，随后旧服务曾恢复；不能证明恢复后至停服期间没有新状态。不能用它冒充最终冻结快照，也不能因 VPS 暂停就假设旧 poller 永远不会在流量重置后恢复。最终需确认源状态差异和旧入口永久停用，才能激活新日常入口。旧 pending 持续 held；Go Club 完成记录、私有文件和确认通知不重复。

## 版本目录迁移推进（2026-11-26 23:03 UTC）

新增 CircleCI 历史版本元数据执行器，复用已验证的原生运行包与目录分页解析器；按来源、任务、工作机、账号区域和游标绑定结果。查询最多10条版本记录，拒绝游标倒退、异常包文件及会话区域变化。普通账号密码仅传登录子进程；国区仅恢复既有会话，失效即要求维护。目录角色 default_catalog / cn_catalog 仅领取所需账号字段，不领取 FairPlay 模型、检查点、交付密钥或 Drive 凭据；独立 GitHub 签发作业保持最小 Secrets 范围。该执行器尚未接入正式控制端排队与 Telegram 分页按钮，不能据此声称目录全链路完成。

新增 GitHub 合成测试覆盖模型隔离、账号区域变化、会话维护失败、取消清理、异常下载、游标与运行包摘要。[工作机验证45908601584](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45908601584)通过：新增目录10项、凭据加密11项，以及原默认/CN17项、TF6项、上传/执行与归档验证均通过；[控制端45908601586](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45908601586)亦成功。验证源码2315f12aafce9afb7abc1a73d1d961bf3471930b。无当前服务器编译或项目测试。

最新[只读源状态检查45908023150](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45908023150)的公开检查通过，但源检查 SSH 超时（exit255、结果0字节）；尚不能取得最终冻结状态或停用旧轮询。用户后续 KiwiVM 截图明确显示无法再次临时恢复（错误码721104），页面要求等待流量重置或升级；这仍不能视为已完成永久停机交接。此前 Go Club 成功任务和确认通知保持原记录，不重复执行。

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


## CircleCI 接入与持久化调度候选（2026-11-26，最新）

用户已配置 `CIRCLECI_API_TOKEN`，无需再次索要。令牌在 GitHub 密钥步骤内认证通过，账号与既有触发者一致，可读取固定项目/定义并提交任务。使用 API v3 创建 run；创建后查询接口可能短暂返回 404，只能重读同一 ID，绝不因此重复 POST。[完整调度与真实 OIDC 验证 45820517834](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45820517834)通过，源码 `cd3964da45324b59bf1f8d56a5a02a1c9bf5d649`。

真实 CircleCI run `a9e78112-ddff-41b3-aeb3-c1bd9a938c0f`、[job 33](https://app.circleci.com/workflow/91165577-39cf-4158-a323-809d36e54042/job/23f40104-d13f-4ef7-bd11-ad3707d8ad9a)通过 CircleCI OIDC V3 签名、公钥、issuer/audience、时效、账号、项目、配置/检出仓库及分支、definition/run/job 和非 SSH 重跑检查。公钥地址来自该 issuer 的 discovery，为 `/.well-known/jwks-pub.json`。不保存或输出原始 JWT；当前任务无需另建 context 即可取得 V3 token。11 项 Python 调度测试和 7 项合成签名测试通过。此证明不等于 Worker 已接入这些身份检查或已获得生产凭据。

新增 `deploy/managed/circleci/dispatch.mjs` 和独立迁移 `migrations/0001_dispatch.sql`，目前仅供合成任务，尚未接入实际机器人或应用到远程 D1。提交前持久化 intent，绑定 owner/job/request/source/run；全局串行，已有链接/取消/重复任务拒绝提交，未知结果不超时重置。POST/GET 限时 15 秒。只有来源和成功状态核对一致的 readback 才能释放下一任务。[D1 验证 45822528880](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45822528880)在实际本地 workerd/D1 上通过 8 个场景，覆盖并发、重启、意图或回执丢失、超时、防重提及错误 readback；CircleCI 传输为合成替身，不是真实云端 D1→CircleCI 提交证据。

公共运行包升级至 `circleci-native-runtime-v2`，区分 base/cn/testflight，并绑定源码、ARM64、工具链、TF 依赖版本和逐文件摘要。源码 `230af2f3cc169652b8c09e5b034526c1e5f1d2ff` 的 job 35 已通过 base 的 21 项 Swift 和 CN 的 29 项 Swift 测试、两包打包及隐藏原目录后的 CLI 运行；整个 job 因后续 TF Homebrew 安装失败而失败，这些产物不能当作成功生产包获取。13 项包校验测试通过。

TF 独立 ARM 构建已通过：[CircleCI job 39](https://app.circleci.com/workflow/39ffd3f2-5f09-491d-8fa0-aaf8913ca302/job/31d27271-8022-4fef-a3a8-9dd4d5e29d77)，源码 `2df098277cb266a5c5456c3fdd6b2e65cff7d38b`。显式更新 Homebrew 后依赖安装成功，24 项 CTest、打包校验和隐藏原构建目录后的三项 CLI 自检全部通过。schema v2 产物 12 个文件，归档 SHA-256 `a20265d58a46d2922ebadc36af6dfcc3006eba0950fc9ab63c05b6ad17863d56`，源码指纹 `f8c60a1b44f12ebe692b5baae34ad4e93fb34f9adad9f97481ab244231f01326`。已回读公开 receipt 核对来源和依赖。它仍依赖记录的 Homebrew ABI，并不证明干净机器无需依赖即可运行。三包同一源码的完整成功任务正在补做。

剩余：三包同源码成功来源证明、任务端受信运行包获取、凭据与加密会话交接、TF 接受/取消/未知结果的完整持久化、私有 Drive 上传与回执、费用上限以及单一机器人入口切换。原 VPS 继续承担生产；没有切换 webhook、执行新的 Apple 操作或重复历史邀请/文件发送。所有编译、项目测试和模拟 D1 执行均只在 GitHub/CircleCI，当前服务器仅做 GitHub/API 协调。



## Latest direction: owner-only, on-demand CircleCI (2026-11-26)

The owner explicitly selected CircleCI for personal link-triggered use; 24-hour worker availability is not a requirement. This supersedes earlier hosting comparisons that treated an always-on worker as necessary. Target: Telegram webhook → Cloudflare Worker/D1 durable state → bounded CircleCI macOS worker → private Drive link. Keep App Store default/CN, available historical versions and owner-only TestFlight in migration scope.


### Verified public ARM producer — 2026-11-26

CircleCI workflow [ec99aa78-a31d-4cff-983b-e0fc4abac4c0, job 17](https://app.circleci.com/workflow/ec99aa78-a31d-4cff-983b-e0fc4abac4c0/job/1145ceb4-77f3-42d7-8ef4-8502428c2290) succeeded at source `b3ed18c5f7850d223e030a8ee84b75930f2f3700`. Actual host: macOS 26.3.1 ARM64, Xcode 26.5 build 17F42, Swift 6.3.2. Go/Python/Node checks, 21 selected Swift tests, allowlist/digest verification and relocated CLI execution passed. The initial job 16 failed because the image lacked Go; the successful source installs the bootstrap toolchain inside CircleCI.

The public archive has 53 files; SHA-256 `7f3ffb80d5e2f20018b403d24533672e33e74238dd62cfee5cdbe6c3694b2c2c`, source fingerprint `b78dc6c819bff0735398f01e0533c10a465e0956d5b4374fde5180fc2fc602e3`. CircleCI artifacts list both `public-arm64-native-runtime/native-runtime.tar.gz` and `build-receipt.json`; the latter was read back and matched the source/workflow/job/toolchain and 53-file inventory. No independent consumer download/ABI execution or private account operation is claimed.

GitHub [bundle contract run 45816912649](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45816912649) passed 9 focused tests and shell syntax checks; [managed runtime contracts 45816922963](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45816922963) passed. Compilation and project tests ran only in CI.


The existing GitHub App integration already triggers CircleCI from this branch. The new public ARM64 producer is gated by the boolean pipeline parameter `build_native_runtime` or an explicit `[circleci-runtime-build]` commit marker. Ordinary pushes still run the existing owned-sample check, but do not rebuild the native runtime. The producer receives no account secrets and emits only public binaries/resources/licenses with source, architecture, CircleCI workflow/job and toolchain provenance. Relocation and fixture checks must pass before reuse. CircleCI packages use a separate schema; existing GitHub Intel producer guards and production fingerprints are preserved.

This is a staged implementation, not a production cutover. Public artifact verification is not Apple acquisition/decryption evidence. CN/TF runtime variants, authenticated worker claims, durable acceptance/upload/cancellation handling, source-bound runtime fetching, bounded credits and actual owner-private delivery remain necessary. The CircleCI API token/account connection has since been verified; see the latest checkpoint above. Do not place tokens in chat or pipeline parameters. Existing VPS polling and all historical state remain in place until a separately verified handover; never activate a webhook concurrently with that poller.


## 当前状态（2026-11-26）

- **公开发行**为 [v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。11 月 9 日刷新了公开附件，源码以 `BUILDINFO.json` 为准。国区历史版本属于之后的线上部署。详见[发布说明](RELEASES.md)。
- **线上控制器**最近一次成功部署为 [42727462163](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42727462163)。11 月 25 日的[只读检查](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45638716965)记录服务健康、当时没有活动任务，仍采用 VPS 轮询。当天的[加密备份](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45637494802)包含控制器、Telegram 状态、TestFlight 会话密文和回执库；检查时标准路径中缺少可核验的 TestFlight 接受记录。
- **v0.2** 仍是[草稿 PR](https://github.com/zwthys-cyber/ipa-decrypt-lab/pull/1)。最新[托管运行时验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45808213138)通过 ARM64 镜像构建、独立导入、持久卷预检、状态服务重启，以及双架构合成 ZIP64 全量读取。Drive 上传校验新增了媒体类型改标回归，仍核对大小、SHA-256、归属与权限。
- **私有交付试验**完成了项目自有 ARM64 样例的 Drive 存取和[一次 Telegram 私聊链接发送](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45644694693)，接收人确认可打开。生产 webhook 切换和真实 10 GB 网盘传输仍待验证。详见[零费用试验记录](ZERO-COST.md)。
- **主仓库 CircleCI** 的[首跑](https://app.circleci.com/workflow/7fcc4b73-7caa-4de2-8f16-763288eb34e2)通过 84 项测试，三个 Smarter Testing 套件均通过 Doctor。[CircleCI M4 Pro](https://app.circleci.com/workflow/40131029-8872-4661-8351-f1b0fd0034ba/job/c35d0d9a-2113-4b8a-b3fe-07db03f99967) 另通过了项目自有 iOS 样例的构建和归档校验。指定 `cimg/base:stable` 当前为 Linux amd64，glibc 2.31；workerd 集成仍由 GitHub Actions 验证。

## 迁移来源审计与历史恢复候选（2026-11-26）

[源审计 45811165425](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45811165425) 在 8 项公共测试通过后，经固定主机指纹和 IPv4 只读检查 VPS。心跳新鲜、当时空闲；TF 任务共 1 条、未完成 0 条；会话密文与原推广摘要一致；接受库及扫描范围内旧候选均不存在；原私有发送回执 1 条、未知发送 0 条。此轮没有停止服务、调用 Apple/Telegram、初始化或修改源记录库。Linux 运行器先前连接超时，Intel macOS 出口最终成功。

原接受意图 Git blob 与首次提交一致；59 次保留研究运行中只有原作业出现接受步骤。原接受作业失败与后续只读成员确认成功分别核实，不能将失败记录改写成成功。[恢复候选 45812495918](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45812495918) 源码 `00dca9f` 通过 6 项公共测试、真实历史日志及意图包来源校验，生成带来源表的单条已确认历史记录库，并验证加密后的解密回读。只保留一天的密文、闭合收据和摘要；`production_installed=false`，安装前仍需重新核对完整源状态。

已知历史来源现已可核验，恢复候选已经产出；没有将空库或未校验的初始化当作迁移完成。生产目标仍未落实：本轮官方资料复核发现 Fly.io 新 Free plan 用尽额度后自动转按量付费，Cloudflare Containers 需要付费计划；其他已查候选也未满足当前全部条件。详见[迁移运行环境与来源证据](MIGRATION-READINESS.md)。完整切换尚未执行。

## 迁移源快照预检（2026-11-26）

源码 [`82a7d4c`](https://github.com/zwthys-cyber/ipa-decrypt-lab/commit/82a7d4c2c119ade3f4780bd4e00868881be98cc6) 为离线迁移工具增加 `--inspect-source`：无需准备目标目录，就能分别报告控制器与 TestFlight 状态快照的结构有效性。输出仅有固定 schema 和三个布尔值；缺失接受记录库时失败退出，不创建替代库。三目录比对同样加强了接受表字段、邀请主键、状态及未完成 Telegram 更新的检查。

[托管运行时验证 45808213138](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45808213138) 已成功：amd64/ARM64 各通过 18 项 managed 测试，其中 9 项为迁移专项，覆盖错误库结构、源数据只读、脱敏输出、退出码、未完成更新及未知接受结果在复制后仍拒绝重试。workerd/D1、双架构 10 GB 合成归档、ARM64 镜像/持久卷/重启/独立导入均通过。同提交的 [push 原生检查 45808202663](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45808202663) 在 Linux、macOS Intel 和 Apple silicon 三平台通过。

此轮仅使用 GitHub API 修改源码、由 GitHub Actions 编译测试，没有在编辑服务器执行项目测试，也没有调用 Apple、读取生产私有状态、创建托管服务或发送 Telegram 消息。预检不能证明接受历史的来源或完整性；11 月 25 日发现的缺失记录库仍需核对来源。符合零费用及无 VPS 要求的生产运行环境、兼容且获授权的处理链路、生产切换和真实 10 GB 网盘传输仍未完成。操作方式见[迁移说明](MANAGED-RUNTIME.md#offline-source-snapshot-inspection)。

以下记录以原验证日期为准。

## 国区历史版本已接入生产（2026-11-10）

`/versions 国区完整链接` 可查询、翻页并点选历史版本；`/version 国区完整链接 版本号或历史ID` 固定国区账号下载。国区/外区缓存、查询请求、按钮、恢复和交付收据均独立绑定。纯数字ID仍默认外区；没有自动跨区或最新版回退。

[真实查询与旧版导出42726551974](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42726551974) 的目录、选择及导出子作业成功：LocalSend目录32条、首批10条；旧版1.18.1/889619746完成31个加密镜像、11,716页明文证明，输出26,887,278字节。最终汇总脚本失败后，[42727462387](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42727462387) 从原摘要验证产物重建证明，严格核对未修改运行包/导出源码，没有重复Apple请求或IPA发送。

[最新部署42727462163](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42727462163) 源码 `b70d0f3730651ebcc03c8d4ca31e9e5d4bd84c51`。双平台原生生产42724891189各通过511项Python（各2跳过）、21项Swift和Go/重定位检查；CN变体42725944546和TF实际回归42726551778通过。Ubuntu/Debian成品回归与来源门禁通过后部署，服务健康检查通过。先前源码的列表缺少profile字段被新增回归拦截；修复后才通过，不将初版失败写成成功。

这证明后台国区历史查询、选择和严格旧版导出及成品部署；本轮没有新Telegram用户请求/文件发送、模型初始化、新电脑授权或安装运行验证。地区许可问题和所有应用兼容性仍未解决。公开alpha.5仍为前次6fa96e8附件快照，不自动包含此次国区历史功能。详见 [国区说明](CHINA-ACCOUNT.md)。

## 文档全量复核与 alpha.5 附件更新（2026-11-09）

[发布42720498732](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42720498732) 已更新 alpha.5 的3个项目成品包和8个附件。服务器 build-only 来源为42720309329/源码 `6fa96e8b4ec7500fad84638dde333c4174c04b30`，两个 Intel 包复用源码指纹完全匹配的42714903141。原发布标签保留，新附件来源由 BUILDINFO.json 与包内 SOURCE_COMMIT 明确记录。25份 Markdown 的内部文件链接和包内清单/源码/摘要检查通过；公开来源清单、校验和及7个被校验附件的 GitHub 摘要已读回核对。

README 最新验证日期已同步到11月9日；历史研究页的当前版本入口、多用户 TF 权限、下载/认证独立路线、VPS密文例外和恢复状态清单均已复核。此次只重新发布项目组件，未部署/重启服务、调用 Apple 或发送IPA。线上仍为下述 d53f7def 部署，详情见 [发布说明](RELEASES.md)。

## TestFlight 自动任务已接入生产（2026-11-09）

主人私聊中的 TF 邀请链接现进入独立 `tf_` 队列，后台恢复持久会话、检查并在必要时接受一次邀请、下载可用 iOS 测试构建，完整明文验证后交给原有私聊交付链路。其他白名单用户仍仅使用 App Store 路线；两条既有地区账号与历史版本行为保留。

[修正版部署 42710092658](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42710092658) 通过 Ubuntu/Debian 13 各492项 Python（各1跳过）、Node/Go、真实 systemd 凭据挂载及运行包门禁，并确认服务健康。此前首版部署漏导入了 `app_from_run`，新增自动交付集成测试发现并修复；不要把首版健康检查当成自动交付已验证。该阶段修正版控制器源码为 `f6ace388a5a25aa75df3781455fade18c6553851`；后续 Beta 命名部署来源见下文。

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


## 2026-11-09 按链接选择中国区或原外区账号（历史阶段）

用户要求按 App Store 链接识别地区。main 已实现 `/cn/` 自动选择独立中国区最新版工作流，其他地区链接和纯数字 App ID 保留原外区账号；该阶段国区历史请求被拒绝；11月10日已接入，见本页的 11 月 10 日部署记录，始终不跨账号回退。编号、固定工作流、进度与回执绑定账号，SQLite 重启恢复、取消、取文件及白名单配额保持隔离。普通国区任务不恢复模型、不申请电脑授权、不接收验证码；会话失效转管理员维护。

[链接与隔离回归 42564779892](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564779892) 通过 480 项主 Python（1 跳过）、68 项隔离 Python 与 5 项 Node 检查；[主分支复核 42564839403](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564839403) 也通过。[双 Intel 运行包 42564839454](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564839454) 已成功，包含本轮公共导出流程复用及账号回执绑定。国区独立客户端、真实导出和 VPS 上线分别验证，后续完成记录单列，不把合成检查当作真实 Telegram 收发。

保存模型的独立新运行器复用 [42563127722](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42563127722) 与保存状态重放 [42563352128](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42563352128) 均对另一款国区应用 1530340312 完成 6 切片、164 页验证，状态/GUID 正确，授权数保持 3，无验证码或新增授权。原模型的 LocalSend 31 切片、11,744 页证明继续有效；旧 Intel 配置仍保存在专用备份。

alpha.5 文档和发布流程包含链接分区，该阶段安装/运行、中国区历史和收费尚未实现；国区历史的后续完成记录见本页开头。原德国区账号 Secrets、模型和安全设置未修改。实际导出、部署与公开发布以完成记录为准。见 [中国区操作说明](CHINA-ACCOUNT.md)。


## 正式导出、部署与发布完成

- [国区独立客户端 42565388618](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565388618) 在 macOS 26 Intel 通过 29 项 Swift、Go 密封/原生前置条件及重定位，普通任务成功按精确指纹取包。
- [国区真实普通导出 42565938868](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565938868)：App ID 1530340312，6 个加密切片、164 页完整明文验证，清理后 2,061,272 字节，4 份固定数字进度快照。账号已清理，仅留 age 密文及绑定 `account_profile=cn` 的回执；ZIP、密文摘要、运行/源码/地区回执均已核验。未发送 Telegram 文件，不等于安装运行或一次真实用户国区收发。
- [外区预检 42565489090](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565489090) 在最终源码正确加载新默认运行包及固定公共资源，没有加载 Apple 凭据。
- [服务器 build-only 42565464660](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565464660) 和 [正式部署 42566050391](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566050391) 均通过 Ubuntu/Debian 13 各 480 项 Python（各跳过 1 项）、3 项 Node、Go、大容量加密、systemd 凭据和包检查。部署返回 `persistent_service_ready_verified`，保留原 SQLite、白名单、六项运行凭据和单轮询进程。
- [alpha.5 发布 42566052613](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566052613) 校验 24 份 Markdown、精确源码/指纹、产物摘要、清单与许可证后发布 3 个组件包、8 个附件。[下载 v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。

本轮发布/部署运行源码为 `48ad5b75eb61a6cc5f01ffb539f06a33055adc9a`。后续提交只补齐事实与文档，不改变运行代码或重新部署。原德国区 Secrets、安全设置及旧 CN Intel 备份未改动，没有新增电脑授权、线上测试用户或额外测试文件发送。

## 2026-11-09 中国区独立模型已恢复

用户批准的一次额外 ARM 初始化 [42562058217](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42562058217) 成功，授权数量 2 → 3。中国区 LocalSend 的 31 个加密切片、11,744 页同时通过模型恢复和独立完整明文校验；配套模型/状态/GUID/会话已核验并保存为 CN 专用 Secrets。临时批准和验证码 Secret 已删除，旧 Intel 档案继续保存在 GitHub 专用加密备份中，德国区和 alpha.4 默认服务未变。

该阶段后已完成保存模型跨运行器复用和保存状态重放，链接路由的后续进展见本页开头；该阶段国区历史尚不支持，后续接入见本页开头；没有额外发 Telegram 文件或验证安装运行。此前同日阻塞与准备章节保留为历史阶段，最新结果见 [中国区说明](CHINA-ACCOUNT.md)。

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
