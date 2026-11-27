# Account-authorized ent/download trial

> 文档范围更新（2026-11-27）：本页在main保留旧代码/研究/发行历史。当前生产处理源码来自upgrade/managed-runtime-v0.2，已切换Cloudflare/D1 + CircleCI ARM64 + 私有Drive；main仍用于账号维护和旧Intel发行。[当前对应说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/DOWNLOADER.md) · [运行手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md) · [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。不要按历史VPS说明重启旧poller或重新启用5个退休派发工作流。


> Documentation review — 2026-11-09: This document preserves historical experiments and their original results. Current App Store and owner-only TestFlight automation, the CapyPlayer plaintext proof/user receipt, and Beta filename deployment are recorded in [project status](docs/PROJECT-STATUS.md). Current packages and exact build provenance are listed in [release documentation](docs/RELEASES.md); see the [documentation index](docs/DOCUMENTATION.md) for operations. Historical failures do not supersede later verified results. Installation/runtime and universal app compatibility remain unverified.


This note covers the initial download investigation. For the working pipeline and current limits, see [project status](docs/PROJECT-STATUS.md).

App 6599842047 had not been downloaded with the test account before the trial. Purchase failure 5002 must remain unconfirmed, not be called proof of ownership. The client permits an authenticated download request after that specific ambiguous purchase response; it does not manufacture or bypass an entitlement.

Pinned ipatool d9c0247daea564d3ec7d04a9b015d0a29af66b04 implements ent/download with account/device-bound kbsync. The Swift client now discovers that endpoint from Apple's bag, preserves the original storefront header, and uses the existing session. A bounded Go helper builds the blob using upstream checksum-verified Apple assets. Raw helper data and session secrets are confined to pipes and the disposable runner.

Token-bearing requests reject redirects and non-allowlisted endpoints. Response app ID, bundle ID and version must match before normal IPA acquisition. Tests use synthetic data; all builds/tests run on GitHub. This is not proof of successful download or decryption until the actual trial completes.
