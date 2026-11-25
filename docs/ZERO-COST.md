# Zero-cost deployment constraints

Owner requirement (2026-11-24): no paid VPS, no paid subscriptions or metered overage charges. No automatic provisioning or upgrade to a paid plan. A trial or expiring promotional credit is not a durable zero-cost solution. An estimated bill of zero is not a hard spending limit.

## Available free control-plane candidates

- Cloudflare Workers Free: suitable for small event-driven requests; currently 100,000 requests/day, 10 ms CPU per HTTP invocation and 128 MB memory. Not a native Linux container or macOS runtime.
- D1 Free: candidate for transactional task records and small encrypted state, with free quota limits and errors rather than a plan upgrade. Its row size and database capacity are not suitable for storing large IPA archives. A separate D1 pilot schema and authenticated Telegram webhook now exist. Production SQLite-to-D1 migration must preserve identities, idempotency, unknown outcomes and history; that migration is not implemented.
- Queues Free: 10,000 operations/day and 24-hour retention. The database must remain authoritative for task recovery; do not assume the queue provides indefinite persistence.
- R2 is not approved by default: its included free usage is followed by metered charges, and activation requires an R2 subscription. Do not enable a billable service unless a true zero-cost cap can be confirmed and the owner explicitly changes the constraint.
- Render Free does not provide persistent disks or free background workers. The previous paid configuration is withdrawn.

## Processing and delivery constraints

Workers Free does not replace the native worker or the official Local Bot API process. Telegram's hosted Bot API supports up to 50 MB per upload; the Local Bot API supports up to 2000 MB but requires a compatible running compute host. The current verified controller's disk guard remains in force. A link-based delivery option would still require approved private storage and compliant execution capacity; it is not a working free solution today.

GitHub-hosted Actions may build, test and publish the project under applicable terms and free quotas, not serve as a permanent bot host, production compute substitute or file-distribution network. Do not add scheduled keep-alives, quota workarounds or production dispatches as a workaround for paid infrastructure. Existing production must not be changed by this branch.

The project has not established a fully free, no-server production path preserving all features, including large-file delivery and existing TestFlight state. No service should be migrated until a permitted zero-cost runtime with adequate compute and private persistent storage is actually verified. If the constraints conflict, leave production unchanged and report the unsupported capability rather than silently reducing file limits or incurring charges. Pause new work at free-tier limits; never auto-upgrade.

## Official references

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/d1/platform/limits/
- https://developers.cloudflare.com/d1/reference/faq/
- https://developers.cloudflare.com/queues/platform/pricing/
- https://developers.cloudflare.com/r2/get-started/
- https://render.com/docs/free
- https://core.telegram.org/bots/features#local-bot-api
- https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features


## Free pilot (implementation candidate)

The independent Worker and D1 schema are in deploy/managed/free-pilot. It is disabled by default, has no public route in the example configuration, and requires an isolated D1 database ID and a separate test bot. The owner-only private Telegram webhook supports /start, /help, /status, /cancel and registration of an App Store link or numeric ID. Each request is clearly labeled waiting_for_runtime; no native worker is invoked, no GitHub production workflow is dispatched, and no file is retrieved or sent. TestFlight is intentionally unsupported in this pilot. The database deduplicates Telegram update IDs and atomically enforces three registrations per UTC day and thirty outstanding records. Cancellation does not refund the daily cap. The code refuses unavailable D1 rather than automatically changing plans, and it logs no private inputs.

The provided wrangler.example.json is intentionally not directly deployable: replace its non-resolving database ID only in an isolated Workers Free account; manually verify the account's plan and billing status. Provision only the isolated free D1 database, apply its initial migration, configure an independent owner ID and random Telegram webhook secret as Worker Secrets, select an explicitly approved test endpoint, and enable PILOT_ENABLED only for a separate test bot. Never set a webhook on the live bot while it uses getUpdates or a Local Bot API server. No actual deployment or secret changes are done by CI. Telegram webhook replies are best effort and do not certify delivery.

The synthetic contract workflow tests this Worker, its SQLite SQL semantics and the existing managed modules; container image compilation is opt-in manual build-only because it is not required for the free control-plane pilot. The previous image build failed restoring the pinned Bot API cache. No image availability is claimed. A future permitted zero-cost execution and private delivery environment remains mandatory for production migration.

## Phase 5: free-platform feasibility and integration gate (2026-11-24)

The previous free-pilot synthetic and native CI succeeded (runs 45388729857 and 45388729945). The new integration test runs the exact Worker in a pinned local Miniflare/workerd simulator, with simulated D1 and no external accounts or real credentials. It checks concurrent admission, replay protection, cancellation, database persistence across simulator restart, and fail-closed database errors. The compatibility date is pinned to the simulator release date. CI must pass before any pilot deployment. A successful local integration still does not prove hosted Free CPU limits or real Telegram receipt.

Provider review:

- Cloudflare Containers require Workers Paid ($5/month base plus metered usage); excluded.
- Google Cloud e2-micro free allocation includes 1 GB monthly outbound transfer; unsuitable for a service retaining the 2 GB per-file capability and hard zero-charge requirement.
- Oracle Cloud Always Free is a possible **free VM**, not a serverless substitute. Current official entitlement lists 1,500 A1 OCPU-hours and 9,000 GB-hours per month (2 OCPU / 12 GB continuous allocation), with up to 200 GB eligible block volume storage. Availability is regional and idle VMs may be reclaimed. Account signup requires payment-card verification; do not upgrade to Pay As You Go. The existing controller package is amd64, so ARM support would require separate validated builds. This VM cannot provide the existing macOS environment. Do not create any VM or account without owner approval.
- GitHub Actions is for software development/testing and cannot be assumed available for production request processing or file distribution. No change to production workflows is authorized by this review.

Thus the free-only, no-VM architecture remains incomplete. If no permitted zero-cost runtime can be verified, keep the isolated pilot and existing production untouched. Do not repeatedly add mock task processing or label waiting records as completed. For a useful next architecture decision, distinguish whether the owner accepts a free VM (still a server), or requires strictly serverless and accepts reduced capabilities. Neither option has been provisioned.

Sources:
- https://developers.cloudflare.com/containers/platform/pricing/
- https://docs.cloud.google.com/free/docs/free-cloud-features
- https://www.oracle.com/cloud/free/
- https://www.oracle.com/cloud/free/faq/
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
- https://developers.cloudflare.com/workers/testing/miniflare/get-started/
- https://developers.cloudflare.com/workers/testing/miniflare/storage/d1/


## Phase 6: private link delivery pilot

Owner approved replacing large Telegram file uploads with download links, while the hard zero-cost constraint remains. Google Drive personal accounts include 15 GB shared storage, and standard Drive API usage is currently free; Google has announced future charges for above-threshold API usage. Do not attach a Cloud billing account or increase quotas for this pilot. Verify the current free plan and billing status before enabling. R2 requires a subscription and B2 non-paying downloads are capped; neither is automatically provisioned.

The pilot implements **retrieval of already uploaded, authorized files**, not automated uploads, native processing, or distribution of third-party apps. The isolated operator may register a synthetic or rights-cleared file already in a restricted Drive account. Apply all D1 migrations in order (including 0004, see Phase 10). Set PILOT_LINK_ENABLED=1 only after isolated configuration review. New independent Worker secrets: PILOT_LINK_ISSUER_TOKEN, PILOT_DRIVE_ACCESS_TOKEN (short-lived manually authorized OAuth token with minimal Drive read access to the selected file), and PILOT_DRIVE_RECIPIENT_EMAIL. Keep them out of logs, repository files, and chat. No refresh token is retained; expiration or failed verification makes the feature unavailable. The issuer calls POST /v1/link-register with Bearer issuer token and a JSON object containing job_id, file_id, filename, bytes and sha256. Use only synthetic test records until explicitly authorized for deployment. Do not use the live bot.

Before registration and /get, the Worker verifies Drive file size, name, SHA-256 metadata, ownership, non-trashed status and a closed permission list (one owning account plus at most the designated user reader; no public/domain/group access). It only returns a standard Drive link privately to the configured Telegram owner. The file remains in Drive, not D1 or Telegram, and the original maximum registered size was 2,000,000,000 bytes (superseded by Phase 8). A 2-hour bot retrieval window is enforced by the D1 query; expiry or cancellation does not revoke previously issued Drive access. Free personal accounts do not generally support native expiration; revoke Drive ACL manually where needed. Links remain subject to account access, quota, download restrictions and provider policies. The feature does not assert download success. Do not mark a job completed based solely on receipt registration.

No live account, provider permission change, upload, bot message, or billing change is performed by CI. Tests simulate Google metadata and ACL responses and run the actual SQL against SQLite. A real free storage account, isolated bot, permitted production execution environment, upload integration, cleanup/revocation and end-to-end tests still need to be established.

Sources:
- https://support.google.com/accounts/answer/6374270
- https://developers.google.com/workspace/drive/api/guides/limits
- https://support.google.com/drive/answer/7166529
- https://developers.google.com/workspace/drive/api/guides/manage-sharing
- https://developers.cloudflare.com/r2/get-started/
- https://www.backblaze.com/apidocs/b2-get-download-authorization


## Phase 7: resumable private upload candidate

The isolated operator CLI `deploy/managed/free-pilot/private_upload.py` uploads a pre-existing synthetic or rights-cleared private file to the operator's own Drive account; it does not acquire or decrypt third-party apps or change the production worker. It is not called from GitHub Actions, and live CLI execution on Actions is explicitly rejected. The same designated Google account must own the uploaded file and access the returned link. No public or external-reader permission is granted automatically. This deliberately keeps the first end-to-end pilot owner-only.

Use an approved personal free account, a manually authorized short-lived access token with drive.file scope for the same OAuth app, and a private input file (0600). Do not attach billing, increase quotas, or use a paid account. The CLI asks for explicit free-account and authorized-file confirmation, checks the provider's reported shared storage limit (at most 15 GiB), total usage, and a 1 GB reserve before starting. A storage quota does not prove account billing status; the operator must verify that separately. Multiple unrelated writers to the same account are not coordinated, so keep the account isolated and stop on quota errors.

It uses the official resumable create endpoint and bounded 8 MiB chunks. A private local journal binds job, filename, bytes, checksum and recipient account. The opaque resumable session stays in that journal, not in public output. Repeat the same command after an interrupted chunk to query the server-confirmed offset. A lost session, ambiguous create, or ambiguous registration stops; it does not create a replacement file or retry the link receipt blindly. Do not discard the journal to retry an unknown operation.

After completion, verify provider size, SHA-256 metadata and owner-only access before recording a receipt. With the optional register flag, the CLI submits that receipt to the explicitly configured isolated Worker origin using its independent issuer token. It never sends Drive credentials to the Worker endpoint. The Worker independently rechecks metadata and ACL before /get. The 2-hour retrieval window is still not a provider ACL expiry. No automatic deletion, public share, or paid upgrade is performed. OAuth expiry, an unavailable free runtime, and provider or database quota errors remain explicit blockers.

Operator usage (only after isolated pilot and free plan approval, and never with a live production bot): set PILOT_DRIVE_ACCESS_TOKEN and PILOT_DRIVE_RECIPIENT_EMAIL in a private environment; for registration also set PILOT_LINK_ORIGIN and PILOT_LINK_ISSUER_TOKEN. Run private_upload.py with --file, --job (an existing pilot job), --journal (an existing or new private directory), --confirm-free-account, --confirm-authorized-file and optionally --register. Never put secrets in arguments, chat, public source or logs. Keep the journal on an approved private persistent volume. CI runs only fake transports and synthetic local files, not the live CLI.

References:
- https://developers.google.com/workspace/drive/api/guides/manage-uploads
- https://developers.google.com/workspace/drive/api/reference/rest/v3/about
- https://developers.google.com/workspace/drive/api/reference/rest/v3/about/get
- https://developers.google.com/workspace/drive/api/reference/rest/v3/files

Remaining gate: establish a real isolated free account and permitted execution environment, deploy the separate test Worker and D1 migrations, authorize minimal credentials privately, test a synthetic upload and /get receipt, verify cleanup and real download. Existing production remains unchanged.


## Phase 8: 10 GB private link capacity

The owner approved a 10 GB decimal ceiling (10,000,000,000 bytes) for the isolated link-delivery pilot. The uploader, link metadata validation and new D1 migration 0003_links_10gb.sql enforce the same cap. Existing 0002 migration remains unchanged for reproducible upgrades. Apply 0003 transactionally with the pilot disabled, preserving existing rows and original expiry times. CI checks the migration in SQLite and local workerd/D1, including exact integers beyond 32-bit and rejection above the new limit.

No file is stored in D1 or uploaded through the Worker: D1 retains only metadata and the authorized uploader uses bounded 8 MiB chunks directly to Drive. Before any new upload and before resuming incomplete writes, the CLI checks the reported free-plan storage limit, current usage and the full file size plus 1 GB (decimal) reserve. This conservative recheck may stop a resume if capacity cannot be confirmed. Provider quota errors remain hard failures; do not upgrade plans. The practical limit is min(10 GB, reported free bytes minus 1 GB reserve), subject to actual provider restrictions. Synthetic tests model large offsets and capacity arithmetic without allocating or uploading multi-GB files; they do not prove a real 10 GB upload.

The production Telegram path and native processing capacity (tools/capacity.py MAX_IPA_BYTES=2,000,000,000), archive checks, disk guard, workflow artifact/time limits, and existing delivery path remain unchanged. This is a capacity upgrade for already-prepared authorized files in the separate pilot, **not** verified 10 GB IPA acquisition or decryption, nor a production deployment. A permitted free processing environment and real end-to-end storage test remain required. Do not raise native or live delivery limits blindly or use production credentials for CI.


## Phase 9: ZIP64 and archive capacity preflight

Phase 8 CI passed (managed contracts run 45390184333), covering 10 GB link metadata, SQLite/workerd migration and simulated large upload offsets. This did not upload a 10 GB file.

The isolated uploader now runs a read-only ZIP/ZIP64 metadata preflight before hashing and uploading an already-prepared authorized .zip or .ipa. It bounds the central directory to 16 MiB, entry count to 32,768, archive/member size to 10 decimal GB and declared expansion to 30 GB. It rejects multi-disk archives, malformed end records, unsupported compression, duplicate/unsafe paths, encrypted ZIP entries, symlinks and invalid or overlapping local member headers. It does not extract, change, decrypt or run the archive, and does not claim all member CRCs or runtime are verified. The whole input SHA-256 and provider checksum comparison remain separate. CI creates a synthetic sparse stored ZIP64 archive with a real logical member size and later member offset beyond 4 GiB, without uploading any file or allocating multi-GB physical storage.

Capacity audit of the existing native path: tools/capacity.py and tools/delivery_crypto.go still enforce 2,000,000,000 bytes; ipa_audit.py derives member, expansion and read limits; private_export.py and worker workflows enforce source, output, disk, time and artifact bounds. Simply changing the shared constant would also raise the existing Telegram route and would not demonstrate large-package compatibility. At 10 GB, the existing 3x archive/transfer disk reservation formula alone implies 32,147,483,648 bytes free, before additional runtime overhead. The free control-plane pilot does not provide that native compute/disk environment. Native acquisition/processing, live Telegram limits and deployment are unchanged. Do not claim end-to-end 10 GB IPA support until a permitted, adequately provisioned processing environment and real authorized file verification exist.


## Phase 10: explicit storage reclamation and retirement

Apply migration 0004_retired_links.sql in the isolated database with the pilot disabled. Link metadata and update deduplication are retained; registered links no longer occupy the 30 waiting-job slots, and the status view distinguishes recorded links from waiting jobs. A retired link cannot be retrieved again. Expired records do not refund the daily quota.

New uploader-created files have private Drive appProperties binding the pilot job and uploader schema. The operator-only private_cleanup.py defaults to inspection, not deletion. It accepts only the matching private journal, exact file identity, digest, size, name, owning account, owner-only ACL and uploader marker. Previously created or manually registered files without the marker are intentionally excluded. With the explicit --confirm-permanent-delete flag and verified free account, it requests the isolated Worker to retire the exact receipt; the Worker will only grant retirement after the two-hour retrieval window plus 24 hours. It then rechecks file ownership and identity and attempts one single-file permanent deletion. No bulk delete, empty-trash operation, automatic scheduler or live CI deletion is included. A lost deletion response leaves an intent in the journal and blocks retries; inspect the provider manually. Expiry alone does not remove a file or release quota. Only provider-confirmed deletion may be described as deleted; free-space reporting may lag.

Do not enable this on a production bot or shared account. Keep the default read-only until the owner explicitly authorizes a particular disposable test file for permanent deletion. The CLI refuses live execution on Actions; CI uses only fake network calls. Remaining blockers are actual isolated free account setup, live authorized upload/download, and a permitted native execution environment. More synthetic modules cannot establish an end-to-end production service without these prerequisites.

References:
- https://developers.google.com/workspace/drive/api/guides/delete
- https://developers.google.com/workspace/drive/api/guides/properties
- https://developers.google.com/workspace/drive/api/reference/rest/v3/files/delete


## Phase 11: deployable free pilot bundle

Phase 10 synthetic and workerd contracts passed in run 45391181658 (container job skipped). The new read-only CI packaging job runs after both contract jobs. It uses a pinned esbuild release to bundle the Worker into a single ES module, packages the exact migrations, fresh-database schema, disabled configuration, public operator utilities, source provenance and checksums. No Cloudflare account, OAuth credentials, Telegram token or paid resources are involved; this is a public software build artifact, not a file-delivery service.

See [Chinese browser deployment guide](../deploy/managed/free-pilot/DEPLOY.zh-CN.md). The owner must establish the independent free Cloudflare account/database, separate test bot, and authorized Google OAuth setup before live verification. Do not use the production bot or the original account state. There is no approved, verified zero-cost native execution host yet; the upload operator still needs a trusted execution environment. Do not claim full production cutover.


## Phase 12: request-local Drive OAuth refresh candidate

The isolated Worker accepts optional owner-configured OAuth client ID, client secret and refresh token bindings. It uses Google's standard server-side token endpoint only when a permitted link operation needs Drive access; a single access token is used for the metadata and ACL checks. Returned Bearer type, expiry and explicit drive.file scope are required. Partial configuration, errors, expired or revoked grants, unexpected token rotation and broader or absent scopes fail closed, without fallback to the previous manual access token. No token persistence in D1, scheduled jobs, credential transfer automation or live OAuth calls are introduced. Tests use synthetic injected transports only. The original manual short-lived token mode remains available when no refresh settings are configured. The Python operator uploader still requires a valid short-lived access token. Google Testing mode retains its seven-day refresh-token expiry. A separately reviewed authorization and deployment are needed before enabling the pilot; no change to production or billing.

Official references:
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2#expiration
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth


## Phase 13: live verification and operator refresh

Live read-only probe 45412582043 confirmed OAuth refresh, account match, D1 schema and available capacity for a 10,000,000,000-byte file with reserve. The transport-fix artifact was deployed in 45415199977. The initial deployment failed artifact-digest verification and was corrected without bypassing that check. Both activation switches remain disabled. Synthetic transfer contracts passed in 45414991034; the actual one-file verification stopped before upload in 45415372611 and 45415585730, with the latter reporting Google invalid_grant. No smoke file was created, and the original isolated deployment was restored. This is not a verified transfer. A fresh owner-authorized grant is required; the exact cause of the invalidation is unknown.

The operator uploader and cleanup tool now optionally use a process-local short-lived token cache with explicit scope/type/expiry validation. They refuse incomplete OAuth configuration and latch invalid_grant for the current process. No automatic replay of writes, credential export, CI live upload, production dispatch or change to cleanup authorization is introduced. Actual operator execution still requires a trusted host. The no-VM production runtime constraint remains unresolved.


## Phase 14: eligibility regression and stop conditions

The later personal-mode configuration was checked in run 45421278281: all four binding types were secret_text; OAuth succeeded, but the transfer stopped at quota verification before creating any file. The original isolated disabled deployment was restored. The owner subsequently reported updating the recipient email. A further live test was not authorized by the available execution interface, so this newer configuration remains unverified. No production bot, native worker, billing setting, existing file, or user data was changed.

This source-only revision separates eligibility errors (account mismatch, malformed/unavailable quota, incompatible capacity, insufficient storage and HTTP status categories) without disclosing raw provider data. Tests use synthetic responses and assert that every failed preflight prevents file creation. The encoded Drive about query and explicit GET are covered by the regression. The revision does not install a live diagnostic endpoint, execute a real OAuth request or change the existing deployed Worker. Actual end-to-end transfer is still pending.

Free-runtime review (2026-11-24): Workers Free has 10 ms CPU / 128 MB memory; OCI Always Free A1 is a Linux ARM VM, not a native macOS serverless environment, and may be reclaimed if idle. Cloud Run is metered; free usage allowances do not establish a hard zero-charge guarantee. GitHub Actions remains a development/test/deployment service, not a substitute for a production processing or file distribution service. The existing native limit is 2,000,000,000 bytes; the 10,000,000,000-byte link limit does not change that. No eligible native runtime or production cutover is certified.

References:
- https://developers.cloudflare.com/workers/platform/limits/
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://docs.cloud.google.com/run/docs/configuring/billing-settings
- https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features


## Phase 15: Linux read-only archive integrity tool

A standalone zipapp is built from archive_verify.py and the existing bounded ZIP64 metadata preflight. It verifies CRCs of all logical members, declared sizes, a minimal IPA layout, the original archive SHA-256 and unchanged-file metadata; it can compare an independently trusted expected digest. The build and relocated smoke test use only synthetic data in GitHub-hosted Ubuntu CI. It cannot establish authenticity, installation compatibility or DRM status and does not alter archives. The 10 GB input bound remains distinct from actual full-size throughput. No production runtime or live transfer is introduced. See deploy/managed/free-pilot/LINUX-ARCHIVE.zh-CN.md.


## Phase 16: Linux pre-upload integrity gate and exact-size fixture

The private operator uploader uses the existing full archive verifier for IPA/ZIP input, with no modification of source bytes. It keeps the original receipt and journal schema and checks input metadata before provider operations and around chunk reads. Malformed layout/CRC failures stop before uploads; changed input stops the current attempt without recreating the upload. Synthetic transport tests exercise interrupted upload and byte-for-byte recovery. The Linux bundle job additionally runs a sparse, exactly 10,000,000,000-byte ZIP64 fixture through complete CRC and independent reference SHA-256 verification, with an oversize rejection. Its measured CI result is evidence only after the job succeeds; the fixture is not published. No live upload, billing, credential operation, or deployment is introduced. Apple-specific processing and an eligible production host are still unresolved.


## Phase 17: dual-architecture Linux operator tools

Phase 16 succeeded in run 45426356157, including a complete read of the 10,000,000,000-byte synthetic archive in 8.285 seconds (sparse fixture, not a live transfer), 19 synthetic uploader tests, workerd and packaging. The new matrix uses GitHub standard ubuntu-24.04 and ubuntu-24.04-arm for software build/test only. It validates host architecture, repeats the exact-size synthetic archive test, builds standalone Python zipapps for read-only verification and the existing private operator uploader, tests the relocated uploader with fake transport, and checks its refusal of live uploads on CI. Public artifacts contain only tool code and checksums; no account material or user files. Runtime compatibility must be reported separately for each passing matrix job. No change to Apple-specific processing, production deployment, or credential handling; no free host is provisioned.


## Phase 18: preserve standalone CLI failure status

Run 45426964681 verified the exact 10 GB synthetic archive on both Linux architectures: x86_64 11.528 s, 28,044 KiB peak RSS; aarch64 12.547 s, 27,048 KiB peak RSS. Both relocated read-only verifier checks passed. Both uploader packages failed the CLI exit-status assertion, so no standalone uploader artifact from those matrix jobs is certified. The standard zipapp -m entrypoint calls main without propagating its return value; this revision writes an explicit SystemExit entrypoint and retains the existing refusal-of-live-CI-upload check. No upload guard is relaxed. Existing synthetic transport tests, native constraints, and disabled live pilot are unchanged. Certification requires the corrected matrix to pass.

## Phase 19: corrected dual-architecture packaging evidence

Managed runtime contracts run [45427781144](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45427781144) completed successfully for source head `cdb8e9e503b21273041dafdafabcd6ff83c3c353`. Both Ubuntu matrix jobs completed the exact 10,000,000,000-byte sparse synthetic ZIP64 full-read CRC and independent SHA-256 tests, oversize rejection, relocated archive tool check, packaged uploader refusal of live CI execution, 19 fake-transport uploader regression tests, and artifact checksum generation. The local workerd contracts and disabled-by-default deployment bundle also passed; the optional image job was skipped.

| Verified Linux host | Full-read verification | Peak RSS | Build artifact ID |
| --- | ---: | ---: | ---: |
| x86_64 | 11.636 s | 28,132 KiB | 14938575447 |
| aarch64 | 12.489 s | 27,044 KiB | 14938175552 |

The artifacts contain public software tools, BUILDINFO and checksums, not actual IPA files or account credentials. The reported measurements use a sparse stored synthetic archive, not realistic compressed data or a live provider transfer. The CI artifact names carry the checked-out PR merge revision; the source head is recorded separately. The corrected CLI failure status is certified for these two jobs, not for untested platforms.

The separate [native feasibility run 45427781233](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45427781233) reported no native symbol on Linux. Its two virtualized macOS jobs reported native symbol availability, but neither account authorization nor actual decryption was established. Passing synthetic native tests must not be described as successful real decryption.

Remaining hard gates: an eligible zero-cost, non-VM processing runtime; current private Google OAuth and storage eligibility; a permitted real upload/download check of authorized input; and actual integration with the existing bot. Do not enable live switches, change billing, migrate the production bot, or use CI as a permanent processing service. The production limits remain unchanged. No live account or service operation was performed to record this evidence.

## Phase 20: owner-reported iOS foreground regression (2026-11-24)

The owner supplied phone terminal screenshots of the pinned host probe (source `f9aa91c54a0d81687bc45dd3d8727034391a4f50`) and phone synthetic regression runner (commit `07b06712ed17e2f92af0b4cbf1857a4123c315a3`). The emulated Alpine i686/Python 3.9.16 host failed exclusive locking and symlink refusal, so it is not accepted for the existing upload journal. The native iOS a-Shell mini/Python 3.13.1+ host passed all seven primitive checks. The pinned regression runner reported 29 tests in 0.039 s, zero failures, errors or skips; the large sparse fixture was explicitly excluded. These are owner-provided foreground observations, not independently reproduced device tests. No security check was weakened.

The new phone-only Drive smoke runner is a candidate, not a passed live test. It checks three pinned public source blobs, accepts a short-lived authorized drive.file token via non-echoing input only, requires explicit confirmation of a free personal account and synthetic upload, and uses the existing upload journal and verification module. It creates a single 1 KiB synthetic file, verifies owner-only permissions and download byte equality/SHA-256, and retains the journal. It neither registers a bot link nor deletes files, and refuses GitHub Actions execution. No production credentials, user app files, or real Drive requests were used to develop this runner. The account, token, actual transfer and download must be verified on the phone. The iOS foreground execution result does not establish unattended operation, 10 GB device throughput, native decryption or production cutover.

## Phase 21: cloud-only architecture re-evaluation (2026-11-24)

Owner explicitly rejected making the phone a worker or upload device. Phase 20 is retained solely as historical compatibility evidence; its proposed phone Drive smoke test is superseded and must not be requested again. Production acceptance requires unattended cloud-only operation, no owner-operated computer or VM, no additional fees, no silent feature reduction, and authorized private link delivery with a 10 GB maximum. Do not ask the owner to create another bot, repeat OAuth setup, or enroll in a paid or payment-dependent platform merely to test a speculative architecture.

Provider documentation rechecked on 2026-11-24:

- Cloudflare Workers Free: 10 ms CPU, 128 MB memory; suitable for the control plane, not the existing native worker. Containers require Workers Paid. https://developers.cloudflare.com/workers/platform/limits/ and https://developers.cloudflare.com/containers/platform/pricing/
- Northflank Sandbox: free resources without a card, supports jobs, but the vendor advises against production use on the free tier. The documented standard ephemeral disk quota is 2 GiB (free project limits may differ); a suitable free large-disk allocation is not established. https://northflank.com/docs/v1/application/billing/pricing-on-northflank and https://northflank.com/docs/v1/application/billing/resource-plans-and-quotas
- Koyeb Free: 2 GB disk, 512 MB RAM, 0.1 vCPU, no worker services; intended for testing/hobby workloads, not production. https://www.koyeb.com/docs/reference/instances
- Hugging Face: current documentation says creating a compute-backed Space requires a paid plan even when CPU Basic hardware itself has no hourly cost. https://huggingface.co/docs/hub/spaces-overview
- Deno Deploy Free: 20 GiB monthly egress, 10 active CPU hours, no Sandbox entitlement. Potential limited control/transfer role, not established as a compatible native worker. https://deno.com/deploy/pricing
- Google Apps Script: 6 minutes per execution, 50 MB URL Fetch request/response limit and 90 minutes daily trigger runtime on consumer accounts. Not a substitute for native processing. https://developers.google.com/apps-script/guides/services/quotas
- Modal Starter: recurring 30 USD compute credit and 1 TiB monthly included egress; function timeout configurable up to 24 hours; default container disk quota 512 GiB subject to host availability. The provider documents separate gross usage budgets and net spend limits that stop additional paid workloads. However, an on-file payment method is required, and the ability to configure and enforce an exact zero-dollar net limit for this account and all applicable meters has not been demonstrated. Do not enroll or deploy. Even if a hard zero-charge configuration is confirmed, ordinary Linux containers would only be a candidate for authorized archive processing, not an implementation of the missing Apple-native capability. https://modal.com/pricing , https://modal.com/docs/guide/budgets , https://modal.com/docs/guide/billing , https://modal.com/docs/guide/resources and https://modal.com/docs/guide/timeouts
- AWS EC2 Mac: billable dedicated hardware with a 24-hour minimum allocation. MacStadium dedicated Macs are paid and do not offer individual trials. https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html and https://macstadium.com/pricing?tab=cloud
- GitHub-hosted Actions remains software development/build/test infrastructure, not the production service or a file distribution network. https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features

Decision: no new runtime meets every verified acceptance gate. Do not enable a cloud worker on the strength of free-credit marketing, use device workarounds, or certify a Linux archive tool as a native decryptor. A genuine cloud-only full migration remains blocked by an eligible runtime and the separately unverified native capability, plus the outstanding private Drive round trip and bot integration. Keep existing production, pilot configuration and account billing unchanged. This revision records the investigation and stops the abandoned phone path; no deployments, account creation, secret changes or live tests were executed.

## Phase 22: verified private Drive round trip (2026-11-25)

The isolated Cloudflare Worker passed OAuth refresh, account matching and the small-fixture quota check, then completed one resumable upload of a 1 KiB synthetic text file in [run 45618247660](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45618247660). The upload returned the reserved file ID; the subsequent metadata check rejected the media type. A read-only inspection in [run 45618525453](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45618525453) located the same exact name and app marker and confirmed its size, ownership and stored SHA-256 before failing at the media type check.

The fixed test accepts plain text for this specific fixture. The [managed runtime contract run](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45618644975) passed on the tested source. The [read-only cloud verification](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45618731737) confirmed the existing file had exactly one permission (its designated owner), downloaded 1,024 bytes, and reproduced the pinned SHA-256. The probe created no additional file and restored the original disabled Worker deployment. The owner-only synthetic file remains in Drive.

Google now documents a no-charge [Drive API Standard Tier](https://developers.google.com/workspace/drive/api/guides/quotas) with quota throttling. Keep pilot operation within Standard Tier and the existing personal storage allocation. The 1 KiB result covers the private upload/download path. A live 10 GB transfer, Telegram link integration, and an eligible zero-cost cloud host for unattended native processing are still outstanding. Production cutover remains blocked.

## Phase 23: private link verification and owner-only retrieval (2026-11-25)

The isolated [cloud verification](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45619922392) used the same Drive link verifier as `/get` on the existing 1 KiB sample. The verifier accepted the file's metadata and restricted permissions, generated the expected private Drive link, and reported only a sanitized success flag. The run also matched the downloaded SHA-256; it created no file, changed no Drive permissions, and restored the disabled Worker deployment.

The [managed runtime contracts](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45620003273) exercised the actual Worker handler against workerd D1 and synthetic Drive responses. The test covers issuer authentication, duplicate registration, owner-only `/get` replies, and exclusion after expiry or cancellation. Telegram receipt and live D1 link registration remain unverified. The synthetic fixture is still private in Drive. The native cloud runtime and a real 10 GB transfer remain open.

## Phase 24: hosted D1 registration and retrieval (2026-11-25)

The [isolated hosted D1 run](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45620785416) passed using the pilot's actual registration and lookup SQL. A single atomic D1 batch inserted a uniquely scoped synthetic job and link, verified the exact 10,000,000,000-byte metadata value, and exercised duplicate rejection, owner scoping, expiration and cancellation. The same batch removed both fixture rows and confirmed zero residue. The run also revalidated the original 1 KiB private Drive sample without writing additional files, and restored the disabled Worker deployment.

This evidence covers hosted D1 SQL and the private Drive verifier. The database test used synthetic metadata. A real 10 GB transfer, Telegram receipt, and an eligible zero-cost native cloud worker remain open.

## Phase 25: native cloud eligibility recheck (2026-11-25)

- [Scaleway Apple silicon M4](https://www.scaleway.com/en/mac-mini-m4/) starts at €0.22/hour with a 24-hour minimum allocation. [EC2 Mac](https://aws.amazon.com/ec2/instance-types/mac/) also bills for a dedicated host with a 24-hour minimum. Both require a budget for compute.
- [Microsoft-hosted Azure Pipelines macOS agents](https://learn.microsoft.com/en-us/azure/devops/pipelines/agents/hosted?view=azure-devops) are discarded after each CI job and provide 14 GB of SSD space. They do not establish an unattended production host. [GitHub-hosted runners](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job) also create a fresh runner for each job.
- [Cloudflare Containers](https://developers.cloudflare.com/containers/platform/pricing/) require a paid Workers plan. Workers Free continues to cover the pilot control plane; Phase 24 established hosted D1 behavior and exact 10 GB metadata persistence. Real file transfer at that size and Telegram receipt still require their own evidence.

The reviewed offerings provide no verified way to cut over under the current zero-cost and unattended cloud requirements. No services were provisioned in this review.

## Phase 26: CircleCI ARM64 sample to private Drive (2026-11-25)

A [CircleCI macOS job](https://app.circleci.com/workflow/77558c11-5004-4058-a6a6-00dfed479eb7/job/d3ebdbc6-d150-4c05-99ff-2f2485f27d92) produced an unsigned synthetic ARM64 iOS sample from project-owned source and verified it with the v0.2 archive verifier. The isolated [Drive upload](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45641196677) returned the file ID, then stopped on Drive's MIME label. The [read-only follow-up](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45641512941) found the same sample and confirmed owner-only access, 5,495 downloaded bytes and exact SHA-256 equality with the CircleCI artifact. No duplicate file was created. The sample remains private in Drive and the Worker returned to its disabled deployment.

This proof covers build, archive verification and private Drive transfer for a small project-owned IPA. Live Telegram receipt, a 10 GB transfer and production cutover remain open.

## Phase 27: hosted owner-only retrieval for the CircleCI IPA (2026-11-25)

The [isolated retrieval test](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45642951780) registered and looked up the existing 5,495-byte CircleCI Drive sample using the hosted D1 SQL in a single batch. The batch removed both fixture rows before it returned the receipt. The Worker fed that receipt and a synthetic private update to the real `/get` handler. The handler rechecked the existing Google Drive file's metadata and owner-only access, constructed the expected private link reply, and withheld it from a different synthetic sender. The probe returned only a sanitized summary and restored the disabled Worker deployment.

No Telegram API request was sent. This establishes the reply and access checks for the sample, while actual Telegram receipt, 10 GB transfer, and production cutover remain open.

## Phase 28: private Telegram test with the existing bot (2026-11-25)

The [owner-authorized one-shot test](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45644694693) regenerated the private `/get` reply for the existing ARM64 sample. The isolated Worker denied a different synthetic sender and restored its disabled deployment before the existing VPS bot sent the link. Telegram acknowledged exactly one `sendMessage` to the configured owner's private chat with link previews disabled. The VPS reserved a private one-shot marker before sending so an ambiguous response cannot cause an automatic duplicate. No credentials, private URL or chat identifier were logged.

Telegram acknowledged the outgoing test reply, and the owner subsequently confirmed that the designated Google account could open the link from their private Telegram chat. This confirms receipt and access for the small sample. The VPS continues polling. Inbound webhook cutover, a live 10 GB transfer and the production runtime remain separate.

## Phase 29: ARM64 production host recheck (2026-11-25)

The two Linux ARM64 images passed import on a fresh native runner in [run 45655428851](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45655428851/job/139351699825). The current controller requires one continuously available replica, at least 2 GiB of memory and a private writable volume with at least 8,147,483,648 bytes available. The following checks apply to that controller.

- CircleCI Free supports the Apple silicon M4 Pro build runner. Its hosted jobs end after at most one hour. Workspaces are temporary workflow storage with a maximum retention of 15 days. Keep the verified CircleCI path for project-owned ARM64 builds. [CircleCI configuration reference](https://circleci.com/docs/reference/configuration-reference/) · [CircleCI workspaces](https://circleci.com/docs/guides/orchestrate/workspaces/)
- Railway Free has 0.5 GB RAM per service and one 0.5 GB volume. Its monthly usage allowance also stops services when exhausted. [Railway Free plan](https://docs.railway.com/pricing/free-plan)
- Northflank Sandbox is documented for evaluation and hobby workloads. Northflank advises using its production plans for production workloads. [Northflank pricing documentation](https://northflank.com/docs/v1/application/billing/pricing-on-northflank)
- Cloudflare Containers require Workers Paid. Google Cloud Run's documented runtime ABI is Linux x86_64. [Cloudflare Containers pricing](https://developers.cloudflare.com/containers/platform/pricing/) · [Cloud Run container contract](https://docs.cloud.google.com/run/docs/container-contract)
- OCI Always Free A1 supports Linux ARM and eligible block storage. It is a VM and Oracle may reclaim idle instances. It falls outside the no-VPS migration requirement. [OCI Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)

No reviewed destination meets the current production requirements. The existing VPS remains the Telegram poller. A complete cutover also depends on a verified source acceptance ledger and a compatible, authorized ARM64 export path.
