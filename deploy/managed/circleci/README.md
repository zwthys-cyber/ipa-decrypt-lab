# CircleCI on-demand migration candidate

The owner uses this project personally and does not require a 24-hour worker. Production remains on the VPS until a verified single-controller handover. See [current status](../../../docs/PROJECT-STATUS.md) for completed and pending evidence.

## Public native producers

`[circleci-runtime-build]` or pipeline parameter `build_native_runtime=true` requests the full public producer. `[circleci-tf-runtime-build]` requests only the TestFlight producer for isolated diagnosis. Ordinary pushes run only the existing owned sample validation.

The macOS 26 / Xcode 26.5 / M4 Pro Medium producer builds pinned public sources without account credentials:
- `base`: default App Store Swift client and Go helpers.
- `cn`: separate CN session/catalog client using those same Go helpers.
- `testflight`: independent SDK client and its native libraries.

Artifacts use `public-arm64-native-runtime/<variant>/native-runtime.tar.gz` and `build-receipt.json`. Schema v2 requires the exact variant, source fingerprint, successful CircleCI source/workflow/job, ARM64 platform, toolchain and TF dependency versions. It rejects unexpected members, escaping paths, links, duplicate entries and digest changes. Every variant must pass relocation with its original build directory hidden. Failed jobs' partial artifacts are ineligible for production.

A future consumer must authenticate the successful job through CircleCI and compare the expected source contract and current runner ABI before executing any binary. The manifest cannot authenticate itself. Production fetching is not implemented yet. Existing GitHub Intel runtime schemas and guards are preserved; never spoof `GITHUB_ACTIONS=true` on CircleCI.

## API and job identity

The owner has already configured Actions secret `CIRCLECI_API_TOKEN`. Do not ask them to send it in chat or duplicate setup. The fixed-repository workflow `.github/workflows/circleci-connection-probe.yml` uses it only within GitHub, sends one synthetic API v3 run, stores the nonsecret acknowledged ID and polls that same run. Transient read 404s do not cause another POST. Only nonsecret source/request parameters reach CircleCI.

`oidc.mjs` verifies CircleCI V3 RS256 signatures against the fixed issuer's public JWKS, audience/time, owner, project, checkout and config sources/refs, definition/run/job and SSH-rerun flag. Expected run/job IDs must come from the trusted dispatch record and CircleCI metadata, never directly from the caller's JWT. Signed identity is only part of future authorization; Worker routes and credential release are not implemented by this probe. No raw JWT is stored or logged.

## Durable dispatch candidate

`dispatch.mjs` is **synthetic-only** and not wired into the bot. Apply its migration only to an isolated pilot D1 after the existing pilot jobs/link tables; it is not a migration for the production VPS journal. Never clear existing intents to retry a job.

The D1 intent precedes the sole external POST. Owner/job/source/request binding, unique jobs and a global active-run guard prevent duplicate/concurrent dispatch. Intent acknowledgement loss sends nothing; uncertain trigger outcomes stay blocked across restart without expiry. Successful API acknowledgement binds the run ID. Only source/project/definition-bound successful readback releases capacity; GET readback never triggers another run. Network operations have a 15-second bound.

`dispatch.integration.mjs` exercises real local workerd D1 through Miniflare with synthetic HTTP, including concurrent claims, restart, lost acknowledgements and timeout. It does not prove deployed cloud execution. All tests run in CI only.

## Remaining production work

Finish TF ARM validation, authenticated runtime consumption, production entry points and state/credential handover, durable TF acceptance/cancellation/unknown-result records, private Drive upload receipts and limits, account credit bounds and single-poller/webhook cutover. Preserve App Store default/CN, available historical versions and owner-only TF. No new enrollment/security upgrade, historical invitation replay or old file resend is part of public builds.

References: [CircleCI API](https://circleci.com/docs/api/v3), [OIDC](https://circleci.com/docs/guides/permissions-authentication/openid-connect-tokens/).

## CircleCI 接入与持久化调度候选（2026-11-26，最新）

用户已配置 `CIRCLECI_API_TOKEN`，无需再次索要。令牌在 GitHub 密钥步骤内认证通过，账号与既有触发者一致，可读取固定项目/定义并提交任务。使用 API v3 创建 run；创建后查询接口可能短暂返回 404，只能重读同一 ID，绝不因此重复 POST。[完整调度与真实 OIDC 验证 45820517834](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45820517834)通过，源码 `cd3964da45324b59bf1f8d56a5a02a1c9bf5d649`。

真实 CircleCI run `a9e78112-ddff-41b3-aeb3-c1bd9a938c0f`、[job 33](https://app.circleci.com/workflow/91165577-39cf-4158-a323-809d36e54042/job/23f40104-d13f-4ef7-bd11-ad3707d8ad9a)通过 CircleCI OIDC V3 签名、公钥、issuer/audience、时效、账号、项目、配置/检出仓库及分支、definition/run/job 和非 SSH 重跑检查。公钥地址来自该 issuer 的 discovery，为 `/.well-known/jwks-pub.json`。不保存或输出原始 JWT；当前任务无需另建 context 即可取得 V3 token。11 项 Python 调度测试和 7 项合成签名测试通过。此证明不等于 Worker 已接入这些身份检查或已获得生产凭据。

新增 `deploy/managed/circleci/dispatch.mjs` 和独立迁移 `migrations/0001_dispatch.sql`，目前仅供合成任务，尚未接入实际机器人或应用到远程 D1。提交前持久化 intent，绑定 owner/job/request/source/run；全局串行，已有链接/取消/重复任务拒绝提交，未知结果不超时重置。POST/GET 限时 15 秒。只有来源和成功状态核对一致的 readback 才能释放下一任务。[D1 验证 45822528880](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45822528880)在实际本地 workerd/D1 上通过 8 个场景，覆盖并发、重启、意图或回执丢失、超时、防重提及错误 readback；CircleCI 传输为合成替身，不是真实云端 D1→CircleCI 提交证据。

公共运行包升级至 `circleci-native-runtime-v2`，区分 base/cn/testflight，并绑定源码、ARM64、工具链、TF 依赖版本和逐文件摘要。源码 `230af2f3cc169652b8c09e5b034526c1e5f1d2ff` 的 job 35 已通过 base 的 21 项 Swift 和 CN 的 29 项 Swift 测试、两包打包及隐藏原目录后的 CLI 运行；整个 job 因后续 TF Homebrew 安装失败而失败，这些产物不能当作成功生产包获取。13 项包校验测试通过。

TF 已拆为可独立验证的 `build-public-tf-runtime.sh`。当前待验证修复源码 `2df098277cb266a5c5456c3fdd6b2e65cff7d38b`：先显式更新镜像自带 Homebrew，并在安装后处理失败时输出有限的包管理器诊断。此前 job 38 在 ca-certificates post-install 再次失败；不能声称 TF ARM 编译或三包总体构建已通过。

剩余：TF 原生构建及三包成功来源证明、任务端受信运行包获取、凭据与加密会话交接、TF 接受/取消/未知结果的完整持久化、私有 Drive 上传与回执、费用上限以及单一机器人入口切换。原 VPS 继续承担生产；没有切换 webhook、执行新的 Apple 操作或重复历史邀请/文件发送。所有编译、项目测试和模拟 D1 执行均只在 GitHub/CircleCI，当前服务器仅做 GitHub/API 协调。

