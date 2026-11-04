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

The first trial did not expose an error domain/code. The bounded diagnostic follow-up below now records AuthKit errors on Intel, but the rejection cause remains unresolved. Do not equate the generic UI error or these codes with a wrong password, enabled 2FA, a mandatory security upgrade, or definitive virtual-machine exclusion. The previously successful download-client session does not establish native App Store enrollment.

Further work needs evidence about that native rejection or a working enrollment protocol, rather than another unchanged login/remap retry. No real IPA decryption or portable enrollment model was produced in these experiments.

### Implementation boundaries

- tools/EnrollmentEnvironment.swift uses bounded Accessibility traversal and only recognized controls. It never treats an enabled ancestor Store menu as an enabled Sign In action.
- The account-free workflow supplies no Apple secrets. The separate login workflow supplies the existing secrets only to its final step and checks diagnostic tests before that step.
- The helper submits credentials at most once per form stage and stops on detected rejection or verification challenges. Optional security-upgrade handling only chooses explicit decline/other-options controls.
- tools/enrollment_environment.py discards raw native output. Published fields are fixed statuses, bounded counts, known error categories and path visibility. Credential values, account identifiers, screenshots and native error text are not published.
- UI indications never set enrollment_created or decryption_proven to true. The login workflow returns nonzero for unresolved/rejected authentication even when the native probe itself exits normally.
- No artifacts, real IPA files or models are uploaded. The hosted VM is discarded after the job.


## Bounded error diagnostics and Intel comparison (2026-11-04)

### Completed runs

| Run / commit | Hosted runner | Checks | Authentication and model result |
| --- | --- | --- | --- |
| [41744985165](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41744985165) / 9e1e6f3f758da2d29705f9b554a938288f67273b | macos-15, arm64 | 10 UI-report tests + 8 diagnostic tests passed; log preflight and Swift compilation passed | Native login rejected with unknown_error. The unfiltered process log exceeded 8 MiB; its raw bytes were discarded, so this run establishes no underlying error code. |
| [41745356356](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41745356356) / 32313fd76707ea70b147b7875096f16262fb8767 | macos-15-intel, x86_64 | Same 18 tests, source-filtered log preflight and native compilation passed | Native login rejected with unknown_error; bounded log capture succeeded. No enrollment model recovered. |

Both trials submitted the configured email and password through the native form. Both left email and password fields visible with Sign Out disabled. Neither detected a verification-code or optional security-upgrade prompt, and neither accepted an upgrade. Privileged metadata checks returned not_found before and after for all three previously listed SIDB/SIDS paths.

The Intel run examined 184 filtered events and produced 15 aggregate records without hitting output, event or record limits. Its allowlisted error-code observations include:

| Process | Domain / code | Events | Authentication words in the same event |
| --- | --- | --- | --- |
| akd | AKAuthenticationError -7018 | 1 | yes |
| akd | AKAuthenticationError -7012 | 1 | yes |
| akd | AKAuthenticationError -7066 | 16 | no |
| akd | AKAuthenticationError -7044 / -7023 / -7010 | 2 / 6 / 5 | no |
| akd | NSOSStatusErrorDomain -25300 | 4 | no |
| App Store | AMSErrorDomain 12 | 5 | no |

HTTP 200 and 304 observations from the same window are not authentication-success evidence. Other background errors also occurred. The authentication_context field is a lexical classification of a log message, not proof of causality or a distinct successful authentication transaction.

The collection window covers helper launch through termination and final metadata checks, including App Store introductions, unrelated background requests and cleanup. Consequently -7012 or other codes could describe secondary/cancellation events. No temporal ordering, underlying-error relationship, server payload or specific failure reason is established by the aggregate report. Unknown error domains and all raw descriptions are deliberately dropped. Future causal diagnosis should narrow to the credential-submission window and classify the underlying AuthKit failure before another account trial; it should not infer the cause from the mere presence of a code.

### Platform evidence and limits

[Apple's virtual-machine support article](https://support.apple.com/en-asia/120468) lists Apple Media Services, including apps, among unavailable VM features. [Parallels' July 2026 support article](https://kb.parallels.com/en/131160) explicitly says native Mac App Store sign-in remains unsupported in Apple Silicon VMs even with macOS 15+, and distinguishes Intel virtualization from that framework-specific restriction. [GitHub's runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) lists both macos-15 and macos-15-intel as hosted VM options.

These sources motivated a single Intel comparison. They do not prove that every custom Store protocol is impossible, and the repository's earlier signed download-client success remains valid. Conversely, the Intel failure does not establish a universal Intel restriction, while changing architecture alone did not fix this account's tested native route. A successful Intel login would still not prove compatible iOS enrollment or replace the matching installed iOS-app/IPA control required by the pinned recovery engine.

Primary reports give a reason to avoid overinterpreting -7018: [an Apple Developer Forums report](https://developer.apple.com/forums/thread/834106) includes this code in a separate Sign in with Apple failure on physical devices. That is a different API and is not a diagnosis of this App Store failure. No definitive public mapping for this trial's -7012 or complete underlying rejection chain was established.

The tested GitHub-only native bootstrap remains unsuccessful on both architectures. No portable model, real plaintext verification or paid service was produced. Further work needs a new protocol/state-creation hypothesis or a more specific underlying failure, not an unchanged UI login retry.

### Diagnostic implementation

- tools/native_auth_diagnostics.py reads only a bounded time window from a fixed process set. After the arm64 output-limit failure, the predicate also requires a known error-domain, failureType or HTTP-status term before log serialization.
- The child receives only PATH and LC_ALL, not Apple secrets. It has a 15-second timeout, 8 MiB output cap, 20,000-event cap and 64-record cap. Failed/oversized raw output is discarded.
- Only allowlisted process/domain/symbol names, bounded numeric codes, boolean context and aggregate counts can enter the public report. Raw logs are kept only transiently in runner memory; no file or artifact is created.
- The account workflow tests redaction, limits, timeout behavior, environment isolation and failure reporting before supplying credentials. A log-query preflight must also pass before the account step.
- The login workflow now exposes only the two explicitly permitted GitHub-hosted runner choices, serializes account trials and retains bounded job/step timeouts.
- Compilation and all tests/experiments in this update ran on GitHub. No project build, test, login or execution occurred on the Debian server or editing workspace.
