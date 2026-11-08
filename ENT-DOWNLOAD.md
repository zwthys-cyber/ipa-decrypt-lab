# Account-authorized ent/download trial


> Current-state update — 2026-11-08: The production ent/download path now supplies native Store AMD proofs and preserves the full storefront. The 2026-11-08 X export verified original acquisition and all 32 encrypted images / 86,704 pages. The original trial below retains its own narrower scope. Current packages: [v0.1.0-alpha.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.2). Evidence: [verified X export](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2). Operational documentation: [documentation index](docs/DOCUMENTATION.md).


This note covers the initial download investigation. For the working pipeline and current limits, see [project status](docs/PROJECT-STATUS.md).

App 6599842047 had not been downloaded with the test account before the trial. Purchase failure 5002 must remain unconfirmed, not be called proof of ownership. The client permits an authenticated download request after that specific ambiguous purchase response; it does not manufacture or bypass an entitlement.

Pinned ipatool d9c0247daea564d3ec7d04a9b015d0a29af66b04 implements ent/download with account/device-bound kbsync. The Swift client now discovers that endpoint from Apple's bag, preserves the original storefront header, and uses the existing session. A bounded Go helper builds the blob using upstream checksum-verified Apple assets. Raw helper data and session secrets are confined to pipes and the disposable runner.

Token-bearing requests reject redirects and non-allowlisted endpoints. Response app ID, bundle ID and version must match before normal IPA acquisition. Tests use synthetic data; all builds/tests run on GitHub. This is not proof of successful download or decryption until the actual trial completes.
