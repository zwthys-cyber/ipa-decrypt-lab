# Native download investigation — 2026-11-03

> 文档范围更新（2026-11-27）：本页在main保留旧代码/研究/发行历史。当前生产处理源码来自upgrade/managed-runtime-v0.2，已切换Cloudflare/D1 + CircleCI ARM64 + 私有Drive；main仍用于账号维护和旧Intel发行。[当前同名文档](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/NATIVE-DOWNLOAD-RESULTS.md) · [运行手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md) · [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。不要按历史VPS说明重启旧poller或重新启用5个退休派发工作流。


> Documentation review — 2026-11-09: This document preserves historical experiments and their original results. Current App Store and owner-only TestFlight automation, the CapyPlayer plaintext proof/user receipt, and Beta filename deployment are recorded in [project status](docs/PROJECT-STATUS.md). Current packages and exact build provenance are listed in [release documentation](docs/RELEASES.md); see the [documentation index](docs/DOCUMENTATION.md) for operations. Historical failures do not supersede later verified results. Installation/runtime and universal app compatibility remain unverified.


This document records the original download investigation. The later model-based decryption path is documented in [project status](docs/PROJECT-STATUS.md).

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

## Account history

App 6599842047 had not been downloaded with the test account before the trial. Purchase failure 5002 was not treated as evidence of prior ownership. The trial treats that response as unconfirmed, continues with an authenticated download request, and requires a matching app/bundle/version response. This does not establish whether the account had a license before the trial.

## Earlier failures, retained as history

- Run 41731927872: legacy product requests returned HTTP statuses 200 then 403.
- Run 41732909908: unconditional free-license acquisition stopped on failureType 5002.
- Those earlier results do not describe the latest ent/download implementation.
- Generic BadLogin/5002/403 responses never established a two-factor requirement.

## Change that enabled the successful trial

The pinned ipatool implementation uses the bag-advertised ent/download endpoint with account/device-bound kbsync. The Swift client now preserves the full storefront header and uses that endpoint with the same authenticated session. Token-bearing requests reject redirects and non-allowlisted destinations. A bounded helper uses pinned, checksum-verified Apple assets; private helper input/output travels through pipes.

## Decryption work that remained at this stage

The mremap_encrypted approach has now failed on a real authorized original IPA in the hosted environment. The upstream StoreAgent decryption code examined in ipatool handles macOS package streams using dpInfo and validates XAR packages; it is not evidence of support for encrypted iOS Mach-O slices. Do not transplant it as if it were a working iOS decryptor, or clear cryptid to manufacture success.

At this point the downloader worked, but the decryption path was not yet verified. Later results are in the project status linked above.
