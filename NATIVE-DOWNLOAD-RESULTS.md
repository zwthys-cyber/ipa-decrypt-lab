# Native download investigation — 2026-11-03

## Latest verified result: original IPA acquisition works

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41734345727 completed successfully on commit 1b131e6e6a452987febefbf6bbf4f131118d98c0.

- Swift authentication completed without an OTP or accepting the optional security upgrade.
- The authenticated ent/download implementation acquired the requested original IPA.
- Download output passed the upstream package-platform validation and the project's ZIP/Mach-O audit.
- 62 Mach-O binaries / encrypted slices were found.
- The existing macOS mremap_encrypted engine attempted all 62 and rejected all 62.
- candidate_unverified = 0; decryption_proven = false; runtime_verified = false.
- 36 Python tests, 9 selected Swift tests, and the Go helper input tests passed.
- All builds, tests and execution occurred on GitHub-hosted runners. No account, original IPA, candidate, signed URL or session was exported to public artifacts. Temporary IPA and session files were cleaned up.

The workflow's success means acquisition and diagnosis completed; it does not mean successful decryption.

## Owner clarification

The owner explicitly states that target app 6599842047 had not been downloaded with the account. Do not infer prior ownership from purchase failure 5002. The trial treats that response as unconfirmed, continues with an authenticated download request, and requires a matching app/bundle/version response. This does not establish whether the account had a license before the trial.

## Earlier failures, retained as history

- Run 41731927872: legacy product requests returned HTTP statuses 200 then 403.
- Run 41732909908: unconditional free-license acquisition stopped on failureType 5002.
- Those earlier results do not describe the latest ent/download implementation.
- Generic BadLogin/5002/403 responses never established a two-factor requirement.

## Change that enabled the successful trial

The pinned ipatool implementation uses the bag-advertised ent/download endpoint with account/device-bound kbsync. The Swift client now preserves the full storefront header and uses that endpoint with the same authenticated session. Token-bearing requests reject redirects and non-allowlisted destinations. A bounded helper uses pinned, checksum-verified Apple assets; private helper input/output travels through pipes.

## Remaining decryption work

The mremap_encrypted approach has now failed on a real authorized original IPA in the hosted environment. The upstream StoreAgent decryption code examined in ipatool handles macOS package streams using dpInfo and validates XAR packages; it is not evidence of support for encrypted iOS Mach-O slices. Do not transplant it as if it were a working iOS decryptor, or clear cryptid to manufacture success.

This repository is still a research prototype, not a production paid Telegram service.
