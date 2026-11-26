# Managed runtime pilot (v0.2)

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


The v0.2 pilot remains a draft on 2026-11-26. The VPS remains the production controller. The [latest managed contracts](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45663099506) passed native ARM64 image builds, independent import and volume checks. The owner requires zero cost. See [the project status](PROJECT-STATUS.md) and [zero-cost constraints](ZERO-COST.md).

The Linux controller can run as a single non-root managed container without SSH or systemd. The existing systemd path remains the default. A managed container is **not** a scale-to-zero Worker: it needs continuous availability for Telegram polling, persistent private storage and enough disk for local file handling. Use a provider that permits this workload and supports the required memory, storage, and private networking. Do not use GitHub Actions as a permanent service host. Use only authorized inputs and distribution.

## Runtime prerequisites

- A CI-verified controller bundle built from the matching source commit; alpha.5 predates this mode.
- Linux ARM64 or amd64, one replica, UID/GID 10001, at least 2 GiB memory and a private volume with sufficient free space (existing delivery guard: at least 8,147,483,648 bytes). Mount at /var/lib/ipazake, owned by UID 10001, mode 0700. Use stop-before-start deployments, not rolling replicas.
- Inject the existing six credentials via the provider's private environment settings: TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID, TELEGRAM_API_ID, TELEGRAM_API_HASH, DELIVERY_AGE_IDENTITY, GH_TOKEN. Do not add them to Docker build args, files in the build context, logs or image layers.
- No public listening port is required for the controller. Local Bot API stays on loopback. Keep restart and encrypted backups at the platform level.
- The production worker and its prerequisites remain unchanged. This change does not approve using GitHub-hosted runners as permanent production hosting.

## Build and validation

The existing vps-release workflow validates the container using the exact assembled package before publishing the bundle. The PR workflow runs synthetic credential, volume and journal tests and produces validation builds of the ARM64 images. Neither workflow requires real credentials or sends files during these checks. The vps-release workflow builds its release bundles on main.

After a successful matching CI build, use the published digest to check the bundle, unpack it into a private build context containing only the public bundle, and build with deploy/managed/Dockerfile. Provider startup configuration and image registry must be reviewed separately. Never deploy an unverified branch directly.

## Migration block

TestFlight currently relies on SSH-backed session ciphertext and invitation acceptance records. Managed mode disables new TestFlight submissions and refuses journals with any prior TF tasks. No existing live bot token or production journal should be used for the pilot. This deliberately does not implement complete VPS removal for the current installation.

Before production cutover:
1. Replace TF SSH state transport with an authenticated, transactional private state service; migrate the encrypted session, acceptance-intent history and return ledger without resetting unknown outcomes.
2. Prove synthetic restart, deduplication, quota, cancellation, secret isolation and provider storage behavior; test the isolated controller with an authorized synthetic workload.
3. Establish a permitted production worker host and verify its integration. Validate local Bot API capacity and controlled migration of Telegram state. Never run two pollers with the same token.
4. Stop the old service only when idle, back up all private state, perform an atomic migration, and verify delivery and recovery before decommissioning the old VPS. Preserve a rollback copy and existing delivery identity.

Do not remove existing VPS Secrets or data, perform new Apple authorization, or start a second production bot as part of this phase.


## Phase 2: authenticated HTTPS state transport candidate

A separate managed service can run the same verified controller image with entrypoint `/usr/bin/python3 /opt/ipazake/tools/tf_state_http.py`. It needs its own persistent private volume mounted at /var/lib/ipazake, UID 10001, mode 0700, containing the migrated testflight/session.age and testflight/acceptance.sqlite files (mode 0600). A missing or malformed state ledger prevents startup. The service never installs or replaces session ciphertext remotely. No Apple or Telegram credentials are needed; inject only TF_STATE_API_TOKEN (a securely generated random URL-safe token at least 43 characters). Bind to loopback by default; a hosted platform may set TF_STATE_BIND=0.0.0.0 and TF_STATE_TRUSTED_TLS_PROXY=1 only with an authenticated HTTPS ingress path and no direct public HTTP access. Disable proxy request/response body and authorization logging, caching and retries; limit request rates at ingress.

The worker supports the explicit repository variable TF_STATE_TRANSPORT=https and two new Secrets TF_STATE_API_URL (HTTPS origin only) and TF_STATE_API_TOKEN. Default remains ssh. There is no automatic fallback or retry of acceptance claims; after ambiguous outcomes the original ledger continues to block repetition. The worker checks the ciphertext digest and length as before. The native runtime and original cryptographic checks are unchanged.

**Do not set these variables yet.** This is a synthetic contract candidate, not a migrated service. Existing session-promotion/recovery tooling still uses SSH, and the managed Telegram controller still disables TF. Migration, provider deployment, matching runtime proof, production worker hosting review, and controlled cutover remain prerequisites. Copy the existing ledger while idle using a consistent backup; never manufacture a new ledger from the ciphertext. Do not run the SSH state service and HTTPS state service against divergent live ledgers. Preserve the return ledger and the same delivery key.


## Phase 3: managed images, edge ingress and offline migration check

The managed-runtime-contracts workflow can produce two Linux amd64 images from an isolated public build context in a manual build-only run after synthetic contracts. The native ARM64 jobs produce a matching pair for pull request validation. Both images use UID/GID 10001 and fail without a private persistent volume. The artifact contains Docker image archives and checksums, not an automatic registry push or provider deployment. Verify SHA256SUMS and exact source, then publish to an approved private registry from a trusted environment. Deploy by immutable image digest. The state image uses a separate entrypoint and provides a minimal /healthz endpoint; its data operations still require the independent state token.

The earlier paid Render Blueprint proposal is withdrawn because the owner requires zero recurring and overage charges. The deployable paid example has been removed from this branch. No provider deployment is approved. See [zero-cost constraints](ZERO-COST.md).

An optional Cloudflare Worker in deploy/managed/cloudflare is an edge HTTPS relay, not a replacement for the state database, Telegram controller or large-file sender. Configure separate random EDGE_TOKEN and ORIGIN_TOKEN as Secrets (ORIGIN_TOKEN matches the state service token), and STATE_ORIGIN as the approved HTTPS origin Secret. The worker permits only four bounded POST routes, does not forward caller headers, follows no redirects, caches no results, and makes a single upstream call. The default Wrangler config has no public routes or workers.dev endpoint: configure the intended custom domain or route and ingress rules explicitly. Disable origin/proxy authorization/body logging and retries. The origin must still authenticate requests; never rely solely on the edge. The caller's TF_STATE_API_TOKEN would be EDGE_TOKEN rather than the origin token if the relay is deployed. No Cloudflare account access or deploy is attempted by CI.

Migration check: tools/managed_migration.py compares a frozen source snapshot with two independently prepared offline destination roots, verifying private file modes, SQLite quick_check, absence of database sidecars, no pending/sending task records or pending version catalog lookups in any scope, byte-identical controller DB, TF return ledger, acceptance ledger, ciphertext and persistent Telegram files. It prints only a fixed match/failure status. It does not copy data, generate secrets, or certify provider behavior. Do not run on live databases. First stop all relevant writers at an approved idle cutover, safely checkpoint and snapshot on the approved infrastructure, and preserve rollback data. Never reset or fabricate a ledger to satisfy this check; unresolved work requires explicit reconciliation. Keep the existing pilot TF gate until an end-to-end approved state migration and integration are proven.

Official provider references: https://render.com/docs/blueprint-spec and https://render.com/docs/disks ; https://developers.cloudflare.com/workers/wrangler/configuration/ . Provider configuration is a candidate, not an operational deployment.


## Phase 4: free-only control-plane pilot

See [zero-cost constraints and pilot setup](ZERO-COST.md). The independent Worker/D1 pilot does not use the HTTPS state relay or managed container. The free pilot tests and packaging run as separate jobs. The current pull request also builds and independently imports ARM64 images. The production Telegram controller continues to poll on the VPS.

### Live migration state inventory (2026-11-25)

The [encrypted backup](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45637494802) captured the controller and Telegram state, TestFlight session ciphertext, and the private return journal. The subsequent [read-only source inventory](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45638716965) confirmed those paths exist and are owner-only. The source had no `testflight/acceptance.sqlite` or SQLite sidecars at its standard location. The service was ready and had no active task at inspection time.

An absent file is consistent with the live state helper's lazy initialization, but the inventory does not establish the history of prior invite acceptances. The managed state service requires a verified acceptance ledger before startup. Preserve the backup as a partial migration snapshot and establish the ledger's provenance before migrating TestFlight. Production cutover still depends on an eligible destination and compatible replacement runtime.

### Native Linux ARM64 checks

The managed contracts run the controller, state transport, frozen-snapshot and file delivery tests on native Linux amd64 and ARM64 runners. The ARM64 delivery helper job builds and tests the same age-based executable used by the controller and publishes it with source provenance and checksums. The ARM64 image job compiles the pinned Local Bot API for ARM64 on a cache miss, then builds the controller and state images with the matching ARM64 helper. The job checks executable and container architecture, non-root imports, missing-volume rejection and the Local Bot API version. It also starts the state image twice with the same isolated volume, checks readiness and status authentication, and verifies that the synthetic session checksum survives container replacement. A separate native ARM64 runner downloads that exact artifact by ID, checks the manifest digest reported by the build job, and verifies every file before importing both images. It compares the loaded image IDs and embedded source commit with the build metadata and checks the platform and runtime UID. Use the artifact after both jobs pass. The macOS export runtime has separate architecture requirements.

### Offline controller volume preflight

With the controller stopped, mount the intended private volume and run the check from the matching CI-verified controller image. This example uses a Docker named volume and the image's default UID/GID 10001.

```sh
docker run --rm --network none \
  --mount "type=volume,source=$CONTROLLER_VOLUME,target=/var/lib/ipazake" \
  --entrypoint /usr/bin/python3 "$CONTROLLER_IMAGE" \
  /opt/ipazake/tools/managed_volume_preflight.py
```

The check requires a mounted, owner-only, writable filesystem with at least 8,147,483,648 available bytes. It checks local lock contention, SQLite WAL support and committed journal readback in a temporary directory on the volume. It removes the temporary files and does not read existing controller records or require credentials. Success prints `managed_controller_volume_ready`. The lock check covers the local mount. Keep one controller replica.

### Offline source snapshot inspection

Before preparing destination copies, a CI-verified tool can inspect an already
frozen private source snapshot on the approved migration infrastructure:

```sh
python3 tools/managed_migration.py --source "$FROZEN_SOURCE" --inspect-source
```

The report contains only the fixed schema `ipa-migration-source-v1` and three
booleans: `controller_snapshot_valid`, `state_snapshot_valid` and
`snapshot_valid`. An incomplete or invalid snapshot exits with status 2.
The tool never initializes a missing acceptance ledger, writes source data or
prints paths, identities, checksums, exceptions or database contents. The
existing three-root comparison remains available and applies the same checks.

Both modes reject unsupported or null controller task states, unfinished
Telegram update records, and acceptance databases without the expected
invitations table, invite primary key or supported states. Existing acceptance
`intent` and `outcome_unknown` rows remain valid durable blockers and must be
copied byte for byte; their age does not permit a retry. CI exercises this with
the real acceptance helper on synthetic data.

These are structural checks of offline data. A valid schema, including an
empty table, cannot establish the provenance or completeness of historical
acceptances. The missing production ledger recorded on November 25 still
requires reconciliation against verified history; never create an empty
replacement to obtain a passing report. A passing source report also does not
establish a hosting destination, TestFlight compatibility or permission to cut
over. Do not execute the tool on live state or in the editing workspace.

### Verified historical recovery candidate (2026-11-26)

The [source audit](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45811165425)
confirmed the original session ciphertext, one completed TF task, the preserved
private return ledger and absence of an acceptance database in the inspected
locations. The [historical recovery build](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45812495918)
then checked the original encrypted intent, failed acceptance and successful
read-only membership receipts, and produced an encrypted one-record recovery
candidate with a provenance table and successful decryption readback.

This is evidence-based staging, not installation of a replacement ledger.
The candidate must not overwrite existing or newly created records. Its receipt
requires a fresh source check before any installation; preserve the full source
and rollback data at an idle, consistent cutover. It does not enable TF in the
managed pilot, provision a production host or change the VPS. See
[the detailed evidence and current hosting decision](MIGRATION-READINESS.md).
