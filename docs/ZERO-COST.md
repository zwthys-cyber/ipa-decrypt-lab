# Zero-cost deployment constraints

Owner requirement (2026-11-24): no paid VPS, no paid subscriptions or metered overage charges. No automatic provisioning or upgrade to a paid plan. A trial or expiring promotional credit is not a durable zero-cost solution. An estimated bill of zero is not a hard spending limit.

## Available free control-plane candidates

- Cloudflare Workers Free: suitable for small event-driven requests; currently 100,000 requests/day, 10 ms CPU per HTTP invocation and 128 MB memory. Not a native Linux container or macOS runtime.
- D1 Free: candidate for transactional task records and small encrypted state, with free quota limits and errors rather than a plan upgrade. Its row size and database capacity are not suitable for storing large IPA archives. A SQLite-to-D1 migration must preserve identities, idempotency, unknown outcomes and history. Not yet implemented.
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
