# Managed runtime pilot (v0.2 phase 1)

Status: implementation candidate; not a production deployment. No provider, credentials, or billing are configured by this change. The owner requires zero cost; the container image builds are retained for testing, not as approval to provision paid compute. See [zero-cost constraints](ZERO-COST.md).

The Linux controller can run as a single non-root managed container without SSH or systemd. The existing systemd path remains the default. A managed container is **not** a scale-to-zero Worker: it needs continuous availability for Telegram polling, persistent private storage and enough disk for local file handling. Use a provider that permits this workload and supports the required memory, storage, and private networking. Do not use GitHub Actions as a permanent service host. Use only authorized inputs and distribution.

## Runtime prerequisites

- A CI-verified controller bundle built from the matching source commit; alpha.5 predates this mode.
- Linux amd64, one replica, UID/GID 10001, at least 2 GiB memory and a private volume with sufficient free space (existing delivery guard: at least 8,147,483,648 bytes). Mount at /var/lib/ipazake, owned by UID 10001, mode 0700. Use stop-before-start deployments, not rolling replicas.
- Inject the existing six credentials via the provider's private environment settings: TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID, TELEGRAM_API_ID, TELEGRAM_API_HASH, DELIVERY_AGE_IDENTITY, GH_TOKEN. Do not add them to Docker build args, files in the build context, logs or image layers.
- No public listening port is required for the controller. Local Bot API stays on loopback. Keep restart and encrypted backups at the platform level.
- The production worker and its prerequisites remain unchanged. This change does not approve using GitHub-hosted runners as permanent production hosting.

## Build and validation

The existing vps-release workflow validates the container using the exact assembled package before publishing the bundle. The PR workflow runs synthetic credential/volume/journal tests. Neither requires real credentials or sends files. The current vps-release workflow builds only on main; a branch PR does not produce a verified release bundle.

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

The managed-runtime-contracts workflow now produces two Linux amd64 images from an isolated public build context only, after synthetic contracts. Both images use UID/GID 10001 and fail without a private persistent volume. The artifact contains Docker image archives and checksums, not an automatic registry push or provider deployment. Verify SHA256SUMS and exact source, then publish to an approved private registry from a trusted environment. Deploy by immutable image digest. The state image uses a separate entrypoint and provides a minimal /healthz endpoint; its data operations still require the independent state token.

The earlier paid Render Blueprint proposal is withdrawn because the owner requires zero recurring and overage charges. The deployable paid example has been removed from this branch. No provider deployment is approved. See [zero-cost constraints](ZERO-COST.md).

An optional Cloudflare Worker in deploy/managed/cloudflare is an edge HTTPS relay, not a replacement for the state database, Telegram controller or large-file sender. Configure separate random EDGE_TOKEN and ORIGIN_TOKEN as Secrets (ORIGIN_TOKEN matches the state service token), and STATE_ORIGIN as the approved HTTPS origin Secret. The worker permits only four bounded POST routes, does not forward caller headers, follows no redirects, caches no results, and makes a single upstream call. The default Wrangler config has no public routes or workers.dev endpoint: configure the intended custom domain or route and ingress rules explicitly. Disable origin/proxy authorization/body logging and retries. The origin must still authenticate requests; never rely solely on the edge. The caller's TF_STATE_API_TOKEN would be EDGE_TOKEN rather than the origin token if the relay is deployed. No Cloudflare account access or deploy is attempted by CI.

Migration check: tools/managed_migration.py compares a frozen source snapshot with two independently prepared offline destination roots, verifying private file modes, SQLite quick_check, absence of database sidecars, no pending/sending task records, byte-identical controller DB, TF return ledger, acceptance ledger, ciphertext and persistent Telegram files. It prints only a fixed match/failure status. It does not copy data, generate secrets, or certify provider behavior. Do not run on live databases. First stop all relevant writers at an approved idle cutover, safely checkpoint and snapshot on the approved infrastructure, and preserve rollback data. Never reset or fabricate a ledger to satisfy this check; unresolved work requires explicit reconciliation. Keep the existing pilot TF gate until an end-to-end approved state migration and integration are proven.

Official provider references: https://render.com/docs/blueprint-spec and https://render.com/docs/disks ; https://developers.cloudflare.com/workers/wrangler/configuration/ . Provider configuration is a candidate, not an operational deployment.
