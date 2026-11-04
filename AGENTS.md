# Project constraints

- All project compilation, tests, validation and execution MUST run on GitHub-hosted Actions runners only.
- Never build, install project dependencies, run project code or deploy on the user's Debian server or this workspace.
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

- The user explicitly resumed Telegram integration on 2026-11-04. Implement bounded GitHub-hosted bot sessions and verified private delivery; this does not authorize server execution or permanent Actions hosting.

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
