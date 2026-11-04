# Project constraints

- All project compilation, automated tests and build validation MUST run on GitHub-hosted Actions runners only. The user subsequently authorized a VPS to run CI-verified finished services (2026-11-04).
- Never build, install build dependencies or run test suites on the VPS or this workspace. Install only necessary system runtime packages and the CI-verified deployment bundle on the authorized VPS. No local project execution.
- Edit source through GitHub APIs. Do not create local project checkouts or build caches.
- Do not use the user's personal iPhone or TrollStore installation as infrastructure.
- No third-party decryption services unless the user changes scope explicitly.
- Never commit or upload Apple credentials, account keys, Telegram tokens, provisioning profiles or third-party IPA files to this public repository or public Actions artifacts/logs.
- Synthetic fixtures are the default. CI success proves compilation and fixture behavior, not successful App Store decryption.
- Keep research results candid: missing credentials/platform support must fail explicitly; never clear cryptid to pretend decryption succeeded.
- Pin action revisions; use read-only workflow permissions, bounded timeouts and short artifact retention. The owner-authorized Telegram dispatcher may use actions:write solely to submit/cancel the fixed private-delivery workflow.
- GitHub Actions is a bounded build/research environment, not permanent production hosting.

- The account owner declines the optional two-factor security upgrade. Never enable or accept that upgrade automatically.
- Do not infer an enabled two-factor setting or a definite verification challenge from MZFinance.BadLogin.Configurator_message. Treat it as ambiguous until stronger response evidence is available.

- The user explicitly resumed Telegram integration on 2026-11-04. Implement bounded GitHub-hosted bot sessions and verified private delivery; the later explicit authorization permits finished-service execution on the VPS, but never permanent Actions hosting.

## Verified research milestone (2026-11-04)

- GitHub-only initial model recovery is now verified for App ID 6599842047. Successful runs: bootstrap 41846142942, saved-model reuse 41846974302, saved-state replay 41847775765. All verified 62 encrypted slices and 12,524 pages. See docs/PROJECT-STATUS.md and the current-status section of OFFLINE-BACKEND.md.
- FAIRPLAY_MODEL_B64 and FAIRPLAY_STATE_B64 already exist as repository Secrets. Reuse the model with native-store.yml / offline, or rederive with model-bootstrap.yml / checkpoint-replay. Do not repeat initial enrollment merely to repeat a verification.
- The last observed computer count was 4 of 5. The user-approved all-computer deauthorization was performed once (5 -> 0); that approval is not reusable for another account-wide operation.
- Raw private material stays on the GitHub runner. Only ciphertext sealed to the fixed repository public key may be relayed for Secret storage; it is not a public usable model or a decrypted IPA artifact. Workflow output does not itself write or replace repository Secrets.
- The recovered model and full plaintext checks do not establish installation/runtime, other-app/account compatibility, actual Linux decryption, or a deployed paid service. No downloadable IPA was retained.
- Telegram job submission and file delivery must be restricted to the configured owner in a private chat. Identity bootstrap may reply only with the requesting private sender's own numeric ID; it cannot submit tasks or access Apple Secrets.
- Verified IPA delivery may use authenticated age encryption for short-lived public ciphertext artifacts, followed by owner-only private transmission. Never publish plaintext IPA or raw decryption reports. Delivery keys remain in Secrets; cleanup plaintext on all exit paths.
- Read the current-status documents before treating historical failed experiments as present blockers.

## Verified private delivery milestone (2026-11-04)

- Private export 41856194867 verified all 62 slices / 12,524 pages, removed Store account data, and retained only age ciphertext and a sanitized receipt for one day. Plaintext IPA size: 92,118,013 bytes.
- Telegram delivery 41864719056 authenticated the pinned official local Bot API server, privately decrypted the ciphertext on GitHub Linux, independently checked digest and archive structure, and obtained a private-owner sendDocument acknowledgement for all 92,118,013 bytes. This is private delivery evidence, not proof of actual Linux FairPlay decryption or installation/runtime.
- DELIVERY_AGE_IDENTITY and Telegram credentials are configured as Secrets. Do not regenerate/replace the delivery identity merely to retry an existing artifact. See docs/TELEGRAM.md for bounded session commands and limits.
- Queue/owner/deduplication behavior has synthetic coverage. Record actual Telegram-request-to-workflow runs separately before claiming that live path verified.

## Sanitized progress reporting

- The user requested live Telegram progress. private-delivery.yml may use checks:write solely to publish the fixed delivery-progress check for its own request/run and source commit. No account data, raw logs, file paths or secrets may enter progress payloads.
- The Telegram controller may read those checks with checks:read and edit its own owner-private progress message. Report actual stages and elapsed time; never invent byte percentages. Completion 100% requires the file-send acknowledgement. Progress reporting failures must not repeat a job or file upload.
- progress-contracts.yml may use checks:write only for its own synthetic progress-channel probe on the current source commit; it receives no Apple or Telegram credentials.

## Delivery readiness during delayed workflow finalization

- A trusted worker's request/run-bound artifact_ready check plus a finalized, non-expired encrypted artifact with a SHA-256 digest may release private delivery while the overall workflow status still lags. A completed failed/cancelled run does not qualify for this early path.
- The controller must still verify artifact archive digest (when present), recipient-encrypted payload, receipt binding, plaintext digest and IPA structure before sending; the progress card reaches 100% only after Telegram acknowledges the file.
- progress-contracts.yml may read Actions artifacts metadata and download only the fixed encrypted verification sample to test readiness/archive integrity. It receives no delivery identity or Apple/Telegram credentials and must not send files or expose plaintext.

## macOS 26 and queue upgrade (2026-11-04)

- The user requested macOS 26. Default private delivery is now macos-26-intel, fallback macos-15-intel; keep the explicit GitHub-hosted allowlist. No self-hosted or paid larger runner is authorized by this change.
- 26 Intel preflight 41872589701 and real model/download/decryption sample 41876940427 verified the path. The latter verified 6 slices / 164 pages for App ID 1530340312 and reused the validated Swift build cache. It does not establish installation/runtime.
- The user's original request was recovered on 15 Intel in 41869909475, delivered via Telegram session 41870902876 (2,035,796 bytes), and acknowledged by the user. This manual recovery is not an automatic-failover live test.
- Queued jobs may attempt one alternate pool only after safe termination/no-execution proof; never blindly retry an assigned/executed job, a user cancellation, or an ambiguous dispatch. Keep at most two automatic logical runs and protect artifacts/Secrets.
- Use 4 Swift jobs on Intel, 2 on ARM; isolate OS/architecture/Xcode/source caches. Verified exact cache reuse may skip repeated native compilation/tests; Python/Go checks remain required. ARM 26 preflight did not obtain capacity; do not claim it verified.
- Early readiness/archive integrity probe 41879112828 passed 305 Python tests (1 environment skip) and read back the real encrypted sample without plaintext or Telegram transmission.

- Latest regression/probe run 41882955218 passed 308 Python tests (1 environment skip) and real ciphertext readiness/archive-digest verification. Prefer verified worker/native-check stages over delayed queued metadata; before queue cancellation cross-check that the bound native Check is actually queued. New Telegram sessions replace old bounded sessions, not IPA worker workflows.

## Bounded cross-session recovery
- telegram-session.yml may use checks:write for sanitized, HMAC-authenticated recovery records anchored to commit 482c1fccde988a4ca198251e32935374e83578f1. Never publish raw owner IDs, message IDs, update IDs, tokens, account data or file contents.
- A journal write and readback must precede dispatch or file transmission. Unknown file-send outcomes must not be automatically repeated after restart. Explicit owner /get remains a manual retrieval action.
- Keep the existing single-session concurrency group and owner-only gate. This bounded Checks log is not a production database or distributed lock. Recovered work must not repeat ambiguous failover dispatches.
- journal-contracts.yml may write/read synthetic journal records using its GitHub token, without Apple/Telegram secrets, to test cross-runner recovery and principal isolation.

## Persistent VPS deployment
- The user purchased a Debian 13 x86_64 VPS and explicitly asked to connect the project. Keep the server address and SSH credentials in deployment Secrets, not public source.
- GitHub builds/tests the public release, including Debian 13 compatibility. The VPS installs only runtime packages and verified artifacts. SSH installation, service startup and operational health inspection are authorized; no tests or compilers on the VPS.
- A dedicated VPS_GH_TOKEN limited to this repository supplies Actions write and Contents read. Never copy the maintainer's broad workstation OAuth credential onto the server.
- The daemon uses a private SQLite recovery log, persistent Telegram state, a single-controller lock, systemd restart and a non-root service account. Apple credentials/model stay in GitHub. Only authenticated delivery-envelope decryption may run on the VPS.
- Disable the bounded telegram-session workflow after successful cutover to prevent a second poller. Owner-only access and billing-off remain defaults.
- Runtime service credentials travel only via pinned SSH to a root-private systemd credential file, never public artifacts/logs. Deploy only after CI passes; retain the previous release for rollback.

Checks 不是 fine-grained PAT 的必填权限。遇到 Checks 权限拒绝时，服务器改用 Actions 任务/步骤状态；不再基于缺失的 Checks 证据提前交付或取消排队任务，等待正常完成后校验交付。

- Persistent VPS deployment is verified by run 41899775076 at code commit 06bcf81fab70e597c823d1096877d3d6df4c01bd (347 Python tests, 1 skip, on both Ubuntu and Debian 13; Go and actual systemd credential mount tests). The owner-only daemon is enabled and healthy, and Telegram startup notification was acknowledged. Do not describe a fresh post-migration IPA task as verified without separate evidence. The legacy telegram-session workflow is disabled; stop the VPS service before enabling another poller.
