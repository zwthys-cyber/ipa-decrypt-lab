# Offline decryption backend

## What is wired

The manual native-store workflow now offers:
- native: original download plus the existing macOS syscall diagnosis.
- offline: original download plus the pinned UnfairPlay verify command.

Offline verification requires a private enrollment model supplied as FAIRPLAY_MODEL_B64 (strict base64, decoded size at most 32 KiB). It is not an Apple ID password, password token, SINF, kbsync blob, or the separate 16-byte credential format. A missing model stops the offline workflow before building dependencies, logging in, or downloading an IPA.

The adapter writes the model to a private temporary file with mode 0600, strips Apple credentials from the verifier environment, captures all raw output, and exposes only a fixed status and non-identifying counts. UnfairPlay's verify command temporarily processes the IPA and deletes its plaintext. Temporary children remain under the wrapper's private directory.

A zero exit code or cryptid=0 is not enough. Success requires the expected report schema, an exact encrypted-slice count match, a positive page count, and plaintext_verified=true. Upstream validates all available CodeDirectory pre-encryption page hashes; missing coverage is reported unverified. These hashes establish consistency, not independent Apple CMS trust or successful installation/runtime behavior.

No account, model, real IPA or decrypted artifact is used in offline-engine.yml. Its build and test success is synthetic evidence only.

## Credential prerequisite remains unresolved

The user states target app 6599842047 had not previously been downloaded. Generic purchase 5002 remains unconfirmed rather than proof of ownership.

Source review:
- EthanArbuckle/fairplay-decrypt bb09a61046f5c99eb1795589a307646df04b26d0 performs Python offline decryption with an account-matching 16-byte credential. Its documented acquisition uses a supported jailbroken device.
- londek/ipadecrypt similarly requires one-time credential minting per account, even though everyday decryption is offline.
- DrWhax/unfairplay 26a099fcb2292eaacd9e0ce89793cdbc88e516d1 can decrypt on Linux after a model has been recovered. Its documented setup requires an enrolled native Mac App Store state and matching installed app/IPA.
- The pinned ipatool kbsync helper used here does not create that enrollment state: the examined shim only opens CoreFP.icxs and rejects other open requests. API login and kbsync generation do not constitute enrollment-model recovery.

There is no matching private model configured in this repository at the time of this implementation. This update does not claim to have recovered one, and does not perform a new failed remap experiment. The user's personal phone and Debian server are not used.

## Verified CI result

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41737576446 completed successfully on commit 0d659ffb969370f8189b0f107075bb64dc8402e3.

- Linux x86_64 engine compilation passed.
- Upstream internal/fairplay and cmd/unfairplay tests passed, including synthetic wrong-page-key rejection and pre-encryption hash checks.
- 52 Python tests passed, including missing-model early exit, full encrypted-image coverage requirements, private model permissions, environment filtering and cleanup.
- The no-model probe returned missing_enrollment_model, with decryption_proven=false, plaintext_verified=false and runtime_verified=false.
- No Apple login, real IPA, enrollment collection or private-model recovery occurred in this run.

The engine compilation and adapter are verified under these synthetic conditions; real offline decryption remains gated on matching enrollment material. No paid Telegram decryption service is ready.

## Pinned engine and notices

DrWhax/unfairplay: https://github.com/DrWhax/unfairplay/tree/26a099fcb2292eaacd9e0ce89793cdbc88e516d1
Engine license: https://github.com/DrWhax/unfairplay/blob/26a099fcb2292eaacd9e0ce89793cdbc88e516d1/LICENSE
Third-party notices: https://github.com/DrWhax/unfairplay/blob/26a099fcb2292eaacd9e0ce89793cdbc88e516d1/NOTICE
The engine source and dependencies are checked out and compiled only in GitHub-hosted Actions. Any future distribution must retain the applicable upstream notices.

Other sources:
- https://github.com/EthanArbuckle/fairplay-decrypt/blob/bb09a61046f5c99eb1795589a307646df04b26d0/README.md
- https://github.com/EthanArbuckle/fairplay-decrypt/blob/bb09a61046f5c99eb1795589a307646df04b26d0/credential-retrieval/README.md
- https://github.com/londek/ipadecrypt
- https://github.com/majd/ipatool/blob/d9c0247daea564d3ec7d04a9b015d0a29af66b04/internal/sap/machine/shim_platform.go

## Enrollment bootstrap source review

This review concerns the pinned implementations, not a claim that a new protocol implementation is impossible.

- [UnfairPlay recovery](https://github.com/DrWhax/unfairplay/blob/26a099fcb2292eaacd9e0ce89793cdbc88e516d1/internal/recovery/recover.go) consumes captured SIDB, SINF, SUPF and hardware inputs. It derives a model from existing state; it does not create a new Apple enrollment.
- [Capture normalization](https://github.com/DrWhax/unfairplay/blob/26a099fcb2292eaacd9e0ce89793cdbc88e516d1/internal/fairplay/enrollment_normalize.go) explicitly requires a verified six-byte hardware identity, an installed SINF, valid SUPF/SUPP and SIDB state. Providing a downloaded SINF alone does not satisfy this contract.
- [The kbsync generator](https://github.com/majd/ipatool/blob/d9c0247daea564d3ec7d04a9b015d0a29af66b04/internal/sap/machine/kbsync.go) explicitly generates download data without opening a decryption session.
- [The emulated account framework](https://github.com/majd/ipatool/blob/d9c0247daea564d3ec7d04a9b015d0a29af66b04/internal/store/emulator/accounts.go) keeps ephemeral values without host account-store or keychain writes. [The session path](https://github.com/majd/ipatool/blob/d9c0247daea564d3ec7d04a9b015d0a29af66b04/internal/store/emulator/session.go) constructs an ephemeral account; successful API authentication is not evidence of native enrollment.
- The existence of an authorizeMachine URL or experimental HTTP request code is not evidence that a reusable decryption model has been produced. No such working bootstrap was established in this review.

The documented acquisition route starts with an enrolled project-owned Mac; it does not require using the user's personal phone. It would nevertheless require a change to the current GitHub-only execution constraint, so no collection or external-machine execution was performed. No model was generated and no new real decryption run was claimed.

Before a future real offline trial, require all of the following:

1. A private model recovered from the matching enrollment, or a complete matching private capture from which the pinned recovery implementation can derive it.
2. A matched installed-app/IPA control for initial recovery; the same Apple account name alone is not a match proof.
3. Storage of the model as a secret rather than a repository file, public issue, chat attachment or Actions artifact. A capture is not the model and cannot be pasted into FAIRPLAY_MODEL_B64.
4. Verification against the actual target IPA, with complete encrypted-image counts and applicable page hashes. A mismatch or missing hash coverage remains a failure/unverified result in this adapter.

A successful future model recovery would remove one prerequisite; it would not itself establish Telegram delivery, payment integration, installation support or production readiness.
