# CircleCI ARM runtime producer

This is the public, credential-free first stage of the owner's on-demand migration. Existing production remains on the VPS.

Push a commit with `[circleci-runtime-build]` to request a one-off native build, or use the boolean pipeline parameter `build_native_runtime=true`. Without this gate only the existing owned iOS sample is built. The macOS 26 / Xcode 26.5 / M4 Pro Medium job runs Go/Python/Node/Swift checks, builds four pinned public components, verifies ARM64 Mach-O architecture, packages an allowlisted inventory and tests relocation with the Swift build directory hidden. No private context is attached.

Outputs under CircleCI artifacts `public-arm64-native-runtime`:
- `native-runtime.tar.gz`: binaries, public resources, licenses and provenance manifest.
- `build-receipt.json`: sanitized build manifest.

A future consumer must authenticate the successful job through CircleCI, bind its repository, branch, source SHA, job identity and source fingerprint, and independently check the expected toolchain/ABI. A manifest cannot authenticate itself. `runtime.unpack` requires these expected values; the producer's self-check only proves archive integrity/relocation. Consumers must also recheck the current runner ABI before executing these binaries. Never treat the public artifact URL as authorization to restore Apple credentials.

This producer covers the base App Store tool, not the separate CN/TF variants or production task runner. Do not set `GITHUB_ACTIONS=true` on CircleCI to bypass existing runtime/session guards. No new Apple enrollment, session replacement, invitation acceptance or file transmission is part of building this bundle.

Account setup still required for later automated dispatch:
1. On the owner's existing CircleCI account, create a personal API token at https://app.circleci.com/settings/user/tokens .
2. Save it as repository Actions secret `CIRCLECI_API_TOKEN` at https://github.com/zwthys-cyber/ipa-decrypt-lab/settings/secrets/actions/new . Do not send it in chat.
3. Use a separate CI-only provisioning workflow to validate account/project/definition and restricted context before connecting the Worker. Such provisioning and live dispatch are not implemented by this producer.

The connected GitHub App project uses opaque CircleCI slugs, not the legacy `gh/owner/repo` trigger path. See [CircleCI API](https://circleci.com/docs/api/v2/index.html). No token is necessary for the currently configured GitHub push trigger.
