# iOS native decryption follow-up

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

Test results pending the follow-up run. No successful plaintext decryption is claimed.
