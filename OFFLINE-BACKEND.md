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

The upstream acquisition route starts with an enrolled Mac, not the user's personal phone. Using a Mac outside GitHub would change the current execution constraint. This does not establish that native enrollment inside a GitHub-hosted Mac is impossible: that path is now under direct investigation below. No external-machine execution, collection or model recovery was performed.

Before a future real offline trial, require all of the following:

1. A private model recovered from the matching enrollment, or a complete matching private capture from which the pinned recovery implementation can derive it.
2. A matched installed-app/IPA control for initial recovery; the same Apple account name alone is not a match proof.
3. Storage of the model as a secret rather than a repository file, public issue, chat attachment or Actions artifact. A capture is not the model and cannot be pasted into FAIRPLAY_MODEL_B64.
4. Verification against the actual target IPA, with complete encrypted-image counts and applicable page hashes. A mismatch or missing hash coverage remains a failure/unverified result in this adapter.

A successful future model recovery would remove one prerequisite; it would not itself establish Telegram delivery, payment integration, installation support or production readiness.

## GitHub-only native enrollment trial

Current user direction: continue researching enrollment entirely within GitHub-hosted Actions. Do not start Telegram integration or assume permission to use a separate Mac or personal phone.

This experiment uses the real App Store application on a disposable hosted Mac. It is separate from the already-working Swift download-client login.

### Evidence

- [Initial environment run](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41740575162), commit feed2cd03b1bced37e67d6c7a4528d2f7c9ec1a7: both macos-15 and macos-26 arm64 had a console user session, native App Store and Accessibility trust. Both could launch App Store.
- [Account-free login-form run](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41742100267), commit 89d378f381662a278aa282cbf097f48f47c8c0e0: on macos-15, two first-launch introduction actions enabled Sign In. Pressing the actual enabled control exposed one identified email/phone field. Search fields are counted separately from identified credential fields. This run supplied no account credentials.
- [Report-contract and form regression run](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41742741424), commit dbdba2e52bbc2826f912ff0091de1ff100242f3c: six synthetic tests passed and the account-free form path reproduced.
- [Native account trial with terminal-state diagnostics](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41743132997), commit 4c1cc4ee726558752fb081600d6ae7e4973ecad2: eight diagnostic tests and native Swift compilation passed. The native UI accepted field entry and submit actions for the configured email and password, then displayed text matching the fixed unknown_error classification. The helper returned native_login_rejected. Sign Out was not enabled; email and secure-password fields remained visible. The workflow correctly failed at the login step.

The final trial's privileged metadata checks reported not_found before and after login for these exact paths:
- /private/var/db/fpsd/SC Info/SC Info.sidb
- /private/var/db/fpsd/SC Info/SC Info.sids
- /Users/Shared/SC Info/SC Info.sidb

Those checks distinguish missing paths from inaccessible paths. They do not search every possible enrollment location, read file contents, prove that a nonempty file would be a usable model, or derive any model.

No verification-code or optional account-security-upgrade prompt was detected in this trial. No upgrade was enabled. This observation does not establish the account's general 2FA configuration and does not identify the cause of Apple's generic error.

### Interpretation and next research boundary

A graphical session and UI automation are available on GitHub-hosted Macs; an external Mac is not established as a necessary prerequisite merely because the work needs native App Store UI. The current tested macos-15 route instead stops at native authentication. macos-26 was probed without credentials and has not passed the corresponding form or login test.

The underlying authentication error domain/code and rejection cause remain unknown. Do not equate the generic error with a wrong password, enabled 2FA, a mandatory security upgrade, or definitive virtual-machine exclusion. The previously successful download-client session does not establish native App Store enrollment.

Further work needs evidence about that native rejection or a working enrollment protocol, rather than another unchanged login/remap retry. No real IPA decryption or portable enrollment model was produced in these experiments.

### Implementation boundaries

- tools/EnrollmentEnvironment.swift uses bounded Accessibility traversal and only recognized controls. It never treats an enabled ancestor Store menu as an enabled Sign In action.
- The account-free workflow supplies no Apple secrets. The separate login workflow supplies the existing secrets only to its final step and checks diagnostic tests before that step.
- The helper submits credentials at most once per form stage and stops on detected rejection or verification challenges. Optional security-upgrade handling only chooses explicit decline/other-options controls.
- tools/enrollment_environment.py discards raw native output. Published fields are fixed statuses, bounded counts, known error categories and path visibility. Credential values, account identifiers, screenshots and native error text are not published.
- UI indications never set enrollment_created or decryption_proven to true. The login workflow returns nonzero for unresolved/rejected authentication even when the native probe itself exits normally.
- No artifacts, real IPA files or models are uploaded. The hosted VM is discarded after the job.
