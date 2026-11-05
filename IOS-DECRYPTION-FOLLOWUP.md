# iOS native decryption follow-up

These notes cover the native remap investigation. The model-based route was completed later; see [project status](docs/PROJECT-STATUS.md) for the current implementation.

The previous real-package result counted 62 failed engine invocations, not necessarily 62 kernel calls. This follow-up records preflight failures separately from actual mremap_encrypted returns.

Changes:
- Preserve the original IPA. In the private extraction directory only, replicate an existing SINF to validated SinfReplicationPaths from SC_Info/Manifest.plist.
- Refuse traversal, symlinks, conflicting existing files, oversized inputs and ambiguous multiple distinct source licenses. File presence is never proof of authorization.
- Remove the overly strict encrypted-length host-page-multiple check. Retain the aligned-start check and copy only the original encrypted length.
- Record native-call/return events, errno counts, local SINF coverage, host page size and the runtime's virtual-machine indicator. Publish no paths, SINF bytes or account details.

Apple's XNU mremap_encrypted sanitizer requires an aligned start, with the end normalized internally:
https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_mman.c

EPERM may arise while creating the decrypter or mapping protected pages; errno alone cannot identify which of those occurred.

The pinned ApplePackage SignatureInjector only processes SinfPaths:
https://github.com/Lakr233/ApplePackage/blob/391bfe6ee6598d73e4f94b88b38b50bd6f6ec67b/Sources/ApplePackage/Supplement/SignatureInjector.swift

An on-device research implementation describes manifest-driven replication:
https://github.com/morzelowski/FairPlayed/blob/main/embed_ipa.sh

That project requires a physical iPhone; it is not a device-free server solution and is not being deployed here. All work remains on GitHub-hosted runners.

## Actual follow-up result

Commit: 27657d5e69167dd218eebe52a4d197be2afdae41

- Native ARM macOS, Intel macOS and Linux CI passed:
  https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41736203140
- Original downloader's account-free regression workflow passed:
  https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41736203178
- Actual acquisition and diagnosis completed:
  https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41736203256
- 44 Python tests and all four CTest suites passed in the actual trial workflow.
- Original IPA downloaded again.
- 62 manifest replication targets: 61 missing copies created, 1 already present.
- All 62 binaries had a nonempty sibling SINF after staging; 0 missing.
- All 62 attempts reached the native syscall; all returned errno 1 (EPERM).
- 0 candidates; decryption_proven=false; runtime_verified=false.
- Host: arm64, 16384-byte pages, kern.hv_vmm_present=1.

This result rules out missing declared sibling SINF copies and local start-alignment preflight rejection for this sample after staging. It does NOT prove that the system FairPlay service accepted those licenses, that API login initialized the macOS App Store session, or that virtualization alone caused EPERM.

At this stage, the remaining work was an actually compatible iOS FairPlay runtime/authorization path or a separately verified software iOS decryption implementation. Repeating the same remap on this runner, adding a Telegram queue, or clearing cryptid would not resolve or demonstrate decryption. These trials ran on GitHub-hosted runners without a personal phone, VPS execution, or third-party decryption service.
