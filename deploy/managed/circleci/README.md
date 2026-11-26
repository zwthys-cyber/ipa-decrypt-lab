# CircleCI on-demand migration candidate

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

