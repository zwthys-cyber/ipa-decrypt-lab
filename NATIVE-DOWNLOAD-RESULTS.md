# Native download investigation — 2026-11-03

All builds, tests and account requests ran on GitHub-hosted macOS runners.

## Verified results

- Authentication repeatedly completed without an OTP or security upgrade.
- App lookup and platform version lookup completed.
- Run 41731927872 reached product requests: HTTP statuses 200 then 403. No IPA was downloaded. The stage parse_product refers to the last stage reached before the subsequent HTTP rejection, not proof of a plist decoding failure.
- A trial that explicitly acquires the verified zero-price app before download failed at acquire_free_license.
- Run 41732909908 extracted Apple failureType 5002 from that purchase failure.
- 5002 and HTTP 403 do not establish that two-factor authentication is enabled, nor do they establish a specific underlying cause.
- Native compilation, signing request tests and Python tests passed on the final diagnostic runs. No decryption of a real app has been demonstrated.

## Current implementation

tools/patch_swift_diagnostics.py instruments fixed progress markers and bounded numerical HTTP/error codes. tools/native_store.py captures raw child output privately and only publishes allowlisted diagnostics. Markers are excluded from error classification. Account credentials, response contents, signed URLs, sessions and IPA files are not published.

The manual workflow caches only upstream .build, saving it before supplying Apple credentials. Tests run before native compilation. This remains a research workflow, not a production Telegram service.

## Unresolved

The Apple free-license request is rejected with 5002 and the fallback download route returns 403. Investigate the authenticated purchase/download request protocol and response classification before additional repeated account requests. Do not label these generic failures as an OTP requirement, disable TLS validation, accept security upgrades automatically, or claim success from clearing cryptid.

Evidence:
- https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41731927872
- https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41732909908
