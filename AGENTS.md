# Project constraints

- All project compilation, automated tests and build validation MUST run on GitHub-hosted Actions runners only. The VPS may run CI-verified finished services (2026-11-04).
- Never build, install build dependencies or run test suites on the VPS or this workspace. Install only necessary system runtime packages and the CI-verified deployment bundle on the authorized VPS. No local project execution.
- Edit source through GitHub APIs. Do not create local project checkouts or build caches.
- Do not use a personal iPhone or TrollStore installation as infrastructure.
- No third-party decryption services unless the scope is explicitly changed.
- Never commit or upload Apple credentials, account keys, Telegram tokens, provisioning profiles or third-party IPA files to this public repository or public Actions artifacts/logs.
- Synthetic fixtures are the default. CI success proves compilation and fixture behavior, not successful App Store decryption.
- Keep research results candid: missing credentials/platform support must fail explicitly; never clear cryptid to pretend decryption succeeded.
- Pin action revisions; use read-only workflow permissions, bounded timeouts and short artifact retention. The owner-authorized Telegram dispatcher may use actions:write solely to submit/cancel the fixed private-delivery workflow.
- GitHub Actions is a bounded build/research environment, not permanent production hosting.

- The optional two-factor security upgrade is declined. Never enable or accept that upgrade automatically.
- Do not infer an enabled two-factor setting or a definite verification challenge from MZFinance.BadLogin.Configurator_message. Treat it as ambiguous until stronger response evidence is available.

- Telegram integration resumed on 2026-11-04. Implement bounded GitHub-hosted bot sessions and verified private delivery; the later explicit authorization permits finished-service execution on the VPS, but never permanent Actions hosting.

## Verified research milestone (2026-11-04)

- GitHub-only initial model recovery is now verified for App ID 6599842047. Successful runs: bootstrap 41846142942, saved-model reuse 41846974302, saved-state replay 41847775765. All verified 62 encrypted slices and 12,524 pages. See docs/PROJECT-STATUS.md and the current-status section of OFFLINE-BACKEND.md.
- FAIRPLAY_MODEL_B64 and FAIRPLAY_STATE_B64 already exist as repository Secrets. Reuse the model with native-store.yml / offline, or rederive with model-bootstrap.yml / checkpoint-replay. Do not repeat initial enrollment merely to repeat a verification.
- The last observed computer count was 4 of 5. The approved all-computer deauthorization was performed once (5 -> 0); that approval is not reusable for another account-wide operation.
- Raw private material stays on the GitHub runner. Only ciphertext sealed to the fixed repository public key may be relayed for Secret storage; it is not a public usable model or a decrypted IPA artifact. Workflow output does not itself write or replace repository Secrets.
- The recovered model and full plaintext checks do not establish installation/runtime, other-app/account compatibility, actual Linux decryption, or a deployed paid service. No downloadable IPA was retained.
- Telegram job submission and file delivery must be restricted to the configured owner in a private chat. Identity bootstrap may reply only with the requesting private sender's own numeric ID; it cannot submit tasks or access Apple Secrets.
- Verified IPA delivery may use authenticated age encryption for short-lived public ciphertext artifacts, followed by owner-only private transmission. Never publish plaintext IPA or raw decryption reports. Delivery keys remain in Secrets; cleanup plaintext on all exit paths.
- Read the current-status documents before treating historical failed experiments as present blockers.

## Verified private delivery milestone (2026-11-04)

- Private export 41856194867 verified all 62 slices / 12,524 pages, removed Store account data, and retained only age ciphertext and a sanitized receipt for one day. Plaintext IPA size: 92,118,013 bytes.
- Telegram delivery 41864719056 authenticated the pinned official local Bot API server, privately decrypted the ciphertext on GitHub Linux, independently checked digest and archive structure, and obtained a private-owner sendDocument acknowledgement for all 92,118,013 bytes. This is private delivery evidence, not proof of actual Linux FairPlay decryption or installation/runtime.
- DELIVERY_AGE_IDENTITY and Telegram credentials are configured as Secrets. Do not regenerate/replace the delivery identity merely to retry an existing artifact. See docs/TELEGRAM.md for current daemon commands and limits.
- Queue/owner/deduplication behavior has synthetic coverage. Record actual Telegram-request-to-workflow runs separately before claiming that live path verified.

## Sanitized progress reporting

- Live Telegram progress is enabled. private-delivery.yml may use checks:write solely to publish the fixed delivery-progress check for its own request/run and source commit. No account data, raw logs, file paths or secrets may enter progress payloads.
- The Telegram controller may read those checks with checks:read and edit its own owner-private progress message. Report actual stages and elapsed time; never invent byte percentages. Completion 100% requires the file-send acknowledgement. Progress reporting failures must not repeat a job or file upload.
- progress-contracts.yml may use checks:write only for its own synthetic progress-channel probe on the current source commit; it receives no Apple or Telegram credentials.

## Delivery readiness during delayed workflow finalization

- A trusted worker's request/run-bound artifact_ready check plus a finalized, non-expired encrypted artifact with a SHA-256 digest may release private delivery while the overall workflow status still lags. A completed failed/cancelled run does not qualify for this early path.
- The controller must still verify artifact archive digest (when present), recipient-encrypted payload, receipt binding, plaintext digest and IPA structure before sending; the progress card reaches 100% only after Telegram acknowledges the file.
- progress-contracts.yml may read Actions artifacts metadata and download only the fixed encrypted verification sample to test readiness/archive integrity. It receives no delivery identity or Apple/Telegram credentials and must not send files or expose plaintext.

## macOS 26 and queue upgrade (2026-11-04)

- macOS 26 is the default platform. Default private delivery is now macos-26-intel, fallback macos-15-intel; keep the explicit GitHub-hosted allowlist. No self-hosted or paid larger runner is authorized by this change.
- 26 Intel preflight 41872589701 and real model/download/decryption sample 41876940427 verified the path. The latter verified 6 slices / 164 pages for App ID 1530340312 and reused the validated Swift build cache. It does not establish installation/runtime.
- The original request was recovered on 15 Intel in 41869909475, delivered via Telegram session 41870902876 (2,035,796 bytes), and acknowledged by the user. This manual recovery is not an automatic-failover live test.
- Queued jobs may attempt one alternate pool only after safe termination/no-execution proof; never blindly retry an assigned/executed job, a user cancellation, or an ambiguous dispatch. Keep at most two automatic logical runs and protect artifacts/Secrets.
- Use 4 Swift jobs on Intel, 2 on ARM; isolate OS/architecture/Xcode/source caches. Verified exact cache reuse may skip repeated native compilation/tests; Python/Go checks remain required. ARM 26 preflight did not obtain capacity; do not claim it verified.
- Early readiness/archive integrity probe 41879112828 passed 305 Python tests (1 environment skip) and read back the real encrypted sample without plaintext or Telegram transmission.

- Latest regression/probe run 41882955218 passed 308 Python tests (1 environment skip) and real ciphertext readiness/archive-digest verification. Prefer verified worker/native-check stages over delayed queued metadata; before queue cancellation cross-check that the bound native Check is actually queued. New Telegram sessions replace old bounded sessions, not IPA worker workflows.

## Persistent recovery
- Use private SQLite recovery records. Record intent before dispatch or transmission; unknown file-send outcomes must not be automatically repeated after restart.
- The old Checks journal and bounded polling entry points have been removed. Preserve owner isolation and recovery failure tests against SQLite.

## Persistent VPS deployment
- The persistent controller runs on a Debian 13 x86_64 VPS. Keep the server address and SSH credentials in deployment Secrets, not public source.
- GitHub builds/tests the public release, including Debian 13 compatibility. The VPS installs only runtime packages and verified artifacts. SSH installation, service startup and operational health inspection are authorized; no tests or compilers on the VPS.
- A dedicated VPS_GH_TOKEN limited to this repository supplies Actions write and Contents read. Never copy the maintainer's broad workstation OAuth credential onto the server.
- The daemon uses a private SQLite recovery log, persistent Telegram state, a single-controller lock, systemd restart and a non-root service account. Apple credentials/model stay in GitHub. Only authenticated delivery-envelope decryption may run on the VPS.
- Legacy bounded polling and identity bootstrap entry points are removed. Reject overlapping historical poller runs during deployment. Owner-only access and billing-off remain defaults.
- Runtime service credentials travel only via pinned SSH to a root-private systemd credential file, never public artifacts/logs. Deploy only after CI passes; retain the previous release for rollback.

Checks 不是 fine-grained PAT 的必填权限。遇到 Checks 权限拒绝时，服务器改用 Actions 任务/步骤状态；不再基于缺失的 Checks 证据提前交付或取消排队任务，等待正常完成后校验交付。

- Persistent VPS deployment is verified by run 41899775076 at code commit 06bcf81fab70e597c823d1096877d3d6df4c01bd (347 Python tests, 1 skip, on both Ubuntu and Debian 13; Go and actual systemd credential mount tests). The owner-only daemon is enabled and healthy, and Telegram startup notification was acknowledged. Do not describe a fresh post-migration IPA task as verified without separate evidence. Legacy polling source has been removed; never start another poller alongside the VPS.

- Owner-authorized historical version browsing may dispatch the fixed version-catalog.yml workflow with Actions write. Only sanitized app version IDs, display versions and dates may enter its short-lived public metadata artifact. Apple credentials stay on GitHub, no IPA is downloaded by the catalog workflow. Callback selection must pass owner/private-chat, message binding, expiry, durable one-use and ordinary task quota checks.


## Precompiled runtime (2026-11-05)
- Compilation/tests run separately from ordinary delivery and catalog tasks. native-runtime-build.yml builds/tests both supported Intel platforms and publishes only public-source runtime binaries/resources with per-file SHA-256 and a tools/tests/build-workflow fingerprint. No Apple secrets or downloaded Apple assets enter this producer.
- Ordinary private-delivery.yml and version-catalog.yml load only exact-source, exact-platform packages from successful main-branch producer runs. They do not install Go, compile native code, restore the Swift build tree, or rerun suites. This supersedes the earlier per-task Go/Python test requirement; those tests remain required in the producer.
- Runtime source changes require a successful new producer run before ordinary tasks can use that source. Missing/expired packages fail before Apple secrets; never silently use a stale package. Public runtime artifacts expire after 30 days; the weekly producer renews them. Account/IPA artifact retention remains one day.
- Producer 41946086966 passed on macOS 26 Intel and macOS 15 Intel; fresh-runner verification 41947134774 passed on both. This proves package portability, not a new real export or installation/runtime test.


## Exact-platform runtime recovery (2026-11-08)
- The producer's default push/scheduled path still builds and tests both supported Intel pools. A manual dispatch may select one supported pool for bounded recovery; that run must pass the same full checks, provenance/fingerprint verification and relocation checks before its artifact is used.
- A successful single-platform producer validates only that exact platform. Never use its artifact for another OS or claim the other pool passed. Consumers still require a successful main-branch producer, exact source fingerprint and exact platform.
- Login/download recovery is verified by private export 42439908718 attempt 2 for X (333903271): 32 encrypted images, 86,704 pages, 271,261,630 plaintext bytes; only age ciphertext was retained for one day. This does not verify installation/runtime or a new Telegram send.


## Public release and documentation maintenance (2026-11-08)
- Current public package version is v0.1.0-alpha.2. Replacing the old public release removes its downloadable attachments; preserve source tags and historical research unless the owner separately requests their deletion.
- publish-release.yml takes explicit vps_run and native_run producer IDs. The VPS producer must be successful build-only at the release source commit. Native packages must come from a successful main producer matching the exact current fingerprint and both published platforms.
- Release artifacts may contain only project runtimes, provenance, checksums, documentation and license notices; never attach application IPA/ciphertext, account/model material or service credentials. Publishing does not deploy/restart the VPS.
- README, operational docs and historical prefaces point to docs/DOCUMENTATION.md and docs/PROJECT-STATUS.md. Dated research records retain their original scope; current recovery evidence supersedes historical login blockers and TG pauses.


## Measured progress and complete elapsed time
- Main adds explicitly labelled workflow-step completion percentages; these are not time estimates. Only acknowledged Telegram file delivery can mark overall completion 100%.
- Download byte percentages must come from bounded native integer counters. Unknown-length stages and Telegram server uploads have no invented byte percentages or remaining-time predictions. Stale measured values must be labelled as last observed.
- The worker may retain at most 80 tiny, validated request/run/source-bound numeric progress snapshots for one day. This Actions-readable feed does not require expanding the VPS token's Checks permissions. Extra/unstructured fields and private account material must be rejected before upload.
- Progress uploads receive only the job runtime artifact credentials and fixed public metadata, never Apple/model/Telegram/delivery secrets. Feed failures cannot retry the export or send a document.
- Keep timers active during blocking delivery, stop them on service shutdown, and persist card identity plus original task creation time in the owner-scoped private journal. Clock refreshes must not write recovery state or dispatch/transmit files.
- progress-contracts.yml may publish and read the current run's account-free synthetic numeric snapshots. Existing fixed encrypted readiness samples are optional because short-lived artifacts expire; no private key or Telegram credentials may enter that probe.
- Runtime fingerprints include the progress JavaScript action source/manifest so a changed wrapper requires a successful matching producer before private tasks use it.

## Progress and Node 24 verification (2026-11-08)
- Progress controller deployment 42443436341 at d59f3eb8ebd6f8ce0c98bfb0909817bc4345ac22 passed 449 Python checks on Ubuntu/Debian 13 plus Node/Go/systemd checks and VPS ready health. Preserve measured updates even when a heartbeat recently edited the card; throttle rendering, not metric ingestion.
- Latest Node 24 action source is 3c695191364daeb13951e77cd65327c92a1409f0. Native producer 42443706492 passed both supported Intel platforms (449 Python checks, 2 Node checks, 21 Swift checks plus Go/relocation); progress probe 42443707998 and VPS build-only 42443709848 passed. Do not redeploy merely to change GitHub-only dependency pins.
- Real X export 42444399936 succeeded with 9 numeric snapshots, including measured byte progress; 32 images / 86,704 pages and 271,261,630 plaintext bytes verified. No new Telegram file was sent, plaintext remained private, installation/runtime remains unverified.
- Official Node 24 action pins are checkout v7.0.1, setup-go v7.0.0, cache v6.1.0 and upload-artifact v7.0.2. The direct uploader must explicitly supply archive=true and all required boolean inputs, and create isolated output files before launch. Keep it synchronized with the workflow pin and producer fingerprint.

## Verified export speedup (2026-11-08)
- Source 2f8494980894c857e89db13c5c3cb1a4d34c92b7 uses bounded Go zip.Writer.Copy to remove account members without recompressing retained entries. Raw copying does NOT verify CRC; preserve mandatory complete verify_output, plaintext proof, inventory/version and digest checks before encryption/publication. Never fall back to a weaker verification path after helper failure.
- The scrub command is GitHub-only; VPS remains decrypt-only. Output is a private temporary file, bounded and atomically linked without overwrite. No VPS deployment is required for this worker-only change.
- Producer 42445031389 passed both Intel platforms (451 Python checks with 2 skips each, 2 Node checks, 21 Swift checks plus Go/relocation). Account-free synthetic benchmark 42445037747 passed (0.985567 -> 0.027210 seconds on the fixture); never present the per-step fixture ratio as whole-task speedup.
- Real X export 42445425200 verified 32 images / 86,704 pages and 279,312,733 plaintext bytes. Compared with the user task 42444653313, verifying fell 40.45 -> 13.80 seconds and the native job 128 -> 103 seconds. The resulting ZIP is about 3% larger because upstream compressed bytes are retained. This is one backend comparison, not a new end-to-end Telegram timing or installation/runtime test. No extra Telegram document was sent.

## Owner-authorized multi-user whitelist (2026-11-09)
- The user explicitly authorized continuing with a verified new release followed by multi-user allowlisting. This supersedes earlier owner-only feature restrictions only for administrator-authorized private users. Keep billing disabled and reject public/group use. The configured TELEGRAM_OWNER_ID remains the sole administrator.
- Only the administrator may grant/revoke private numeric user IDs or change per-user limits. Default guest quota is 3/day; retain the existing service-wide daily cap and global serialized admission. Store ACLs privately, never in repository/config artifacts.
- Every export lookup, retry, cancellation and delivery must be bound to the user's private ledger; a known task ID is not sufficient authorization. Both guests and administrator use their own task namespace. Preserve browser/callback, progress-message and recovery isolation.
- Preserve one polling process and one global update offset. Tenant task/metadata scopes retain the existing journal hash so administrator data survives upgrades. Revoking stops automatic delivery; track uncertain cancellations privately and hold new workflow admission until terminal status is confirmed.
- The user authorized publishing current progress/speed packages first (alpha.3), then completing and publishing/deploying the whitelist version. Preserve historical releases and source tags. Never populate the live whitelist with synthetic users or send test IPA files to third parties.

## Verified whitelist deployment and releases (2026-11-09)
- alpha.3 was published by 42541919654 at 0f8dc52e52ee92dd56e15cfb474e08f428bc966f, then alpha.4 by 42543237386 at b92dc1575123e1b7eab2283b62d355539fc71e4d. Each has 3 runtime packages and 8 verified public attachments; alpha.2/alpha.3 remain historical snapshots. Current public version is alpha.4.
- Whitelist source 12ca5e2f3f65e7b2adbd42cb5dabbea6efdae874 passed producer 42542616831 on both supported Intel pools: 466 Python checks (2 skips), 2 Node checks, 21 Swift checks plus Go/relocation per pool. Default-pool account-free runtime fetch preflight 42543135884 passed on final release source.
- VPS build-only 42543061196 and actual deployment 42543133206 at b92dc1575123e1b7eab2283b62d355539fc71e4d passed Ubuntu/Debian 13 (466 Python checks, 1 skip each), Node/Go/systemd checks and actual ready health. One poller, legacy administrator namespace and private SQLite were preserved. No extra live users or test Telegram documents were added.
- Only the configured administrator may /allow, /deny, /users. Default guest quota is 3/day, existing service cap remains 20/day unless operator-configured; all scopes share admission and query budget. A known request ID never authorizes export access. Keep administrator and guest ordinary file access scoped alike.
- Revocation persists ACL, cancelled pending tasks, closed catalog tracking and retired work atomically. Normal cancellation also persists retired work with cancelled export/catalog state. Keep terminal-confirmation drain and cancelled-state auto-delivery guard; unknown outcomes cannot release capacity by guesswork.
- Initial alpha.4 boundary evidence was synthetic with real temporary SQLite. The separately recorded real guest case below adds live ownership/progress/delivery evidence for that case; cross-user denial and fault coverage remain primarily synthetic. Actual recipient IDs/ACLs stay private and require an explicit administrator grant, never populate from test fixtures.

## Real ordinary-user delivery evidence (2026-11-09)
- An explicitly user-provided target was already an authorized ordinary guest (not administrator), quota 3/day. Do not place the actual numeric ID in this public repository or workflow inputs. No grant, quota change, duplicate dispatch or Telegram send was performed by the inspection.
- Real worker 42543990293 for App ID 544007664 passed: 8 images, 50,780 pages, 147,146,888 plaintext bytes, 7 progress snapshots; only ciphertext retained. Read-only inspections 42544362020 and 42544535030 at verified VPS source b92dc1575123e1b7eab2283b62d355539fc71e4d confirmed recipient-scoped delivered, separation from administrator records, progress done, frozen completion time and privately saved message identity. Service remained ready.
- private-access-inspection.yml and .github/ops are operational readers, not deployment/runtime components. Five synthetic tests run on GitHub before pinned-SSH read-only operational inspection; never run tests/builds on VPS. Do not start another Telegram poller or send documents to simulate users.
- Target request is passed through an expiring temporary Secret and nonce-bound payload, never public parameters/source. Output contains only reviewed states/booleans, no real IDs, raw rows, message contents or credentials. Temporary runner/remote files and the temporary Secret were removed after both completed inspections.
- This is a single real ordinary-user request-to-delivery case, not a live attempt at every denial/recovery scenario and not an installation/runtime test.


## Isolated China-account onboarding (2026-11-09)
- The user authorized adding a separate China-region account with normal live verification, while leaving the German account unchanged. This does not authorize enabling the original account's optional security upgrade, account-wide deauthorization, or reuse of its model for an unproven account.
- Live verification must keep one Authenticator/process alive. Never prefill an expiring code into a cold replacement login. Relay 42547699795 and authentication 42547602116 succeeded with real CN storefront 143465; the independent session Secret was saved and the temporary code Secret deleted.
- Relay inputs contain only public request/run identifiers. Codes travel through a temporary Secret and source/run/expiry-bound age ciphertext. Public uploader subprocesses must not inherit Apple credentials, codes, GitHub tokens or delivery identities. Raw native authentication output stays private.
- CN session plaintext stays on GitHub runners. Only repository-public-key sealed ciphertext for APPLE_CN_SESSION_B64 may leave the authentication process for verified Secret storage; never send an Apple session to the VPS. Verify country, trusted source, successful run, archive digest and Secret public key before storing. Original Secrets/default runtime remain unchanged.
- A saved token alone failed at the fresh runner's Store proof stage. The isolated resume-cn command performs one normal cookie-bearing authentication, without an automatic OTP prompt or retry. Producer 42548393225 passed 26 Swift tests, Go sealer checks and relocation.
- Real fresh-runner trial 42548840372 refreshed cookies without another verification code and downloaded the CN free sample 1530340312 (2,500,837 bytes), validated bundle identity and cleaned the sample/cache. The refreshed sealed CN session was stored. This is not decryption, installation/runtime or Telegram delivery evidence, and does not guarantee permanent OTP-free reuse.
- Latest account-free contracts cover 29 Python and 2 Node cases. The Python authorization-count query, including the authenticated service pod, still returned HTTP 500 (42549102362); do not infer invalid credentials or a failed download from that endpoint alone. A native proof-bound read-only query is being validated separately.
- Do not start CN model initialization without the required observed computer-count prerequisite. No CN model enrollment/deauthorization has occurred. CN independent model, decryption, history and bot routing remain unverified; see docs/CHINA-ACCOUNT.md. All compilation/tests stay on GitHub-hosted runners; no VPS restart or new release is required for these isolated operations.
