# Managed runtime pilot (v0.2 phase 1)

Status: implementation candidate; not a production deployment. No provider, credentials, or billing are configured by this change.

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
