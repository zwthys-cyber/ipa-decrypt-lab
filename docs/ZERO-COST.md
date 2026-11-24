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
