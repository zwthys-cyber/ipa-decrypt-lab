# Project constraints

- All project compilation, tests, validation and execution MUST run on GitHub-hosted Actions runners only.
- Never build, install project dependencies, run project code or deploy on the user's Debian server or this workspace.
- Edit source through GitHub APIs. Do not create local project checkouts or build caches.
- Do not use the user's personal iPhone or TrollStore installation as infrastructure.
- No third-party decryption services unless the user changes scope explicitly.
- Never commit or upload Apple credentials, account keys, Telegram tokens, provisioning profiles or third-party IPA files to this public repository or public Actions artifacts/logs.
- Synthetic fixtures are the default. CI success proves compilation and fixture behavior, not successful App Store decryption.
- Keep research results candid: missing credentials/platform support must fail explicitly; never clear cryptid to pretend decryption succeeded.
- Pin action revisions; use read-only workflow permissions, bounded timeouts and short artifact retention.
- GitHub Actions is a bounded build/research environment, not permanent production hosting.

- The account owner declines the optional two-factor security upgrade. Never enable or accept that upgrade automatically.
- Do not infer an enabled two-factor setting or a definite verification challenge from MZFinance.BadLogin.Configurator_message. Treat it as ambiguous until stronger response evidence is available.
