# Managed runtime pilot (v0.2)

The v0.2 pilot was still a draft on 2026-11-25. The VPS remains the production controller. The [latest managed contracts](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45663099506) passed native ARM64 image builds, independent import and volume checks. The owner requires zero cost. See [the project status](PROJECT-STATUS.md) and [zero-cost constraints](ZERO-COST.md).

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
