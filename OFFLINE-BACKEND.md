# Offline decryption backend

This document contains the detailed research history. For the current workflow and results, see [Project status and usage](docs/PROJECT-STATUS.md). The sections below retain the conclusions available at each stage; later sections may supersede earlier blockers.

## Current verified status (2026-11-04)

**Model recovery on GitHub-hosted macOS passed validation against the complete original IPA.** [Successful bootstrap 41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942) verified 62 encrypted slices and 12,524 plaintext pages. The model and private native-state checkpoint were saved as GitHub Secrets at 14:22:53 UTC; neither plaintext nor a decrypted IPA artifact was published.

The latest measured computer count is 4 of 5. One all-computer deauthorization was performed earlier (5 -> 0); four subsequent controlled enrollments account for the current measurement. The independent cross-runner reuse check [41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) also passed with 62 encrypted slices and 12,524 verified pages, using the stored model and a freshly downloaded IPA. It does not invoke machine authorization.

Real checkpoint replay also passed in [41847775765](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41847775765): a third fresh runner derived a model from the saved SIDB/IOMAC data and verified the complete newly downloaded IPA without invoking enrollment. Installation/runtime behavior, independent Apple CMS trust, other accounts/apps and a production Telegram service remain unverified or out of the current scope. See [the successful recovery record](#first-verified-github-only-model-recovery-2026-11-04) below. Earlier blocker/failed-run sections are historical evidence, not the current outcome.

Private verified IPA export is now also proven in [41856194867](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41856194867): all 62 slices and 12,524 pages passed, Store account metadata was removed, and the 92,118,013-byte output was retained only as age ciphertext with a one-day lifetime. Owner-only Telegram identity round-trip, queue contracts, and [real 92 MB private delivery 41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056) are verified; see [Telegram private delivery tests](docs/TELEGRAM.md) for live delivery evidence and bounded-session operation.

## What is wired

The manual native-store workflow now offers:
- native: original download plus the existing macOS syscall diagnosis.
- offline: original download plus the pinned UnfairPlay verify command.

Offline verification requires a private enrollment model supplied as FAIRPLAY_MODEL_B64 (strict base64, decoded size at most 32 KiB). It is not an Apple ID password, password token, SINF, kbsync blob, or the separate 16-byte credential format. A missing model stops the offline workflow before building dependencies, logging in, or downloading an IPA.

The adapter writes the model to a private temporary file with mode 0600, strips Apple credentials from the verifier environment, captures all raw output, and exposes only a fixed status and non-identifying counts. UnfairPlay's verify command temporarily processes the IPA and deletes its plaintext. Temporary children remain under the wrapper's private directory.

A zero exit code or cryptid=0 is not enough. Success requires the expected report schema, an exact encrypted-slice count match, a positive page count, and plaintext_verified=true. Upstream validates all available CodeDirectory pre-encryption page hashes; missing coverage is reported unverified. These hashes establish consistency, not independent Apple CMS trust or successful installation/runtime behavior.

No account, model, real IPA or decrypted artifact is used in offline-engine.yml. Its build and test success is synthetic evidence only.

## Historical credential prerequisite blocker

App 6599842047 had not previously been downloaded with this account. Generic purchase 5002 remains unconfirmed rather than proof of ownership.

Source review:
- EthanArbuckle/fairplay-decrypt bb09a61046f5c99eb1795589a307646df04b26d0 performs Python offline decryption with an account-matching 16-byte credential. Its documented acquisition uses a supported jailbroken device.
- londek/ipadecrypt similarly requires one-time credential minting per account, even though everyday decryption is offline.
- DrWhax/unfairplay 26a099fcb2292eaacd9e0ce89793cdbc88e516d1 can decrypt on Linux after a model has been recovered. Its documented setup requires an enrolled native Mac App Store state and matching installed app/IPA.
- The pinned ipatool kbsync helper used here does not create that enrollment state: the examined shim only opens CoreFP.icxs and rejects other open requests. API login and kbsync generation do not constitute enrollment-model recovery.

At this earlier implementation stage, no matching private model was configured and no recovery was claimed. That blocker was resolved by the later successful GitHub-only bootstrap recorded above. This stage used neither a personal phone nor the Debian server.

## Historical synthetic CI baseline

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41737576446 completed successfully on commit 0d659ffb969370f8189b0f107075bb64dc8402e3.

- Linux x86_64 engine compilation passed.
- Upstream internal/fairplay and cmd/unfairplay tests passed, including synthetic wrong-page-key rejection and pre-encryption hash checks.
- 52 Python tests passed, including missing-model early exit, full encrypted-image coverage requirements, private model permissions, environment filtering and cleanup.
- The no-model probe returned missing_enrollment_model, with decryption_proven=false, plaintext_verified=false and runtime_verified=false.
- No Apple login, real IPA, enrollment collection or private-model recovery occurred in this run.

That baseline established compilation and synthetic adapter behavior only. Later real-model and complete IPA evidence is recorded in the current-status section. No paid Telegram service has been deployed.

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

The upstream acquisition route starts with an enrolled Mac, not a personal phone. Using a Mac outside GitHub would change the current execution constraint. This does not establish that native enrollment inside a GitHub-hosted Mac is impossible: that path is now under direct investigation below. No external-machine execution, collection or model recovery was performed.

Before a future real offline trial, require all of the following:

1. A private model recovered from the matching enrollment, or a complete matching private capture from which the pinned recovery implementation can derive it.
2. A matched installed-app/IPA control for initial recovery; the same Apple account name alone is not a match proof.
3. Storage of the model as a secret rather than a repository file, public issue, chat attachment or Actions artifact. A capture is not the model and cannot be pasted into FAIRPLAY_MODEL_B64.
4. Verification against the actual target IPA, with complete encrypted-image counts and applicable page hashes. A mismatch or missing hash coverage remains a failure/unverified result in this adapter.

A successful future model recovery would remove one prerequisite; it would not itself establish Telegram delivery, payment integration, installation support or production readiness.

## GitHub-only native enrollment trial

Direction during this historical trial: research enrollment entirely within GitHub-hosted Actions and defer Telegram. Administrator-only Telegram integration resumed on 2026-11-04; GitHub-only execution and the personal-phone restriction continue to apply.

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


## Isolated authentication failure and independent Anisette prerequisite (2026-11-04)

### Narrowed native diagnostic

[Run 41746379142](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41746379142), commit 9c60beb11d31a51e64b799b872d269234ac12758, ran on macos-15-intel. Twelve report/window tests, eleven diagnostic tests, log preflight and native Swift compilation passed. The account login still failed.

The helper now marks the interval immediately before the first credential submission until its terminal UI observation. It rounds the upper bound to a whole second and waits beyond that bound before closing App Store. The Python wrapper requires that both private timestamps lie inside the child execution and that the interval is at most 180 seconds. Invalid/missing intervals, including helper timeouts, do not fall back to unrelated background logs. Timestamps and raw log messages are never published.

This run's 14-second interval yielded 67 filtered events without truncation. It observed:

- AKAnisetteError -8025 together with AKUnderlyingADIErrors -45061 and the fixed anisette_fetch_failed phrase classification.
- AKAnisetteError -8008 with anisette_provisioning_failed.
- AKAuthenticationError -7018 together with AKAnisetteError -8008 and -8001 in one error event.
- A separate event containing -8008/-8001 and server_authentication_failed.
- AKAuthenticationError -7066 with com.apple.devicecheck.error.baa -10000 and attestation_headers_failed, plus separate device_identity_unavailable events.
- AKAuthenticationServerError -22410 together with AKAuthenticationError -7010.

This is direct evidence of an Anisette acquisition/provisioning failure during the tested native authentication. It is more specific than the generic UI error. Co-occurrence records identify codes and fixed phrases within the same event; they do not reconstruct every nested error relationship or prove that device attestation is the sole root cause.

-7012 also occurred inside the new interval, so it cannot be attributed solely to the helper closing App Store afterward. No reliable standalone semantic mapping was established. Neither selected_protocol_missing nor srp_server_proof_missing was observed in this run. It would be incorrect to import those explanations from unrelated public -7018 reports.

The UI again showed unknown_error, with no detected OTP or optional security-upgrade prompt. All three privileged SIDB/SIDS checks remained not_found. No model or plaintext was produced.

### Independent prerequisite experiment

Anisette data is a device-authentication prerequisite. It is not the FairPlay enrollment model, SIDB, SINF, or the account's reusable app-decryption credential.

To test the newly identified dependency without another account login, the repository adds an isolated experiment using [malmeloo/Anisette.py at a61cddfb2275187822ad0c3999af747b8c9a4f9a](https://github.com/malmeloo/Anisette.py/tree/a61cddfb2275187822ad0c3999af747b8c9a4f9a). Its source and frozen dependency lock are installed only on the GitHub runner. The [upstream MIT notice](https://github.com/malmeloo/Anisette.py/blob/a61cddfb2275187822ad0c3999af747b8c9a4f9a/LICENSE) remains in the checkout; this repository does not redistribute its binaries or Apple's libraries.

The wrapper supplies an explicit local Apple Music APK, downloaded directly from Apple's public apps.mzstatic.com endpoint, instead of using the provider's default third-party library-bundle endpoint. Provisioning requests are limited to Apple HTTPS domains, without redirects, with request/body/time limits and normal TLS verification. There is no external Anisette service. The official APK URL is mutable; each run records its public SHA-256 as provenance, rather than claiming that the Apple library build is pinned by that URL.

[Linux run 41747047524](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41747047524), commit 8f3ec9f606c323b7660a0235d4b8e7b40ee51087, completed successfully:

- Seven contract tests passed.
- Dependency installation used the upstream frozen lock and uv 0.9.13.
- Three Apple provisioning requests completed.
- The provider reported provisioned state and produced all required headers with bounded structure/base64 checks.
- Saving the full private state to memory, reloading it and generating headers again succeeded; the machine-ID header remained identical within that session.
- apple_login_attempted, native_state_imported, enrollment_created and decryption_proven all remained false.

Public APK SHA-256 observed: 9aab4e3bfd44b509dd657b030d46df536c5592512c256fc59012cce47a2e9c9c.

The result establishes independent Anisette initialization and reuse on that runner. It does not establish acceptance of those headers by an account-authentication endpoint, compatibility with native macOS ADI storage, successful native App Store login, or a reusable FairPlay model. No state or header values leave the worker. The synthetic state-persistence test and the real provider test both require reload success before reporting complete.

### Hosted Apple Silicon confirmation

[Mac run 41747343222](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41747343222), commit c0f39ed8e7e49d80bcb754fbdaf5de7be9dd0c87, repeated the same account-free prerequisite on macos-15 arm64. Seven contract tests, native metadata helper compilation and dependency installation passed. Three Apple provisioning requests again produced structurally valid headers and reloadable private state, with a stable machine-ID header after reload. The public APK hash matched the Linux run. No account was supplied or authenticated.

The native metadata probe loaded AuthKit and observed these current selectors:

- AKAppleIDAuthenticationContext: setAnisetteDataProvider:, anisetteDataProvider, setProxiedDeviceAnisetteData:, setCompanionDeviceAnisetteData:, _setPassword:, setUsername:, and the queried controls for ephemeral operation, login-attempt limit and optional security-upgrade handling.
- AKAnisetteData: setters for machine ID, one-time password and routing information.
- AKAppleIDAuthenticationController: authenticateWithContext:completion: and updateStateWithExternalAuthenticationResponse:forContext:completion:.

However, objc_getProtocol("AKAnisetteServiceProtocol") returned no registered protocol. This only concerns that name in the loaded client process; it does not prove that custom providers are unavailable. The runtime presence of the context setter is a concrete integration lead, while the current provider/daemon callback contract and permissions remain unverified. No provider was installed, no account was created, and no authentication method was invoked in this metadata probe.

### Integration boundary

The obsolete mas sign-in command is not a verified shortcut: [mas issue 164](https://github.com/mas-cli/mas/issues/164) documents removal of ISAccountService's old signInWithContext:replyBlock: method. Historical [AuthKit context declarations](https://github.com/phatblat/macOSPrivateFrameworks/blob/9047371eb80f925642c8a7c4f1e00095aec66044/PrivateFrameworks/AuthKit/AKAppleIDAuthenticationContext.h) instead expose an anisetteDataProvider property. Historical declarations alone do not establish current availability or that a custom provider can cross the daemon boundary.

The new account-free AuthKit capability probe checks only class/method/protocol metadata on the hosted Mac. It does not instantiate an account, call authentication, attach a provider, mutate system state, or infer successful enrollment from the existence of a selector.

Before another authenticated trial, integration must establish a compatible way to supply the independently provisioned data to the account-authentication path, obey any real verification challenge, and preserve the decision to decline the optional security upgrade. Even successful account authentication must then create and recover matching FairPlay state and validate a real IPA. Copying an Android ADI blob into native macOS storage, renaming it as FAIRPLAY_MODEL_B64, or treating the successful prerequisite probe as decryption would be unsupported.

### Isolation and implementation

- tools/anisette_probe.py launches a disposable worker with no Apple secrets, a 120-second timeout, suppressed stdout/stderr and a private temporary result file. Only fixed status/boolean/count fields are returned; all login, native-import, enrollment and decryption claims are forced false.
- The private provider state is saved/reloaded only in memory and is discarded when the worker exits. No headers, machine identifiers, ADI files, model material or raw errors are uploaded or cached.
- The workflow is manual, main-only, read-only, limited to GitHub-hosted runner choices, and uploads no artifacts. The public APK is removed afterward.
- All implementation, dependency installation, compilation, tests and experiments remain on GitHub; no Debian server, external Mac, personal phone or TG integration is used.

## Native callback contract and private authentication trial (2026-11-04)

### Current provider contract

[Account-free run 41748357798](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41748357798), commit 8a6b135204c5de082e4b56bf031144c4419f06d6, compiled and exercised the real macOS-15 AuthKit proxy with synthetic data. The context retained our provider; _AKAnisetteProviderProxy called fetchAnisetteDataAndProvisionIfNecessary:withCompletion:. The positive and missing-data cases both passed, with two provider fetch calls and no other provider operations. No account credentials were supplied.

The callback shape was found in [historical protocol declarations](https://github.com/phatblat/macOSPrivateFrameworks/blob/9047371eb80f925642c8a7c4f1e00095aec66044/PrivateFrameworks/HomeKit/AKAnisetteServiceProtocol-Protocol.h) and [newer proxy declarations](https://github.com/userlandkernel/ios17-dyld-headers/blob/89931f35a750ed18297df97f009524ed37e60d67/AuthKit/_AKAnisetteProviderProxy.h), then verified against the actual hosted Mac. This establishes a local callback contract; it does not establish that an authentication request can cross the AuthKit daemon boundary.

### One authenticated controller invocation

[Run 41749424573](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41749424573), commit 12bbfe45e7ca2637946001e3ae3460ca4dab8a67, ran on macos-15. Seven independent-provider tests, nine private-authentication tests, both Objective-C compilations and the account-free callback contract passed. The final authentication step correctly failed:

| Observation | Result |
| --- | --- |
| Independent provider initialized using private current-runner device context | true |
| Apple provisioning requests | 3 |
| Ephemeral / no interactive auth / no optional security upgrade / no persistent service-token update policies read back | verified |
| Authentication controller invocations | 1 |
| Authentication completion callback | received |
| Error | NSCocoaErrorDomain 4099 |
| Custom provider callbacks / fresh data requests | 0 / 0 |
| Account identity / IDMS token returned | neither |
| Native Store session / enrollment / model / plaintext | not established |

The account_login_attempted flag means the client invoked authenticateWithContext:completion:. It does not prove that an account request reached Apple's servers. The provider initialized successfully, but this call failed before asking it for data; neither acceptance nor rejection of the independent Anisette headers by the account server was tested.

Apple describes [NSXPCConnectionInvalid](https://developer.apple.com/documentation/foundation/nsxpcconnectioninvalid-c.enum.case) as an invalid XPC connection. The follow-up below compares that SDK constant directly and classifies the connection failure without supplying an account. Code 4099 alone does not identify a missing entitlement, missing service, invalid client setup, incorrect password, enabled two-factor authentication or VM exclusion.

### Private data handling and limits

tools/NativeAnisetteAuth.m obtains the current runner's device context only through a private pipe to tools/native_anisette_auth.py. The independent provider is configured with those values; callbacks would obtain fresh data over a bounded private pipe, up to four times. State is memory-only. Neither device values, authentication headers, server responses, tokens nor errors with free text are printed.

Only the final manual workflow step receives the existing Apple Secrets. Helpers receive a minimal environment; raw stdout/stderr are captured or discarded. Workers have time limits and run in a process group that is terminated during cleanup. The result file is private and temporary; reports use fixed statuses, boolean flags, bounded counts and allowlisted error codes. Tests exercise actual synthetic IPC, repeated fresh-data requests, unexpected output, request limits, timeout cleanup, error redaction and failed-exit handling.

The native context explicitly declines optional security upgrade, prevents interactive authentication, uses ephemeral operation and disables persistent service-token updates; those flags must read back correctly before the single call. No challenge-solving loop, retries, native Store account creation or model generation is implemented in this probe. The trial used the default service type (observed 0), so even a successful generic AuthKit result would require a separate Store-specific enrollment implementation.

This work remains GitHub-only. It does not use the Debian server, an external Mac, a personal phone or Telegram.

### Account-free daemon transport comparison

[Run 41749842285](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41749842285), commit d14722128468ac1412ed040beef585a740e161d6, passed four report/isolation tests and native compilation. It made four account-free public-URL-bag calls: command-line versus our own ad-hoc-signed app bundle, each using default versus explicit own client identification.

All four calls received completion with NSCocoaErrorDomain 4099 and no bag result. The compiled SDK identified 4099 as NSXPCConnectionInvalid. Error text matched only the fixed connection_invalidated category; it did not match the allowlisted missing-service, lookup, sandbox, code-signing or entitlement-denial phrases. Packaging and explicit identification did not fix the tested connection.

The current GUI session had a registered com.apple.akd service and the system launch-agent plist existed. The separate user-domain registration check was false; this is not proof that the GUI service is absent. The native App Store's public signing metadata included com.apple.authkit.client.internal=true. This observation by itself does not prove which permission caused rejection.

The workflow's success means the bounded diagnosis completed, not that the transport, login or model succeeded. No Apple account, Anisette provisioning, authentication call or account-state mutation was used in these transport-only controls. The app bundle uses our own identifier and ordinary ad-hoc signing; no Apple identity or private entitlement was added.


[Diagnostic follow-up 41750036044](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41750036044), commit b35229f935f3273940f121ed19237a7d0423297c, passed six tests and repeated the four account-free failures. Captured client stderr contained none of the fixed entitlement-denial, own-client or code-requirement phrases. A one-minute akd query filtered to entitlement/own-client terms returned zero matching events. This is absence of evidence from that filter/window, not proof that no access check occurred. The internal-entitlement hypothesis remains unconfirmed.

The next research boundary is the AuthKit client-to-daemon path or a complete independent Store-enrollment protocol. Further unchanged credential retries are not justified by these results. Local callback success does not establish cross-process callback delivery, and a successful public bag request would still not establish authentication permissions. No FairPlay state or portable model has been recovered.

## AuthKit service, signing and caller-scope controls (2026-11-04)

All experiments in this section are account-free and run only on GitHub-hosted macos-15. No authentication controller login method, Apple credentials, Anisette provisioning, model recovery or real IPA is involved.

### Inspecting the actual connection

[Run 41750449196](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41750449196), commit cd37ff456fd5615af67bb3bd9c7f3b3f44699113, passed seven privacy/contract tests and native compilation. The retained NSXPCConnection and its underlying XPC connection were available. Its service was com.apple.ak.auth.xpc, which also appeared in the system akd launch agent's MachServices dictionary. The GUI akd registration check remained true. Four ordinary client combinations still returned NSCocoaErrorDomain 4099.

The helper uses Apple's [xpc_connection_get_name](https://developer.apple.com/documentation/xpc/xpc_connection_get_name(_:)) and [xpc_connection_copy_invalidation_reason](https://developer.apple.com/documentation/xpc/xpc_connection_copy_invalidation_reason(_:)) APIs after obtaining the connection inside our own process. Only known service names, fixed reason classifications and boolean peer-availability metadata are published. Raw reason strings, process IDs, account names and hardware identifiers are discarded. Runtime presence is checked before using the private getters.

An additional [in-process proxy observation run 41750914146](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41750914146), commit c36907e16a0c9866869ce5cba6f72b2a82da3061, passed ten tests and native compilation. Each of the four ordinary clients made one observed proxy request to the auth service and received one captured 4099 proxy error. The reason API returned a nonempty string, but only the allowlisted word connection matched; none of the specific cause classifiers matched. No positive peer PID was observed. These observations confirm the error occurred on the actual requested auth-service proxy, but do not identify the daemon's decision or prove it never processed the request.

The observation wraps proxy error handlers only inside our own disposable helper, forwards each original call/callback and restores the original implementations. It neither attaches to nor modifies a system process. Reports bound captured failures to four and never recursively publish nested native objects.

### Declaring the internal permission is not a working fix

[Controlled signing run 41750678118](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41750678118), commit 51e4fe127d25908967583ccebf1425f78ab5f4ea, passed nine tests and native compilation. It compared the ordinary client with a copy signed ad hoc under our own bundle identity, declaring only com.apple.authkit.client.internal=true as the additional entitlement.

The ordinary clients ran, reported no such entitlement in their own signature metadata, and returned 4099. The declared-entitlement copy's static signing metadata included the flag, but both of its attempted launches ended with signal 9 and no native report. No account request was attempted. This establishes that this ad-hoc declaration did not provide a usable client; the experiment did not identify which kernel/code-signing decision caused the termination.

Apple's [code-signing guidance](https://developer.apple.com/forums/thread/751658) also distinguishes declaring entitlements from being able to use restricted entitlements under ad-hoc signing. The hosted result must not be described as a granted AuthKit permission. No Apple signing identity, provisioning profile, system binary or system security setting was changed. The failed variant has been removed from subsequent workflow runs.

### Caller privilege and GUI bootstrap scope


[Caller-scope run 41751197447](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41751197447), commit 740da3cb6d5a1edc2354f22c67ed3ebdc50ba5f4, passed eleven tests and native compilation. Four ordinary calls and two root calls using launchctl asuser all returned 4099. The two administrative helpers confirmed effective_user_is_root=true; every case observed one auth proxy request and captured its error.

The historical container label own_app_root_in_user_gui was too strong: the command targeted the runner user's context with asuser, but did not independently verify adoption of a desktop process's Mach bootstrap namespace. Later code labels it own_app_root_via_asuser. This result shows that this root/asuser combination did not solve the problem; it does not establish that every GUI-context route was tested.


[Mach lookup and desktop-context run 41751601120](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41751601120), commit 6d366dd57b002e74367b5e4b7cc33a9590f2575e, passed thirteen tests and native compilation:

| Control | Executed helper | Auth-service Mach lookup | Public bag call |
| --- | --- | --- | --- |
| Ordinary CLI, default / named | yes / yes | found, code 0 / found, code 0 | 4099 / 4099 |
| Own app bundle, default / named | yes / yes | found, code 0 / found, code 0 | 4099 / 4099 |
| Root via asuser, default / named | yes / yes | found, code 0 / found, code 0 | 4099 / 4099 |
| Adopt desktop process context with bsexec, then restore ordinary UID | no native report in either attempt | not measured | not measured |

All six executed helpers obtained a valid send right for com.apple.ak.auth.xpc and then captured an error from the actual proxy. Failure to find that service is therefore not the cause of these six calls. A successful lookup alone does not prove that the server accepted the connection or request. Root privileges via the tested asuser command did not fix this path.

The bsexec control locates exactly one Finder or Dock process owned by the runner user, privately validates its numeric PID, then requests that process's bootstrap context and restores the runner UID before execution. Both commands exited 1 without a native report. The report intentionally does not expose raw command errors or process IDs, so the specific command failure is not identified. These two cases do not establish a successful desktop-context transfer and must not be counted as additional AuthKit rejections. The earlier asuser label correction matters for that distinction.

Apple's [launchctl manual source](https://github.com/apple-oss-distributions/launchd/blob/d448a1c8f70a61202f8705f94337f686b87c30c4/man/launchctl.1) motivated testing a process-specific bootstrap context; current behavior is judged from the hosted run rather than assumed from the historical manual.

### Result and next boundary

The tested native bridge remains unusable for first-time enrollment. A reachable service name, a local provider callback, administrator execution and an entitlement string in a signature are different conditions; none of these observations establishes successful account authentication or FairPlay state.

No new account login was attempted during this follow-up. The pinned UnfairPlay upstream was rechecked and its current head remains 26a099fcb2292eaacd9e0ce89793cdbc88e516d1; it still consumes already-enrolled Mac state and does not supply a newly working first-enrollment path.

Further work needs a supported client path that reaches the authentication service, or a separately implemented and verified Store/FairPlay registration protocol. Repeating the same account credentials, declaring the internal entitlement again, or treating the successful diagnostic workflow as a working authorization model is not justified. This does not prove that every GitHub-only implementation is impossible.

All edits were made through GitHub APIs. All compilation, tests and process experiments ran on GitHub-hosted Actions. No external Mac, Debian execution, personal phone, TG integration, public credentials, account identifiers, headers, model material or real IPA artifacts were used.


## Native keybag prerequisites and upstream candidates (2026-11-04)

The AuthKit transport failure does not establish that every in-process FairPlay operation is unavailable. A separate account-free native probe now checks AppleMediaServices directly on GitHub-hosted macOS 15 ARM and Intel.

Run [41753771388](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41753771388) confirmed a nonzero, error-free native FairPlay context and nonempty synthetic account-0 keybag sync data on both architectures. The four monitored SIDB/SIDS paths did not report nonempty regular files. This metadata-only check does not distinguish missing files, empty files and inaccessible metadata; it does not prove the absence of every FairPlay state location. An earlier run had incorrectly boxed C comparisons as JSON numbers; strict report validation rejected those results. Native boolean serialization was fixed instead of relaxing the public schema.

Run [41755075728](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41755075728) passed 11 Python contracts per architecture plus native request-policy positive and negative cases. It established:

- AMSKeybag and AMSAuthorizeMachineTask exist with checked Objective-C method signatures on both runners.
- An ephemeral synthetic account can build machine-authorization parameters with native kbsync, GUID and machine name. Neither identifiers nor blob contents are published.
- The observed macOS parameter keys are guid, kbsync, machineName, needDiv, ownerDsid and xToken. The xToken body field is the string "0", and needDiv is observed as one. These are observations for this ephemeral account; they do not establish xToken's semantics for every account type or server acceptance.
- The public AMS bag resolves authorizeMachine to HTTPS buy.itunes.apple.com/commerce/machine/authorize. This differs from assumed legacy WebObjects routes.
- The native builder produces a POST property-list request for the ephemeral account without an Anisette or SAP header in these observations. This is request construction, not server acceptance.
- A separate session adapter checks the exact destination, body account ID, six-byte GUID and kbsync before adding X-Token, X-Dsid and iCloud-DSID headers. Tests reject changed hosts, HTTP, unexpected ports, userinfo, paths/query parameters, a different account and an empty token.
- No authorization request was submitted by these prerequisite runs.

The private machine-enrollment workflow uses a fresh successful Store login as the session source. The patched login exports DSID, password token, GUID, scoped login cookies and the full storefront header to a temporary mode-0600 handoff and returns before saving a persistent account. A native client keeps parameter generation and keybag import in one process, verifies the session/device identity, submits one authorization POST with at most one approved 307/308 routing hop, caps the response at 2 MiB, and separately checks the returned keybag and import result. It does not call the native task's high-level performAuthorization method: reviewed iOS code can resolve that promise successfully even after an import error. Model recovery and plaintext verification remain separate requirements. No session, keybag, SIDB, model or IPA artifact is published.

Interface research used the [iOS 18.2 AMSAuthorizeMachineTask implementation](https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore/blob/e26ed4563f78871c59d2d96856756a65d62517e5/System/Library/PrivateFrameworks/AppleMediaServices.framework/AMSAuthorizeMachineTask.m), [AMSKeybag implementation](https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore/blob/e26ed4563f78871c59d2d96856756a65d62517e5/System/Library/PrivateFrameworks/AppleMediaServices.framework/AMSKeybag.m), and macOS runtime headers. Runtime observations take precedence where macOS differs from those iOS sources.

### Candidate projects reviewed

[EEliberto/Pastel-macOS at 82576f2](https://github.com/EEliberto/Pastel-macOS/tree/82576f2295516e84b6eaa99a4e364af5e8de7664) is a downloader. Its active StoreHelper calls ipatool Download followed by ReplicateSinf, using the same pinned ipatool d9c0247 dependency already investigated here. Its November 2 fix adds missing account license files to downloaded IPAs; it does not remove Mach-O encryption. The README requires a physical Apple-silicon Mac and says virtual machines are unsupported. It is a download-flow reference, not evidence of GitHub-only enrollment.

[EthanArbuckle/fairplay-decrypt at bb09a610](https://github.com/EthanArbuckle/fairplay-decrypt/tree/bb09a61046f5c99eb1795589a307646df04b26d0) implements offline decryption using a matching 16-byte account credential. Its Python decryptor runs on macOS/Linux; its credential-retrieval workflow requires a paired jailbroken iOS device with root SSH and an installed app owned by the account. The Mac build produces iPhoneOS arm64 retriever/driver/trigger binaries; compiling them does not create a credential. This is a possible alternative offline backend, not a verified credential bootstrap for a fresh GitHub runner. No code has been imported from this GPL-3.0 repository, and no personal phone was used.

For decrypt.day, a read-only request from this research environment returned HTTP 451 and the body "error code: 1026"; that observation is not a global outage diagnosis. No current public decryption API contract was verified. The same-name [decrypt-day organization](https://github.com/decrypt-day) exposes idevice-tools with only a one-line libimobiledevice archive-build README, not the service backend. No account was registered, credentials supplied, API job submitted or message sent to its operators.


### First private machine-authorization transport result

Run [41755421489](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41755421489), source commit 716375a, passed 17 Python contracts, native compilation/prerequisites and 7 Swift SAP request tests. Store login succeeded, the private session handoff succeeded, and the native account/GUID boundary passed. The authorization POST returned HTTP 307. The initial deny-all redirect policy stopped there; no keybag import was attempted and the four monitored paths did not report nonempty regular SIDB/SIDS files. This is a metadata observation, not an exhaustive search.

This is a transport result, not an authentication rejection or model-generation result. The follow-up client permits at most one 307/308 redirect to an exact numbered Apple Store pod under p[0-9]{1,3}-buy.itunes.apple.com, on the same /commerce/machine/authorize path (including its canonical trailing slash), over HTTPS/443 with no userinfo/fragment. Initial requests accept only an optional matching guid. A redirect may carry opaque Apple routing query parameters up to 2,048 characters; any guid, dsid or ownerDsid fields must still match the session. It reconstructs the next request from the original POST, preserving its body, and rechecks the account/GUID boundary before applying session headers. All other redirects stop the operation. A separate native synthetic positive/negative policy check runs before any account secret is supplied.

### Routed response and complete Store context

[Run 41756852747](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41756852747) observed an HTTPS 307 POST redirect to an exact numbered Apple Store pod and the exact authorization path. The then-current optional-guid-only query rule stopped it. The client now accepts bounded opaque routing parameters only on those pinned hosts/paths, while rejecting conflicting explicit account/device query fields; positive and negative cases cover both rules.

[Run 41757256880](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41757256880), commit 41d03ba, passed 18 Python contracts and 7 Swift SAP tests. The private Store login succeeded, one approved routing hop completed, and the final response was HTTP 200 with business failureType 2002 and a dialog. There was no keybag. The code alone does not establish a bad password, an OTP challenge or enabled two-factor authentication.

[Run 41758396250](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41758396250), commit 1e03781, passed the same 18 Python and 7 Swift tests, native compilation and the synthetic cookie policy. It preserved login cookies and the full storefront in the private handoff. Host-only login cookies without an explicit domain were scoped to their response origin; authorization requests rebuild the Cookie header for each allowed destination after checking name/value syntax, domain, path and expiry. Cookies are not copied blindly between root and pod hosts. Real cookie values, names and storefront contents are never reported.

In that trial, Store authentication succeeded and the authorization request carried eight eligible cookies plus a storefront header. The initial endpoint returned HTTP 500, with no redirect and no parseable property-list response. This did not establish successful authorization or identify whether the changed context or a transient server condition caused the result. No keybag import was attempted; no model or decryption was verified.

### Authentication-purpose control

Historical open-source implementations distinguish ordinary Store sign-in from a login whose why field is machineAuthorize: [ituneslib.py](https://github.com/lilang-wu/iOS-AppStore-Malware-Automatic-Hunting-System/blob/3fd5704dc69ff00ed9c8d9acf25c3317f09620d9/Auto%20Crawl%20System%20V3.0/AutoCrawler/ituneslib.py) and [login.go](https://github.com/adm1n007/pingguo_jihuo/blob/6bd9a88036aa7f64f71c93852cc872b7215e8cbd/ituneslib/login.go). This is a research hypothesis for the current endpoint, not proof that those historical protocols still work.

The manual private workflow now separates two controls: purpose (signIn, machineAuthorize or machineSession) and session_context (token, cookies, storefront or store). The machineAuthorize control changes only the signed login why field. The separately selected machineSession experiment also supplies createSession=true, the current machine name and attempt=1, and omits the ordinary rmp parameter, following the historical Go request shape. The endpoint, SAP implementation and GUID remain those of the pinned client; this is not a claim that the complete historical protocol has been reproduced. It does not add an extra login, change the password, accept an account-security upgrade or automatically answer a server dialog. The token control withholds cookies/storefront so that a machineAuthorize trial can be compared with the earlier routed 2002 response. A synthetic Swift case checks that the complete changed body is exactly the body passed to SAP signing; Python cases check selection rejection, private handoff and context isolation. Results must be evaluated separately from these contract checks.

[Dual-architecture regression run 41758902225](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41758902225), commit 3e97ab2, passed 12 Python contracts on each of macos-15 ARM and macos-15-intel, native compilation, and the native synthetic request/cookie-policy cases. No Apple credentials were used and no authorization request was submitted.

[Purpose-only private trial 41758811569](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41758811569), commit 3e97ab2, passed 20 Python contracts and 8 Swift SAP tests. With machineAuthorize login and token-only request context, Store authentication succeeded and one allowed pod redirect completed. The final response was HTTP 200, failureType 2002, dialog present and no keybag. Fixed text classifiers matched sign-in and password terms, but not verification-code or computer-limit terms. These limited classifiers are neither a complete dialog interpretation nor proof that the account's password or security setting is wrong. Changing only the signed why field did not complete machine authorization.

Cookie-only and storefront-only controls are available to separate the two session-context changes behind the earlier HTTP 500 result. Each manual run still attempts one authorization operation with at most one approved routing hop; no dialog is answered automatically.

[Cookie-only trial 41759197723](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41759197723), commit 94d1ee5, passed 20 Python contracts and 8 Swift tests. machineAuthorize login succeeded. The native request carried eight eligible cookies without a storefront header, received HTTP 200 without a redirect, and returned failureType 2002 with no keybag. The same limited sign-in/password classifiers matched. This establishes that the cookie-only request received a structured rejection in this run; it does not establish a universal cause for the earlier HTTP 500.

[Storefront-only trial 41759651890](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41759651890), commit 211ec0d, passed 20 Python contracts and 8 Swift tests. machineAuthorize login succeeded and one approved pod redirect completed. With the full login storefront header and no cookies, the authorization endpoint returned HTTP 500 and no parseable property list. Together with the cookie-only and token-only controls, this supports leaving this copied storefront header disabled in subsequent trials. The runs used separate fresh sessions and runners, so they are not proof of a universal server-side cause. No keybag import or model was produced.

The machineSession experiment adds an independent synthetic test that verifies all changed fields are present in the exact SAP-signed bytes. It does not answer any server dialog, enable a security upgrade, request deauthorization, or export private session material.

[Machine-session trial 41760174263](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41760174263), commit 83e1c6a, passed 20 Python contracts, 9 Swift SAP tests, native compilation and synthetic prerequisites. With createSession=true, attempt=1, the current machine name and the machineAuthorize why field signed together, Store login succeeded. The authorization request carried eight scoped cookies and no copied storefront header. It received HTTP 200 without a redirect, failureType 2002, a dialog and no keybag. Sign-in/password text classifiers matched; verification-code/computer-limit classifiers did not. The additional session-creation fields did not complete authorization in this trial.

### Earlier session controls before the body-token correction

| Store login variant | Authorization context | Observed final response | Keybag |
| --- | --- | --- | --- |
| signIn | token | HTTP 200, failureType 2002 after one pod redirect | none |
| signIn | cookies and copied storefront | HTTP 500, not a parsed plist | not obtained |
| machineAuthorize why only | token | HTTP 200, failureType 2002 after one pod redirect | none |
| machineAuthorize why only | cookies | HTTP 200, failureType 2002, no redirect | none |
| machineAuthorize why only | copied storefront | HTTP 500 after one pod redirect, not a parsed plist | not obtained |
| machineSession fields | cookies | HTTP 200, failureType 2002, no redirect | none |

All rows above used the then-incomplete body with xToken="0"; see the later correction and post-correction trials below. They used bounded GitHub-hosted trials. Each authenticated request used its own fresh private session; the table does not isolate every possible server, runner or timing difference. The default authorization context is now token-only, matching a tested structured-response baseline; cookie and storefront variants remain explicitly selectable research controls.

No row imported a keybag, recovered an enrollment model or verified IPA plaintext. A successful Store session and locally generated kbsync are still insufficient evidence of accepted FairPlay enrollment. The tested session controls have not identified the full machine-authorization authentication contract. Repeating these unchanged requests is not a demonstrated path forward. Further work requires new protocol evidence or a verified credential-bootstrap implementation, not another successful compilation.

The reviewed fairplay-decrypt upstream supplies an offline decryptor and an iOS credential extractor; it supplies no verified fresh GitHub-only bootstrap. It has not been integrated or used to claim real decryption. No personal device, third-party decryption service, Telegram integration, local project execution or public private-material artifact was used.

## Native authorization body token correction (2026-11-04)

Earlier private trials authenticated a Store session and added X-Token, X-Dsid and iCloud-DSID request headers, but left the native machine-authorization body xToken at its ephemeral-account default "0". Treating that default as a complete authenticated body was incorrect.

Account-free [code inspection 41761114120](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41761114120), commit d6c685e, passed three bounded-report tests on each GitHub-hosted ARM/Intel Mac and inspected two native AppleMediaServices builders. Both architectures showed that _buildRequestParametersWithError: gets the account-store secure token and inserts it as xToken; only a missing token falls back to "0". The ARM implementation also supplied transaction type 2 on the inspected native builder path; the separate synthetic account-0 transaction-1 prerequisite must not be confused with that actual builder.

[Accessor inspection 41761399542](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41761399542), commit efb8759, passed four report tests per architecture. Runtime method metadata resolved ACAccountStore ams_secureTokenForAccount: and NSDictionary ams_secureToken without invoking either with a real account. The latter reads the passwordToken response key on both architectures. The reviewed [AMSVerifyCredentialsTask](https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore/blob/e26ed4563f78871c59d2d96856756a65d62517e5/System/Library/Accounts/Authentication/AMSAccountAuthenticationPlugin.bundle/AMSVerifyCredentialsTask.m) also stores that response token through ams_setSecureToken:forAccount:error:. A temporary ACAccount whose session has never been persisted therefore cannot supply the token through the original account-store lookup merely because our external login succeeded.

These inspections launched only our framework-loading process under LLDB. They did not authenticate, construct real-account requests, execute the inspected methods for a real account, read heap/register/account data, attach to system daemons or submit authorization. Captured debugger output is filtered to bounded instruction records from an explicit method/module allowlist; raw debugger/process output is discarded.

The adapter now binds the existing private passwordToken to body xToken after checking the exact destination, account, GUID and kbsync. It rejects a conflicting existing body token and refuses to rewrite a body that already carries an action signature. It updates Content-Length after serialization and applies the same session token to the header. A repeated binding is byte-stable; routed requests retain and revalidate the bound body.

[Dual-architecture binding validation 41761683677](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41761683677), commit c4a2274, passed 12 Python contracts per runner, native compilation and synthetic binding/routing cases. The synthetic tests reject a zero token, a conflicting token, an unbound signed body and the existing invalid destination/identity cases. They verify unchanged semantic parameters except xToken, correct content length, header/body agreement and idempotent rebinding. Private success reports additionally require body_token_bound=true.

The earlier 2002 results remain valid observations for incomplete requests. They do not establish that a correctly bound session will fail, that the password is incorrect, or that GitHub-only enrollment is impossible. A real response and successful import are still necessary, followed by separate model recovery and full IPA plaintext validation.

### Private results after binding the actual body token

The following fresh trials independently verified body_token_bound=true and session_identity_verified=true. The earlier unbound trials are not used as proof of these outcomes.

| Run | Signed Store login | Forwarded context | Authorization result |
| --- | --- | --- | --- |
| [41761847159](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41761847159), c4a2274 | signIn | token | HTTP 200, failureType 2002, one approved pod redirect, no keybag |
| [41762179734](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41762179734), c4a2274 | signIn | eight scoped cookies | HTTP 200, failureType 2002, no redirect, no keybag |
| [41762648147](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41762648147), 3d92a1d | machineAuthorize | eight scoped cookies | HTTP 200, failureType 2002, no redirect, no keybag |
| [41762837405](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41762837405), 91c63af | booleanSession | eight scoped cookies | HTTP 200, failureType 2002, no redirect, no keybag |

Each run passed 20 Python contracts, native compilation and synthetic prerequisites before exposing secrets. The first three passed 9 Swift SAP tests; the booleanSession run passed 10. Store login succeeded in all four. No keybag import, recovered model or plaintext verification occurred. The four fixed state-path metadata checks remained false; they do not prove the absence of every possible system FairPlay state.

The new booleanSession control retains the historical machineSession fields but encodes createSession as a plist boolean, following the type observed in the reviewed native AMSVerifyCredentialsTask source. The legacy control retains its original string for comparison. A Swift test verifies the boolean plist type, unchanged identity fields and exact equality of the serialized body and SAP-signed bytes. This experiment changes a specific wire type; it does not claim to reproduce every field or behavior of the native authentication plugin.

## Native Anisette scope and provisioning response evidence (2026-11-04)

[Account-free dual-architecture inspection 41762566901](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41762566901), commit 3d92a1d, passed four bounded-report tests per runner and inspected seven allowlisted AppleMediaServices methods without account credentials. Both ARM and Intel implementations confirm:

- AMSAuthorizeMachineTask selects Anisette type 1.
- AMSURLRequestDecoration skips Anisette decoration when the account is ephemeral and the type is not 2.
- AMSAnisette maps type 1 to the account DSID, while type 2 uses the unsigned -1 sentinel.
- The header generator selects AMSHTTPHeaderXAppleMD / MDM for the account path and AMD / AMDM for type 2.

The independent provider previously tested by this project uses unsigned -2 and returns X-Apple-I-MD / X-Apple-I-MD-M by default ([pinned Anisette.py source](https://github.com/malmeloo/Anisette.py/blob/a61cddfb2275187822ad0c3999af747b8c9a4f9a/src/anisette/anisette.py)). Its successful AuthKit-style provisioning therefore does not prove that its output is interchangeable with the native machine-authorization data. No header renaming, account-ID substitution or unverified private-state transplant was performed.

The reviewed [AMSAnisetteProvisionTask](https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore/blob/e26ed4563f78871c59d2d96856756a65d62517e5/System/Library/PrivateFrameworks/AppleMediaServices.framework/AMSAnisetteProvisionTask.m) starts from server-supplied challenge data. Its account-scoped finish request uses md-finish-provisioning with clientData, GUID, DSID and transaction-1 kbsync. The type-2 path uses amd-finish-provisioning. The finish response can contain transportKey, settingInfo and keybag. This is a distinct protocol from merely adding existing login headers.

The [response category source](https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore/blob/e26ed4563f78871c59d2d96856756a65d62517e5/System/Library/PrivateFrameworks/AppleMediaServices.framework/NSHTTPURLResponse%28AMSAnisette%29.m) identifies X-Apple-MD-Action/Data and X-Apple-AMD-Action/Data. The private client now classifies only fixed SP/SM/RP/none/other action values and data-present/base64-valid booleans, case-insensitively. It never publishes the headers, challenge bytes, cookies or arbitrary values. A synthetic native response test covers empty headers, mixed case, both valid scopes, malformed data and unknown private action text. Python report tests reject arbitrary action values and fields.

[Challenge-classification trial 41763040212](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41763040212), commit 790e2f8, passed 21 Python tests, 10 Swift SAP tests, native compilation, the native response privacy contract and synthetic prerequisites. signIn login succeeded and the authorization request verified body-token binding and eight scoped cookies. The final response was HTTP 200 / failureType 2002 with no keybag. Both md_action and amd_action were none; all four challenge data presence/validity flags were false. Thus this authorization response contained no observed SP/SM/RP instruction to execute. This measurement covers the final authorization response, not earlier login responses.

These findings narrow the missing contract but do not prove GitHub-only enrollment feasible or impossible. A successful first enrollment still needs an actual accepted server exchange, native import, matching model recovery and full IPA plaintext validation. Neither compilation, a Store login nor an Anisette prerequisite substitutes for those results.

### Upstream Mac credential follow-up

The fairplay-decrypt repository's [Mac credential discussion](https://github.com/EthanArbuckle/fairplay-decrypt/issues/21) points to UnfairPlay. This matches the backend already reviewed here; that discussion supplies no first-time GitHub-runner enrollment implementation. The currently listed credential-bundle CI changes build the iOS retrieval helper, while the retrieval and device compatibility changes still rely on an enrolled device. No reviewed issue or PR is treated as proof of a device-free credential bootstrap.

### Login-stage challenge control

[Login-stage trial 41763584459](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41763584459), commit 1d0c6a3, passed 22 Python contracts, 11 Swift tests, native compilation, response privacy cases and synthetic prerequisites. The private login adapter now OR-aggregates twelve fixed MD/AMD flags across every response processed by the login client, including redirects. Only these booleans enter the private handoff and final report; no raw login response header is exported or forwarded to the native authorization request. Swift cases cover empty headers, case-insensitive names, SP/SM/RP, invalid base64 and unknown private text. Python cases verify the summary allowlist and separation from the native session payload.

Store login succeeded. All twelve aggregated login challenge flags were false. The final machine-authorization response likewise contained no observed MD/AMD action or challenge data, returned HTTP 200 / failureType 2002, and contained no keybag. The actual body token, account/GUID identity and eight eligible cookies were verified. This control found no skipped provisioning instruction in the observed login/authorization exchange.

The current blocker is still an unaccepted first-time machine-authorization exchange. The code does not yet implement a verified way to obtain the matching initial FairPlay state using GitHub alone. It must not fabricate an SP challenge, rename AuthKit data into account-scoped headers, treat the new tests as enrollment, or claim a plaintext artifact. Further authenticated trials should follow new protocol evidence rather than repeat these unchanged rejected configurations.


## Native client identity and first keybag response (2026-11-04)

### Account-free signing policy control

The pinned iOS AppleMediaServices source shows request encoding defaults to Mescal type 1, while ephemeral accounts skip ordinary Anisette and Mescal decoration. The account-free macOS probe tests the actual runtime matcher against the public machine-authorize bag and a fixed synthetic request; it does not send an authorization request.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41764373913 passed on ARM and Intel, including four Python contracts per architecture. The native default was type 1, both configured policy matchers returned false for the root machine-authorize endpoint, and invoking the native signing hook produced no signature and no error. Body, destination and other headers were unchanged. This rules out an automatically requested Mescal signature under that observed public configuration, not every possible URL or authenticated session.

### Consistent client identity reaches a new stage

The pinned ApplePackage Configuration.swift uses a Configurator User-Agent for Store login. The native request builder instead derives its User-Agent from the current process. The private handoff now carries the exact configured login agent; the explicit login_agent option replaces only that authorization header after existing body-token, GUID, DSID and destination checks. Printable ASCII and length bounds reject malformed headers; the request body remains unchanged. Synthetic contracts also verify untouched unrelated headers. No User-Agent, session values or payload bytes are printed.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41764672563 used signIn + cookies + login_agent. It passed 23 Python and 11 Swift tests, native compilation and synthetic request/response/header checks before supplying credentials. The private phase observed:

- Store login succeeded, body_token_bound and session_identity_verified were true.
- client_agent_bound and client_agent_changed were true; eight filtered cookies were applied and the problematic storefront header was omitted.
- The single authorization request returned HTTP 200, apple_failure_present=false and keybag_present=true. The earlier 2002 response was absent in this trial.
- No redirect, oversize response or MD/AMD provisioning instruction was observed.
- Native import returned AMSErrorDomain 505: keybag_import_succeeded=false and status=keybag_import_failed. All four observed nonempty-readable SIDB/SIDS path flags remained false.
- enrollment_created=false and decryption_proven=false. The run failed overall, as required for an unsuccessful import. No private keybag was retained as an artifact.

This is the first observed server keybag response in the project. A nonempty response is not proof that the keybag is importable, that computer enrollment completed, or that a model was recovered. The known successful request configuration is preserved while investigation moves to local import; further authentication-purpose variants are not being retried without new evidence.

An account-free code inspection, run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41764812740, confirmed native authenticationType=2, credentialSource=2 and canMakeAccountActive=false on both architectures. These observations alone do not justify changing the now-working server request.

### Import diagnostic baseline

Import diagnostics compare the shared AMSKeybag object and FairPlay context before request generation and before importing the response, without publishing the context identifier. Only allowlisted error domains/codes and a bounded numeric import status may leave the runner; descriptions, failure reasons and keybag contents stay private.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41765392466 passed on both architectures with 12 Python checks per architecture plus native error/header contracts. A fixed invalid keybag, with no login or authorization request, produced AMSErrorDomain 505 and was rejected while its context remained stable. The first diagnostic parser did not extract a numeric status from either macOS runtime; its iOS-derived message template therefore cannot yet explain the real import failure.

The macOS import block was then inspected directly on both architectures in run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41765844311 (four Python reporting contracts per architecture). It confirms the low-level import call and the exact numeric message template; an initial probe with the iOS-style block symbol was unavailable and is superseded by this actual macOS symbol check. The error text is stored in AMS error information rather than necessarily localizedFailureReason. The parser now examines at most 32 userInfo values plus the standard description/reason, accepts only the complete fixed message and signed 32-bit integer, rejects conflicting matches and never publishes text or keys.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766070751 passed on both architectures: 12 Python checks per architecture and native extraction/header contracts. Both fixed invalid samples produced import_fairplay_status=-42023, context_ready_before_request=true and context_stable_after_rejection=true. This validates numeric extraction without using an account; it does not assign the real response the same cause.

### Repeated real keybag response with numeric import diagnosis

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766153823 passed 24 Python tests, 11 Swift tests, native compilation and synthetic contracts. It used the same signIn + cookies + login_agent request configuration. Store login again succeeded, the single authorization response again contained a nonempty keybag without a business failure, and import again failed. The newly extracted import_fairplay_status was -42023; context_ready_before_request and context_stable_before_import were both true. The observed four SIDB/SIDS flags remained false, and enrollment_created/decryption_proven remained false.

The repeated response establishes progress beyond the previous 2002 blocker, but the matching error code for a deliberately invalid sample does not establish the real response's failure cause. No second request, retry import, deauthorization or private artifact export was performed in this trial.

Actual macOS context code inspection in https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766323939 passed on both architectures and confirms /Users/Shared/SC Info as the AMSFairPlayContext storage path, after _validateFairPlayPath. The existing state checks therefore include the actual directory; this does not prove all FairPlay state anywhere on the runner is absent. Static low-level import inspection in https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766425771 does not itself establish the meaning of -42023.

The manual trial and CLI now default to cookies + login_agent, preserving the explicitly tested request configuration. The Python trial API retains legacy defaults for existing callers and tests.

Primary references: [pinned ApplePackage client configuration](https://github.com/Lakr233/ApplePackage/blob/391bfe6ee6598d73e4f94b88b38b50bd6f6ec67b/Sources/ApplePackage/Configuration/Configuration.swift), [iOS AMSKeybag reference](https://github.com/EthanArbuckle/iPhone17-1_18.2_22C152_Restore/blob/e26ed4563f78871c59d2d96856756a65d62517e5/System/Library/PrivateFrameworks/AppleMediaServices.framework/AMSKeybag.m), and the macOS runtime CI reports above. iOS reference behavior is not assumed to match macOS without a runtime check.

### Shared-directory control

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766654638 passed on ARM and Intel (12 Python checks per architecture and native contracts). After native context creation the actual shared directory was present, not a symlink, and writable by the process. The fixed invalid sample still returned -42023. This does not establish every later database I/O would succeed, but provides no evidence to justify a root rerun as a directory-permission fix.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766657666 inspected the actual path-validation function on both architectures with four Python checks per architecture. The lower-level import implementation uses obfuscated control flow; the bounded static snippets do not establish the precise condition producing -42023. No error-code meaning is inferred from an unrelated search result.

### Response-envelope control

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41766951830 passed 25 Python and 11 Swift checks plus native shape/error/header contracts before credentials were supplied. The server again returned a keybag with no business error; native import again returned -42023 with the same context. The live trial confirmed the shared directory was present, writable and not a symlink. The returned data had size bucket under_4096 (256–4095 bytes) and did not match strict canonical Base64 ASCII, an XML prefix, bplist00 or gzip magic. These bounded format flags neither reveal payload bytes nor validate the FairPlay envelope. No unwrapping or import retry was attempted on speculation.

### App Store daemon request prerequisite

The existing runtime metadata confirmed ASDFairPlayService is available. Its reference implementation uses App Store daemon RPC rather than the process-local AMSKeybag context. A separate account-free probe checks actual ABI and attempts only local keybag-request generation for a fixed synthetic account. It never signs in, sends a machine-authorization request or imports a keybag. All stdout/stderr stay discarded and only allowlisted metadata is published.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41767257252 passed on both architectures with three Python privacy/evidence tests per architecture and native compilation. Both found the service and verified its method ABI, but generating a request for synthetic account zero returned ASDErrorDomain 505 and no data. A green diagnostic workflow records completion of a bounded probe; it does not mean request generation or enrollment succeeded. A zero-account result alone cannot distinguish an input restriction from service access or initialization failure.

The follow-up run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41767422349 passed four Python report/privacy tests per architecture, native compilation and synthetic nested-error contracts. It compared fixed synthetic account zero and nonzero in separate processes. All four calls returned ASDErrorDomain 505 with no request data. The bounded classifiers found entitlement wording in each error, but no account/DSID, connection/XPC or permission wording, and no published underlying error. This points to a caller-entitlement prerequisite rather than explaining the independent AMS import error; the classifier is not a complete entitlement-policy proof. No real account was passed, and no Apple authorization or keybag import was attempted.

Current verified position: three private trials with the consistent login agent obtained server keybag data, but all attempted AMS imports failed. The numeric diagnostic in the latter two reported -42023. App Store daemon generation is separately unavailable to the current probe, with entitlement wording in its error. Neither path has produced a recovered FairPlay model or verified decrypted IPA. The next substantive requirement is a supported, demonstrated import/enrollment path; repeated compilation or login is not model generation.


## macOS diversity-bag response handling (2026-11-04)

The account-free runtime checks in https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41768039170 and https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41768174626 passed on ARM and Intel, with four Python reporting checks per architecture. Unlike the examined iOS reference, the actual macOS authorization response block reads both keybag and diversitybag. It calls importKeybagWithData:error: first, then importDiversityBagWithData:error: even after a keybag error. The diversity importer is implemented on macOS, uses the existing FairPlay context, and reports a bounded numeric import status through AMSErrorDomain 505.

The private client previously omitted diversitybag handling. The implementation now validates both blobs and follows the observed native order, keeping primary, initial and diversity import results separate. It never treats the native task's generic completion as import proof. A single local retry of the same keybag is permitted only after an observed successful diversity import, an initial keybag status of -42023, and a stable context. This retry is a controlled recovery hypothesis beyond the observed native one-pass order; it sends no additional authorization request. A malformed or oversized diversity blob, missing interface, failed diversity import, or changed context cannot become a successful result.

The account-free control https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41768464199 passed on both architectures: 14 Python checks per architecture, native compilation and synthetic import-order/error contracts. The native contract exercises absent diversity, successful imports, failed diversity, a bounded successful/failed retry, an unrelated primary error, changed context, malformed/oversized data and private-field omission. The fixed invalid keybag returned -42023, while the fixed invalid diversity blob returned -42018 on both architectures; neither was accepted. These invalid samples do not establish the real response's validity.

The real trial https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41768524362 passed 26 Python and 11 Swift tests plus native contracts before using credentials. The server returned both keybag and diversitybag, HTTP 200 and no business failure. The initial keybag import failed with -42023; the diversity import failed with -42032. Both were AMSErrorDomain 505. Because diversity did not import, no keybag retry occurred. The workflow correctly failed with diversitybag_import_failed. All four expected nonempty SIDB/SIDS flags remained false. A returned diversity blob and distinct failure code do not establish its meaning or a recovered model.

## Bounded native import file-I/O observations (2026-11-04)

Directory presence and writability do not prove subsequent database access succeeds. The next diagnostic uses a small process-local library linked into this project's native executable; it does not inject into a system service. Its DYLD_INTERPOSE mechanism follows the [Apple dyld header](https://github.com/apple-oss-distributions/dyld/blob/main/include/mach-o/dyld-interposing.h). Tracing is optional in the private workflow (trace_io, false by default) and active only around each native import. The login client is unaffected.

Only calls whose requested path or file descriptor resolves under the fixed shared/fpsd SC Info roots are counted. Nineteen selected libc entry points are covered: open/openat/fopen, stat/lstat/access, mkdir/unlink/rename, read/write/pread/pwrite, fsync/fclose/fread/fwrite/flock/ftruncate. Reports contain fixed area/operation labels, bounded call/failure counts, the last numeric errno, missing/permission failure counts and a saturation flag. No path, account/device identifier, data buffer, file content, byte count or keybag byte is emitted. Initial primary, final primary and diversity snapshots are kept separately. Python checks discard malformed, duplicate, oversized or unknown trace fields.

This is a selected library-call observation, not exhaustive syscall tracing: direct syscalls, unlisted entry points, unresolved/relative path variants, another process and calls crossing a trace boundary can be missed. Counts may include overlapping higher- and lower-level calls, so they are not a count of unique disk operations. No observed error does not prove all I/O succeeded, and an observed errno alone does not explain the FairPlay status. Instrumentation may affect runtime behavior; the invalid-blob control and original uninstrumented results remain separate evidence.

Before credentials can be supplied, an account-free native fixture creates and cleans only its own temporary child directory. It exercises every covered operation, verifies data round trips, expected ENOENT/EBADF/EEXIST behavior, disabled tracing and private-field omission. The fixed invalid-import probe now checks context stability after both imports.

The SDK header was absent on both runners in run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41769810843. The diagnostic now declares the dyld tuple layout directly for the two tested targets (arm64 and x86_64), and explicitly refuses arm64e rather than guessing its pointer-authenticated ABI.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41769927731 passed on both architectures with 15 Python tests each and the real dynamic-interposition fixture. ARM recorded an open failure with errno 13 (EACCES) in the fpsd SC Info area during each invalid import. Intel recorded no matching calls; its empty observation is not proof that no I/O took place. Both still rejected the invalid keybag (-42023) and invalid diversity blob (-42018).

### Privilege comparison, including one real root trial

The observed ARM access denial justified an explicit account-free privilege comparison rather than assuming root would fix enrollment. Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41770219993 passed on both architectures with 17 Python tests each plus native contracts. ARM's runner-user primary import observed one failed fpsd-area open (EACCES); root observed one successful open. Root's diversity snapshot had no matching calls. Both users still rejected the fixed invalid samples with -42023 / -42018. Context stability was checked after both imports, and the four expected nonempty SIDB/SIDS flags remained false. Intel recorded no matching calls for either user and rejected both samples.

The workflow now has an explicit native_user choice, defaulting to runner. The login client always remains under the runner user. Root is limited to the native client in the disposable GitHub runner; it receives the private session through stdin, with only PATH, HOME, GITHUB_ACTIONS and the optional tracing flag forwarded through a cleared environment. The report must independently confirm effective root execution. No system-process injection, entitlement signing workaround, directory permission change or deauthorization is performed.

Real trial https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41770295634 passed 29 Python and 11 Swift tests plus native contracts before credentials were supplied. Root execution was confirmed. The server again issued both bags, with HTTP 200 and no business failure. The primary import observed one successful fpsd-area open and no recorded failure, yet returned -42023. Diversity returned -42032, with no matching operations captured; no keybag retry occurred. The workflow correctly failed with diversitybag_import_failed. All four nonempty SIDB/SIDS flags remained false, and neither enrollment recovery nor decryption was established.

Removing the observed access denial did not resolve these import errors in this trial. This does not rule out every permission, identity, entitlement, storage, cryptographic or VM prerequisite; the instrumentation is deliberately incomplete. The real trial has both a user change and instrumentation compared with earlier real runs, so it is not a proof that the original runner-user failure had the same file-I/O cause.

The latest response also set the historical message_mentions_computer_limit flag, whose implementation only checks for the literal phrases "five computers" or "5 computers". **That flag is a mention classifier, not a confirmed quota-exceeded response or an authorization count.** No raw message was retained, and HTTP/business success plus a keybag was still observed. Further account-bearing authorization repeats are suspended pending a substantive new diagnostic and clarified quota evidence; no other machine's authorization is revoked. There have now been five private trials returning keybag data, none with verified import success.

The final account-free validation https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41770552591 passed both architectures with 19 Python checks each plus native I/O and response contracts. It additionally tested terminating an actual root-owned synthetic sleep worker on timeout, verified pipe closure, and checked that cleanup addresses only that child process group with a cleared environment. The native diagnostic also has a 70-second process deadline. These checks validate bounded execution and reporting; they are not new enrollment attempts.

## CommerceKit service prerequisite (2026-11-04)

This is a new account-free service path, separate from the earlier ASDFairPlayService rejection and the direct AMS keybag import failures. No Apple Secrets were supplied in the runs below. No server authorization request, import, account deauthorization, enrollment capture, model recovery, or real IPA decryption was performed.

### Source and runtime evidence

Scoped native inspection https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41773722865 passed on ARM and Intel with five Python checks per architecture and all ten requested CommerceKit implementations found. Limiting each inspection to AMS or CommerceKit keeps the bounded disassembly report useful; an earlier empty ARM report did not establish that CommerceKit could not load.

The inspected CKMachineAuthorizationContext code sends transaction type 2 for machine authorization through the commerce service. Its reply block has four parameters: success, NSData sync data, a diversitybag-needed flag, and NSError. A two-argument callback would be incorrect. The account-free probe constructs a CKStoreAccount directly from a fixed plist and verifies its dsID getter; it does not read a real system account or secure token.

The inspected CKStoreClient initializer checks case-sensitive identifier prefixes. The earlier mixed-case com.apple.AppStore identifier was not accepted and returned nil. The probe now uses the supported com.apple.configurator.ui identifier. This selects the framework's existing Configurator client behavior; it does not establish an entitlement grant or an authorization state.

Earlier crashes were localized using bounded stack metadata from our own synthetic process. The stacks ended in objc_release inside SyntheticAccount. Initializers had been called through untyped objc_msgSend casts, which did not express ARC initializer ownership. Typed initializer declarations and a replacement-object initializer contract fixed that implementation defect. The debugger helper emits only bounded allowlisted symbol/module names and offsets, never arguments, registers, heap contents, or raw debugger output.

### Latest observed result

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41774463734 at commit 5f856eb5e940a12bae2577154792c9fc66be7fe0 passed on both architectures. Each job passed seven Python checks and the native error/initializer contract, then compared separate runner-user and root processes with fixed zero and nonzero synthetic account values.

| Architecture / user | Client and synthetic account | Request and reply | Observed result |
| --- | --- | --- | --- |
| ARM / runner | Created; runtime ABI and dsID check passed | Type 2 request sent; successful reply, nonempty bounded NSData, no error | synthetic_sync_ready; need_diversitybag=true |
| Intel / runner | Created; runtime ABI and dsID check passed | Same evidence for both fixed values | synthetic_sync_ready; need_diversitybag=true |
| ARM / root | Created; account checks passed | Service method ABI check failed; no generation request submitted | interface_unavailable |
| Intel / root | Created; account checks passed | Same result for both fixed values | interface_unavailable |

The root result does not establish a particular entitlement, connection, or daemon failure. It only establishes that this invocation did not expose the expected interface. The working ordinary-user route is the next candidate for study.

All four expected nonempty SIDB/SIDS flags remained false before and after each probe. These four flags are deliberately limited observations, not a complete filesystem audit. Generated sync bytes were retained only inside the short-lived native process and were not printed, saved in artifacts, or returned to the public report.

A green workflow means the bounded diagnostic completed and its contracts passed. The per-case report, not workflow color, determines whether the service prerequisite succeeded. Neither the successful synthetic reply nor the presence of diversitybag requirements demonstrates real-account enrollment, a usable model, or decrypted code.

### Next evidence required

Inspect the framework's import and completion behavior before invoking the import service: CommerceService's importKeyBag:diversityBag: method has no reply parameter, so return from that call cannot prove an import succeeded. Establish an observable result and bounded cleanup with synthetic fixtures first. Real authorization repeats remain subject to the previously recorded uncertainty about the five-computer wording; no other machine's authorization is revoked. A substantive new route must still prove actual import, matching model recovery, and complete encrypted-slice verification before any decryption claim.

## CommerceKit import observations and request construction (2026-11-04)

### Completion semantics

Native response-callback inspection https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41775035009 passed on ARM and Intel, with five Python checks each. The inspected callback reads keybag and diversitybag, invokes importKeyBag:diversityBag: when either exists, and subsequently reports the store response's error through its completion handler. There is no import-result callback in that invocation. The deauthorization branch was inspected statically only and was not executed.

This is why the new probe treats an import call returning and a later successful kbSync reply as availability observations, not an import acknowledgment or ordering guarantee.

### Fixed invalid bags and bounded log windows

The first invalid-input run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41775565133 passed on both architectures, with 12 Python checks per job and the native error/initializer contract. It compared a no-import baseline with two fixed zero-filled arrays (32-byte keybag, 16-byte diversitybag). It supplied no Apple credentials and made no server authorization request. Both cases generated baseline and follow-up sync data; the invalid case's no-reply call returned. All four observed nonempty SIDB/SIDS flags stayed false.

The follow-up https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41775774340 passed 17 Python checks per architecture plus the native contract. It additionally reduced a precise, short system-log time window to counts and a fixed error-code allowlist:

| Architecture / case | Import-related log observation | State and interpretation |
| --- | --- | --- |
| ARM / no import | No matching events | Four expected nonempty file flags false |
| ARM / invalid bags | Two import-failure mentions; known-code set contains -42018 | Call returned; follow-up sync succeeded; import remains unverified |
| Intel / no import | No matching events | Four flags false |
| Intel / invalid bags | No matching events | Call returned; follow-up sync succeeded; import remains unverified |

The log filter accepts only commerce/fpsd events within the measured interval. Raw messages, paths, identifiers and unrecognized numeric values are discarded. A known-code set does not assign a separate result to each bag. Missing Intel events do not establish that the handler did not run or that import succeeded; logging coverage and timing are limited. Logs and file-presence observations never set import_verified, enrollment_created or decryption_proven to true.

Log reads are limited to 15 seconds and a one-MiB accepted report. The native control has a 25-second process deadline and the wrapper a 30-second timeout. Only read-only log collection uses sudo; imports execute as the ordinary runner user. The generic child-group cleanup already handles elevated read-only log processes. No artifact contains raw logs or sync data.

Shared request-generation callbacks now collect replies under their own lock before merging the sanitized metadata into the main report. Regression run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41775607926 passed 12 Python checks per architecture and retained the earlier runner-success/root-interface-unavailable results.

### Constructing, but not sending, a native request

Inspection https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41776041134 found all six selected request-construction methods on both architectures with five Python checks each. CKStoreRequest's _URLRequestWithError: delegates to the system service's URLRequestForStoreRequest:reply: and returns a NSURLRequest/NSError pair. Our probe does not call runAsyncWithCompletionHandler:, runSync:, or a network task to execute that returned authorization request.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41776353497 at dcc32601eeaa456f3b7e3a86a33c4a9d59090eaa passed on ARM and Intel, with 17 Python checks each. A fixed synthetic account and fixed non-secret token generated a four-field native body: machineName, kbsync, needDiv and xToken. The returned request was an HTTPS POST to the expected buy.itunes.apple.com machine-authorization path, preserved the sync/token/diversity fields, and had a six-byte-format GUID in its plist body. Values and the request itself were not published.

This test deliberately distinguishes basic construction from real-session readiness. The body ownerDsid and X-Dsid header did not match the fixed synthetic account, and the User-Agent did not pass the Configurator-prefix check. These false flags alone do not distinguish absent fields from another value. ARM had both inspected Anisette headers, while Intel did not have both; header presence is not proof that their contents are valid.

No authorization request, login, or import occurred in this construction run. The four state flags remained false, no model was captured, and no encrypted IPA was decrypted. The next work is identity/header binding and proving that the request uses a GUID consistent with the authenticated download session, without overwriting a mismatched native identity. These prerequisites must be checked before a real service-based enrollment trial is meaningful.

## CommerceKit session binding and server refusal (2026-11-04)

### Closing the identity and header gap

The pinned download client's DeviceIdentifier.system implementation reads en0, falling back to en1, and produces an uppercase six-byte MAC-format GUID. The workflow now compiles that exact upstream source at ApplePackage 391bfe6ee6598d73e4f94b88b38b50bd6f6ec67b with a minimal helper. Its value travels only through private process pipes; no device identifier is printed or passed as a command-line argument. An initial standalone Swift helper declaration returned Void where the upstream guard requires Never; run 41777038680 stopped at compilation without invoking an account, and commit 49105eb corrected the declaration.

Binding run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41777147010 passed on ARM and Intel with 19 Python checks each and a native binding contract. The system-generated GUID exactly matched the pinned client's value on both runners. The earlier ownerDsid flag was false because that field was absent. Binding supplies the matching account identifier and session headers, applies the same login User-Agent, updates Content-Length, and preserves GUID, sync data, token and needDiv. It rejects conflicting identities, unsupported destinations/methods/query fields, existing action signatures, malformed tokens and header-control characters. The input NSURLRequest remains unchanged on both success and rejection.

The actual machine-enrollment binary now shares that constructor. Account-free preflight https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41777899832 passed 53 Python checks per architecture plus the native binding and response contracts. Both actual clients reported commerce_request_prepared, verified identity, one fixed Cookie, and the same NSXPC connection object through preparation. This is object-identity evidence, not a guarantee that a daemon's internal cryptographic state cannot change.

Invalid-import regression https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41777902392 passed 24 Python checks per architecture and the native contract. It retained ARM's two failure-log mentions with known code -42018 and Intel's lack of matching messages. Only fixed invalid data was supplied.

### One substantive real trial

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41778198600 at 6cb9707aa863aaf6eb42edf89005eb620791cc8c selected backend=commerce, native_user=runner, purpose=signIn, session_context=cookies and client_context=login_agent. Before exposing credentials it passed 59 Python tests, 11 Swift tests, native contracts and the actual constructor's no-submit preflight.

The Store login succeeded. The native account DSID/token checks, GUID comparison, session binding, User-Agent and connection checks passed. Eight filtered session cookies were attached. The CommerceKit-generated request also had a storefront header; this differs from the older direct-AMS request path and remains a documented difference rather than an isolated cause.

The single authorization request received HTTP 200 but a business failure with failureType 3002. The fixed message classifier found the phrase "five computers" or "5 computers". No keybag was present, no redirect occurred, and no keybag or diversitybag import was attempted. The four expected nonempty SIDB/SIDS flags stayed false; the bounded service-log window contained no matching import events. There is no new model, capture, or decrypted IPA.

This combination strongly points to the computer-authorization limit, rather than merely treating any HTTP 200 as success. It is still not a direct account-settings count, a list of affected computers, or an official Apple mapping of error code 3002. The full response text and private account/device values were not retained.

Apple's current official guidance says an account can authorize up to five computers simultaneously, provides Mac/Windows account-settings steps for checking the count, and limits "Deauthorize All" to once a year: https://support.apple.com/zh-cn/118292. That page supports the general rule; it does not independently establish this account's current count.

Earlier research returned keybag data in five separate trials. Those disposable-runner authorizations may have contributed to the limit; existing sanitized records do not establish which computers are counted. No deauthorization was attempted and no other device's authorization was changed. Further real authorization submissions are suspended until available slots are verified or new evidence changes this diagnosis. This does not block account-free implementation review or synthetic verification.

### Final reporting regression

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41778381405 at a521dd5c418abdf12ec7a8d40651f0a88b97bef8 passed on both architectures with 55 Python tests each, the native binding contract and the response/client-context contracts. Both public probes again reported only synthetic binding and no-submit preparation.

The CommerceKit backend always reports import_verified=false and cannot reuse the direct AMS backend's keybag_imported_model_unverified success status. Even a returned import call, follow-up sync response, changed file flag or success wording in a log is insufficient to establish a recovered enrollment model or verified decryption.

## Account-management entry points without a personal computer (2026-11-04)

These experiments stayed on GitHub-hosted runners without a separate computer or an iPhone node.

Read-only static inspection https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41779680901 at 43eae55b06455719058cc08f8df99ba2eb75e13f found all six selected methods on ARM and Intel. The workflow loaded system frameworks into its own account-free process and disassembled the allowlisted methods. It did not invoke those methods or use account secrets.

- CKAccountStore.viewAccount formats a store URL scheme with action=modifyAccount and calls NSWorkspace.openURL:. It is a UI entry point, not a count-returning API.
- CKMachineAuthorizationContext.deauthorizeMachineWithCompletionHandler: constructs an authentication dialog and calls authenticateWithDialog:completionHandler:. This inspection does not establish an API for deauthorizing every computer and did not execute any deauthorization.
- AMSAccountDeviceInfoTask._requestWithURL: creates a POST request with an sn query item. The observed update method stores isBundleOwner on the local account. This evidence is insufficient to treat that task as a computer-authorization inventory or to invoke it merely because its name contains DeviceInfo.
- No search result or inspected interface established a working direct deauthorize-all capability. Failure to find one is not proof that no such internal interface exists.

Apple's published self-service steps currently use Music/Apple TV on Mac or Windows: https://support.apple.com/zh-cn/118292. The documentation does not establish an equivalent iPhone self-service control. Mobile users can contact Apple Support through https://support.apple.com/zh-cn/contact to ask an adviser to verify the authorization count and available options; assistance or a reset is not guaranteed.

The GitHub automation for account-wide removal remains unimplemented and unverified. No authorization count was retrieved, no device was removed, no all-device reset was performed, and no new enrollment request was sent. Any future account-wide removal must have explicit scope approval because it affects existing computers and the published all-device operation has an annual limit.


### Official Music UI capability on GitHub-hosted Macs

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41780878891 at 6f6894d0576f36ff815183bc7682594954566c15 completed successfully on macos-15 (ARM) and macos-15-intel. Both compiled the new NativeAccountManagementCapabilities.m probe with -Wall -Wextra -Werror and ran it without account secrets.

Both runners reported an on-console session, installed Music application, successful Music launch, existing accessibility trust, and successful menu reads. The fixed-label detector saw Account, Sign In, and Authorizations. It did not observe the Account Settings, Authorize This Computer or Deauthorize This Computer labels; this bounded traversal does not establish that those controls are absent or usable after login.

The itms/itmss schemes resolve to com.apple.Music and macappstores resolves to com.apple.AppStore. The probe resolved those handlers but did not open an account URL. It launched Music, read menu attributes, and requested termination of its newly opened application; it did not perform accessibility actions, prompt for new permissions, change TCC settings, enter credentials, sign in, submit authorization, or remove any authorization.

The report contains only fixed schema fields, fixed app identifiers, booleans and fixed error categories. It does not export screenshots, window contents, arbitrary menu text, account identifiers or credentials. The workflow has no Secrets bindings, read-only repository permissions, pinned checkout, a three-minute job limit, a one-minute execution step and a 40-second process deadline.

This establishes a usable GUI foundation for an alternative GitHub-only investigation through Apple's official application. It is not a working account-management implementation. Account login, access to the account settings page, the actual authorized-computer count, and any reset operation remain unverified. The next evidence needed is bounded navigation to the official account page and a private, read-only count query. No further real enrollment attempt is justified solely by this capability result. Account-wide removal still requires explicit scope approval after a concrete supported method is prepared.

The official instructions continue to place computer-authorization management in Music/Apple TV on Mac or Windows: https://support.apple.com/zh-cn/118292. The public web research did not establish an equivalent mobile-browser control; that is an evidence gap, not proof that every web route is impossible.

## Official Music UI navigation and private account query (2026-11-04)

The GitHub-only route now goes beyond opening the application. Account-free run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41827608688 at 594371f45f4021ea7bb85102ab0340fc6ecaaed3 reached the official Music sign-in window on ARM and Intel.

The initial Music welcome sheet blocked the Sign In menu. The navigation helper recognizes that sheet and its Start Listening control, then declines the following optional sheet through its Not Now text. That text did not expose AXPress. The fallback uses its current accessibility geometry, verifies the hit-tested element still has the same process and exact Not Now label, and posts one mouse click. No coordinate is guessed and no Continue/subscription/account-security-upgrade action is used. Both architectures then successfully invoked Account > Sign In and observed the Apple Account placeholder. The first login step has an email field only.

A narrowly scoped account-free diagnostic at https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41826789540 reported only the first welcome sheet's fixed button caption, Start Listening. That temporary caption extractor was removed after identifying the control. Current diagnostics classify labels into fixed enums and do not emit arbitrary UI text.

### Private input and read-only count workflow

The new music-account-query.yml defaults to preflight. Query mode requires both architecture checks, then runs one ARM job with another control preflight before exposing Secrets. It shares the actual navigation implementation with the account-free tool.

Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41828237601 at 78ee6fcc9347ad3cc4b029bebbe39ff13242618e passed on both architectures:
- Eight Python tests cover credential transport, output filtering, timeout cleanup, numeric count validation and required count evidence.
- Native contracts cover allowed navigation actions, private-value reporting and exclusion of policy limits/associated-device totals from the count parser.
- The actual client located the email field, filled a synthetic invalid-domain email without submitting it, observed the Sign In button become enabled, and cleared the field.

The private wrapper passes account credentials only through stdin, not command arguments or the child environment; discards native stderr; and emits only an allowlisted report. UI static text may be classified privately, but arbitrary text, field values, screenshots, account identifiers and passwords are not exported. No account data or build cache is uploaded after login. Account state remains only in the disposable GitHub runner.

The query client allows one email submission and one password submission, waits for an enabled Sign Out menu as sign-in evidence, then opens Account Settings and looks for an explicit current computer-authorization count. It does not call Authorize This Computer, Deauthorize This Computer or Deauthorize All, and does not accept an optional security upgrade. This is an application sign-in: flags describe actions explicitly invoked by this client, not proof that Apple's application performs no background account activity.

The parser requires an authorization-section label and an explicit current-usage sentence, with a count from zero through five. It rejects policy text such as "up to five", associated-device totals, conflicting counts and missing evidence. A page that does not expose that exact evidence must remain count_not_observed; a green build or available GUI is not a count result.


### Actual query attempts and current blocker

- Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41828426165 stopped at an Intel navigation preflight failure. The query job was skipped; that run did not submit real credentials. Fixed-duration assumptions were replaced with bounded waits for observable first-run UI transitions, and a fixed navigation-status summary was added.
- Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41828828697 passed both architecture preflights and the same-runner preflight. The actual official Music flow submitted the account email and then password, but did not observe an enabled Sign Out menu within the initial wait. It reported signin_unconfirmed, not successful login or a password error.
- Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41829387679 at e82027284af9736bf93ab6f4fb3e1f30949ed923 extended the login wait to at most 60 seconds and inspected the authentication window separately from the main Music window. After password submission, the fixed-label classifier observed an unknown-error message. It did not observe a successful login or enter Account Settings.
- Run https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41830015849 at ebcb9239c806bb0b84cecc452d8102d6128aaf54 reproduced the official unknown-error UI and collected a bounded authentication-log summary from the same invocation. Both architecture verification jobs passed 20 Python tests (8 private-query and 12 native-log diagnostics), native navigation/query contracts, log availability checks and synthetic control preflights. The query job also passed its preflight. Its final failure is the actual unresolved sign-in, not a compilation or privacy-test failure.

The last real report has credentials_used, email_form_ready, email_submit_attempted, password_form_ready and password_submit_attempted true. signed_in_menu_observed, account_settings_invoked, authorization_section_observed, explicit_current_count_observed and authorization_count_retrieved remain false. Explicit machine authorization, deauthorization and security-upgrade acceptance remain false. No account-settings count, recovered enrollment model or verified decrypted IPA was obtained.

### Authentication diagnostic evidence

The existing native_auth_diagnostics.py collector was extended to include Music, with a new privacy test. It reads a bounded system-log interval in memory and returns only allowlisted process names, error domains, error/status codes, fixed reason flags and bounded counts. Raw log messages, account identifiers, credentials, timestamps and paths are not exported. This does not capture or expose Apple's SRP proof bytes.

The last invocation examined 30 matching events without hitting output, event, record or cooccurrence limits. Relevant observations:
- akd reported the fixed server_authentication_failed and srp_server_proof_missing flags. The latter corresponds to the literal M2 missing diagnostic.
- AKAuthenticationError -7012 occurred in an authentication-context event.
- com.apple.AppleIDAuthSupport code 2 occurred twice in authentication-context events. One such event also contained the server_authentication_failed flag.
- Music also reported AMSErrorDomain 204, while other akd records included XPC/connection and additional AuthKit codes. Those records are not independently assigned as the cause.

M2 missing and -7012 were not reported as a same-event causal chain. The summary narrows the visible failure to the native authentication exchange, but does not prove that the password is wrong, that two-factor authentication is enabled, that a particular certificate or machine identity is responsible, or that every Apple authentication path fails. The separately verified Swift downloader login path remains distinct.

At this point the GUI navigation is implemented and verified; official native sign-in and authorization-count retrieval are not. Further identical credential submissions would not address the observed failure. A changed authentication path or evidence-based correction is needed before another real trial. An alternative worth investigating is whether the already working downloader session can support a legitimate read-only account-information request; no such account-count endpoint or session handoff has yet been established.

The earlier CommerceKit machine-authorization response still contains business failure 3002 and five-computer wording, with no keybag. The account's actual count remains unknown. No Deauthorize All operation was prepared or executed, and its account-wide scope and annual-use consequences still require explicit owner approval once a concrete working method exists.


## Downloader-session account summary (2026-11-04)

### Purpose and scope

The previous official Music route reached the email/password form but could not establish a signed-in native account. This experiment asks whether the already working signed downloader session can read the **actual authorized-computer count**, without requesting another machine authorization. It does not deauthorize any computer, reset a quota, create a FairPlay model, or prove decryption.

### Current Apple public frontend

The credential-free [Store bag probe](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41832531401) found that `accountSummary` points to an Apple static account-settings page on `apps.mzstatic.com`. This is a frontend URL, not an authenticated account response.

The [bounded public frontend inspection](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41834004314) followed only the advertised content root and read static JavaScript without executing it or supplying credentials. It established:

- Bag key `accountSummaryGraphQL` defaults to `https://buy.itunes.apple.com/account/v1/summary/graphql`.
- The first-party `requestAccountSummary` query includes `authorizations.authorizedComputers`.
- `linkedDevices` is a distinct field and must not be used as a computer-authorization count.
- Modules 9783 and 86014 send a JSON POST and select a native Apple Media Services transport or a web transport. Native account-manager success is therefore not implied by identifying the endpoint.

The lab requests only:

```graphql
query requestAccountSummary {
  authorizations {
    authorizedComputers
  }
}
```

It does not send the full frontend query, which also contains payment and personal account fields.

### Implementation and verification

`tools/store_account_summary.py` uses the pinned Swift login (`Lakr233/ApplePackage@391bfe6ee6598d73e4f94b88b38b50bd6f6ec67b`) with purpose `signIn`. The private handoff keeps DSID, token, GUID, original User-Agent, storefront, and scoped cookies on the ephemeral runner. It is validated for ownership, file mode, type and size, then deleted. Login stdout/stderr and authenticated response bodies are not published.

The request destination and read-only query are fixed. At most one HTTP 307/308 to an explicitly allowed Apple buy pod with the identical path is followed. Cookies are rebuilt for the destination and checked for domain, path, expiry, header injection and total size. Responses are limited to 1 MiB; only an integer 0–5 at the exact GraphQL field is accepted, following confirmed Store login and HTTP 200 with no GraphQL errors. Partial data, linked-device counts, booleans and strings cannot produce success.

[Workflow evidence](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41834443913): Linux passed 20 synthetic tests; the no-credential query returned HTTP 401. This establishes endpoint reachability and authentication enforcement, not a working authenticated account session.

### Real result

The macOS job also passed all 20 Python tests and the 11 pinned Swift SAP authentication tests. The signed downloader login succeeded. The fixed account-summary query returned HTTP 200, JSON, and **`data.authorizations.authorizedComputers = 5`**. The exact login User-Agent and a matching scoped Cookie header were present; no redirect was needed.

The published result is `computer_count_observed`, not a model or decryption success. Both `machine_authorization_attempted` and `deauthorization_attempted` are false. The run did not call either machine-management endpoint, accept a security upgrade, or expose the account identity or response body.

This is stronger evidence than the earlier 3002/five-computers diagnostic: the account's current count is now confirmed directly. It does **not** identify the computers, establish whether the earlier ephemeral runners occupy all slots, or make account-wide deauthorization authorized. Five computers is Apple's documented ceiling; a local code change cannot raise that service-side limit. The next review concerns the official deauthorization mechanism and its account-wide/yearly consequences, before any account-changing action.

The prior native Music/AuthKit login failure remains unresolved, but it no longer prevents this read-only account-count check.

All builds, tests and requests ran on GitHub-hosted runners. The public repository contains source, synthetic fixtures and bounded diagnostic results only.


### Prepared all-computer deauthorization; not executed

The [public settings-component inspection](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41835510353) found the actual confirmation action in both legacy and current Apple desktop account components. After its confirmation dialog, the frontend resolves `deauthAllMachines` and sends a JSON-content-type POST with no request body. Its default route is `/account/deauthAllMachines`. The button is shown for at least two authorized computers; this UI condition does **not** establish that the account is eligible under the yearly limit.

Apple documents that deauthorizing inaccessible computers uses **Deauthorize All**, affects computer purchase access, requires reauthorizing computers still in use, and is available only once per year: [Apple Support](https://support.apple.com/en-us/118292). This is a different operation from removing a linked iPhone, MusicKit permission, or TVKit permission. The lab has not performed it.

`tools/store_deauthorization.py` and `.github/workflows/store-deauthorization.yml` prepare a separately gated operation:

1. Default `preview` exposes no Secrets, performs no network requests and shows the precise operation and consequences.
2. Execution requires both `mode=deauthorize` and the exact acknowledgement `DEAUTHORIZE ALL 5 COMPUTERS`, supplied **only after explicit account-owner approval**.
3. A fresh signed Store login and read-only query must still confirm exactly five computers. An unavailable or changed count stops before mutation.
4. The fixed Apple endpoint receives at most **one** empty-body POST. No mutation redirect or retry is followed, including after timeout.
5. A separate read-only query checks the outcome. HTTP 200 alone does not count as success; the count must become zero. Unknown/error outcomes retain the attempt state and must not be blindly retried.
6. The operation does not request new machine authorization, accept a security upgrade, or run enrollment/decryption. Releasing quota would not itself prove that keybag import or model recovery works.

[Preview verification](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41836096346) passed **38 tests on Linux and 38 on macOS** (20 read-only session/transport tests plus 18 operation tests). Both previews reported no credentials, no network request and zero mutation attempts. The real `deauthorize` job was **skipped**.

The [final public-origin check](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41836095534) resolved module 37689's `hW` constant to `https://buy.itunes.apple.com`; module 57801 binds `DeauthAllMachines` to `/account/deauthAllMachines`. This confirms the prepared request's exact host/path from current public source. Synthetic tests do not establish that the server will accept an eventual real operation or that the account's yearly eligibility remains available.

At the time of the preparation above, no account-wide approval or real execution had occurred. The subsequent approved operation is documented below.


## Approved computer deauthorization (2026-11-04)

One account-wide computer deauthorization was explicitly confirmed before run 41837099155. The approved workflow was dispatched once at commit 294c5184c8656def5eddeb4ea21f1a079a1f7319. This is not permission to repeat the yearly account-wide operation.

[Run 41837099155](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41837099155) completed successfully. Linux and macOS verification passed; the real job passed the 20 session tests and 11 Swift authentication tests before receiving account credentials. A fresh signed login and account-summary query confirmed five computers. The single empty-body POST to the reviewed Apple endpoint returned HTTP 200, without redirect or oversized response. The follow-up read-only query confirmed **zero** computers.

The result is `deauthorization_confirmed`, with `count_before=5`, `count_after=0`, `mutation_request_count=1`, and `automatic_retry=false`. This run did not issue a new machine authorization, create an enrollment model, or verify decryption. Existing computer purchase authorizations were revoked as approved. The annual all-computer operation must not be repeated as routine cleanup.

With the quota condition now changed, one follow-up CommerceKit enrollment trial has been dispatched using the previously validated login identity, GUID, token, User-Agent, and Cookie bindings. Its result is pending; the zero count above records the state immediately after deauthorization, not a guarantee that future authorization leaves it unchanged.


## CommerceKit creates SIDB; privileged visibility correction (2026-11-04)

After the approved five-to-zero deauthorization, [run 41837662134](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41837662134) passed 60 Python and 11 Swift tests, logged in, and obtained keybag plus diversitybag with HTTP 200 and no business failure. The CommerceKit connection remained stable, the one-way import returned, and follow-up synchronization no longer requested a diversitybag. No matching import-log events were found; this is not proof of absence of errors. The legacy four file flags remained false and the run correctly exited unverified.

Review found that those booleans conflated nonexistent files with inaccessible paths. The [credential-free visibility probe](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41839020872) passed 59 tests and demonstrated that the ordinary runner cannot inspect the fpsd state directory, while root can. On that fresh account-free runner the four files were absent even as root.

The observed enrollment path now:

- Requires a successful read-only current computer-count query before authorization.
- Stops without native authorization if the count is unavailable or already five.
- Requires successful administrator metadata observation before the request.
- Records current-user and root state before and after, plus the account count after the attempt.
- Retains the initial diversitybag requirement separately from the follow-up result.
- Never treats permission denial, a successful HTTP response, or an asynchronous import return as complete model recovery.

[Real observed run 41839179045](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41839179045), commit f8736886ab85708ef0ec8617f4ba6845cc5c1bf5, passed 95 Python tests, 11 Swift tests and native contracts:

- Account count: **1 before, 2 after**.
- Authenticated authorization: HTTP 200, keybag and diversitybag present, no business error, no redirect.
- Initial request required diversitybag; post-import service synchronization did not.
- Root saw the fixed fpsd SIDB change from **missing to regular_nonempty**.
- The fpsd SIDS and both shared SC Info files remained missing in the root observations.
- The ordinary process still reported permission denied for both fpsd paths.
- No state-file contents, account identifiers or hardware identifiers were emitted.

This establishes generation of a nonempty SIDB in the protected expected location, not its valid enrollment records, a recovered model, complete import success, or verified decrypted bytes. The old false flags cannot be interpreted as evidence that this protected file did not exist. The first post-reset trial was not observed as root, so its file creation is not claimed retrospectively.

The metadata-only inventory is bounded by fixed roots, depth, entry count and time. It does not cover the entire machine. [Final account-free regression 41839639815](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41839639815) passed 60 tests and added an explicit depth-limit flag plus the system-preferences root. No further authorization was requested by that regression.

### Same-runner recovery attempt prepared

The new model-bootstrap workflow builds both pinned Swift variants, the pinned kbsync helper and UnfairPlay before providing Apple Secrets. Separate source trees avoid overlapping enrollment and downloader patches. One native enrollment, original IPA download, root-only collection/recovery and full IPA verification then occur on the same runner.

The app input is explicitly an extracted IPA candidate, not a claimed native App Store installation. UnfairPlay's SINF, SIDB, hardware, selector and page-validation checks remain intact. An unsupported candidate or unmatched enrollment must fail; no fabricated files, relaxed checks, cryptid changes or synthetic report may substitute for real recovery.

If setup produces a private model, the existing offline adapter independently checks the exact encrypted-slice coverage and available pre-encryption page hashes. A verified model can be sealed with libsodium-compatible anonymous boxes (pinned Go x/crypto dependency) to the GitHub repository's public key. Only that ciphertext and its public key ID may be relayed for creating FAIRPLAY_MODEL_B64; no model plaintext, credential, selector, state capture or IPA is uploaded or logged. The key was obtained from the repository's own GitHub public-key API, and the Secret did not exist when preparation began. Existing model Secrets must not be overwritten blindly.

This recovery workflow is newly prepared and still requires its real result; SIDB generation alone is not model recovery.


## Same-runner recovery rejected; quota preserved for diagnosis (2026-11-04)

[Run 41841347693](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41841347693) at commit 81796a77fc0f5ec1b004198365ffd682c5aa0948 passed 122 Python tests, 11 Swift enrollment tests, 9 Swift download tests, the pinned recovery/verification Go packages, the kbsync and sealed-box Go tests, and native contracts before exposing Apple credentials. The earlier run 41840968459 failed only a macOS /var versus /private/var canonical-path test before credentials; the test was corrected without weakening the implementation.

The real trial authenticated, made one CommerceKit authorization request, obtained keybag and diversitybag with HTTP 200 and no business failure, and changed protected fpsd SIDB from missing to regular_nonempty. The independently queried account count changed from **2 to 3**. This is the third post-reset authorization, not another all-computer deauthorization. The approved annual all-computer action has not been repeated.

The original IPA downloaded successfully and was safely extracted as an explicit candidate app. The pinned engine rejected recovery with nonzero status; the wrapper emitted `model_recovery_rejected`, `model_recovered=false`, `decryption_proven=false` and `plaintext_verified=false`. No model ciphertext was emitted and no model Secret was created. No private capture, IPA, raw upstream error or plaintext was exported.

The original keyword-only diagnostic found SIDB and SINF mentions, but the upstream recovery progress itself contains both words. Those flags do not establish a SIDB/SINF mismatch, an unsupported layout, or the exact failure stage. The raw error was discarded, so it cannot be reconstructed from the public report. Do not infer a completed derivation step or changed cryptographic validity from those mentions.

Commit 2d60d448dfc364679b24d603d0a7ae97049b5871 moves original download, safe extraction and the pinned engine's structural IPA doctor check ahead of machine authorization. All inspected licenses must have the supported current layout and valid inventory/SINF checks. A dedicated `input-inspection` mode stops after this check without calling enrollment. It uses the existing Apple download session but makes no explicit computer-authorization request.

Recovery failures now parse only upstream `error: ` lines into fixed source-backed error codes. Allowlisted progress phases are reported separately; unknown messages, filenames, selectors, paths and account values never pass through. Synthetic regressions cover progress/error separation, unknown-message privacy, incompatible license inputs, failed downloads and the no-enrollment inspection mode. New verification is pending. No fourth real authorization has been dispatched.


### License-only inspection and private checkpoint preparation

[Run 41843509689](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41843509689) passed 128 Python tests, 20 Swift tests and the existing Go/native checks. The real original-download inspection succeeded: inventory and SINF parsing passed, the single inspected license used the current supported layout, and no legacy markers were reported. `authorization_request_attempted=false`; no new machine authorization, model recovery or decryption was performed. This rules out a basic unsupported SINF layout for this downloaded sample, but does not prove that the previous SIDB holds a matching usable class record.

The account-free static [callback inspection](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41843676687) passed five reporting tests on both ARM and Intel. The native deauthorization callback selects the `deauthorizeMachine` bag key before calling the existing request path. This is only inspected system code: no current-machine deauthorization request was sent and no cleanup capability is claimed working.

Commit d672630bf175644d2d508f18fd7561d37af83f32 prepares a private `FAIRPLAY_STATE_B64` checkpoint so a future single authorized runner can supply state for bounded replay trials without repeated authorization. It captures only four fixed SIDB/SIDS locations when present plus the six-byte built-in en0 hardware identity; fpsd SIDB is mandatory. Each file is capped at 16 KiB and the complete plaintext JSON is capped at 32 KiB. Symlinks, unknown paths, extra fields, invalid encodings and public file permissions are rejected. No IPA, account login session, password or arbitrary filesystem content is included.

The checkpoint is different from a verified model. Because it is needed to diagnose a failed recovery, it may be sealed **before** model verification, but only with the same fixed GitHub repository public key and a separate fixed Secret name/schema. Raw checkpoint bytes are never printed or uploaded as artifacts. The pending regression includes fixed-purpose sealed-box routing and replay tests that reject any attempt to call enrollment. The existing verified-model gate remains unchanged.

Replay downloads a fresh personalized IPA and uses the pinned engine's explicit archived-state and IOMAC inputs through `collect` and `recover`; upstream structural/authentication checks and complete IPA validation still apply. A stored checkpoint is not evidence of a working model or portable decryption. The only dispatched checkpoint workflow so far is `preflight`, without Apple credentials; no real checkpoint Secret or fourth authorization exists yet.


### Checkpoint preflight verified

[Portable contracts 41845171020](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41845171020) passed 29 Python tests on GitHub Ubuntu plus the sealed-box roundtrip/tamper/fixed-purpose Go tests. [macOS preflight 41844426287](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41844426287) passed 140 Python tests, 20 Swift tests, Go/native checks and the administrator observer, without Apple credentials. The protected native capture path itself still needs real state; synthetic tests do not establish successful real capture or recovery.

After those checks passed, a single checkpoint-bearing trial was dispatched at 2026-11-04T14:17:45Z from main at b668df099334706a9f02e6bcaf56ff553b023c8b. The core files are identical to the checked macOS commit d672630bf175644d2d508f18fd7561d37af83f32; only documents and the independent contract workflow differ. Its result is pending. The last confirmed authorized-computer count is 3; do not assume it remains 3 if this new trial reaches authorization. Do not dispatch another trial without reading its report.


## First verified GitHub-only model recovery (2026-11-04)

**[Run 41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942) succeeded** at b668df099334706a9f02e6bcaf56ff553b023c8b. It passed 140 Python tests, 20 Swift tests and the Go/native checks before the private trial. The original IPA download and supported-layout inspection completed before the one machine authorization.

The signed CommerceKit request returned HTTP 200 with keybag and diversitybag and no business error. Protected fpsd SIDB became nonempty. The independent account summary confirmed **3 -> 4** authorized computers. There was one new authorization and no deauthorization in this run.

The exact success report records:

- `status=model_recovered_and_verified`, `model_recovered=true`.
- Setup: 62 encrypted images, 12,524 decrypted pages, `setup_plaintext_verified=true`.
- Independent complete IPA verification: `offline_plaintext_verified`, 62 encrypted images, 12,524 pages, `decryption_proven=true`, `plaintext_verified=true`.
- `runtime_verified=false`, `plaintext_retained=false`, `model_plaintext_published=false`.
- `state_checkpoint_status=checkpoint_sealed`; both model and state ciphertext emitted through their fixed repository key/schema/Secret bindings.

The candidate app was extracted from the original IPA. It was not represented as an installed or running Mac app. Neither the underlying recovery/authentication checks nor full IPA validation was relaxed. The independent verifier compared the audited encrypted-slice count against the engine report and required the available pre-encryption CodeDirectory page hashes to match. This is real cryptographic plaintext validation for this sample; it is not independent Apple CMS trust validation or an installation/runtime test.

The inner CommerceKit report still says `commerce_import_unverified` / `import_verified=false`, because its one-way import call has no receipt. The outer result establishes the stronger downstream evidence separately: the generated native state produced a model that passed complete IPA validation. Do not rewrite the native call's own semantics merely to make all intermediate statuses green.

The older trial 41841347693 was rejected, while this version downloaded before enrollment, added checkpoint capture/diagnostics, and ran on a different host. This is not a single-variable experiment. The current evidence does not isolate a unique cause for the old rejection.

### Private Secret persistence and independent reuse

After checking that the repository public key was unchanged and neither destination Secret existed, the already-sealed ciphertext was submitted through the GitHub Secrets REST API. `FAIRPLAY_MODEL_B64` and `FAIRPLAY_STATE_B64` were both created at **2026-11-04T14:22:53Z**. Plaintext model/state material never entered this editing workspace, the repository or public logs. No broad write token was given to the macOS job; only the repository public key was needed by the sealer.

The state checkpoint contains only the fixed native state files plus captured IOMAC bytes, not the complete IPA or an exact archived app. Replay uses a fresh personalized IPA and still requires compatibility and complete validation. Its real replay has not yet been tested. The model itself can be tested directly without another authorization.

Accordingly, [fresh-runner offline verification 41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) was dispatched with the existing `native-store.yml` workflow and `decryption_backend=offline`. This reads the saved model Secret, signs in to download a fresh original IPA, and performs complete verification without invoking machine enrollment. Its result is pending. No fifth authorization is authorized by this dispatch and none is requested by its code path.


### Verified fresh-runner model reuse

[Run 41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) completed successfully at b668df099334706a9f02e6bcaf56ff553b023c8b. GitHub decrypted the stored `FAIRPLAY_MODEL_B64` Secret correctly: initial readiness accepted its encoding, and the final real download/verification reported `offline_plaintext_verified`, `authenticated=true`, `downloaded=true`, `decryption_proven=true`, `plaintext_verified=true`, 62 encrypted images and 12,524 decrypted pages. Plaintext was deleted and runtime remained unverified.

The run passed all 273 Python tests, 9 Swift tests, 4 C tests and the Go helper/engine tests. It used a fresh GitHub-hosted macOS runner and did not invoke machine enrollment. This establishes saved-model reuse beyond the original enrollment host for the tested account/application; other applications/accounts and actual Linux-hosted decryption are not claimed tested.

A further `checkpoint-replay` job has been dispatched solely to exercise the newly implemented archived-state path with `FAIRPLAY_STATE_B64`. Its code explicitly skips enrollment; it will attempt model derivation from the saved SIDB/IOMAC inputs and independently verify a fresh original IPA. This is an unresolved integration check for the optional recovery checkpoint, not another machine authorization or a repeat of the successful model Secret check.


### Verified real checkpoint replay and phase completion

[Run 41847775765](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41847775765) completed successfully at b668df099334706a9f02e6bcaf56ff553b023c8b in `checkpoint-replay` mode. The new runner read `FAIRPLAY_STATE_B64`, downloaded and checked a fresh original IPA, materialized only fixed state files inside its private temporary directory, and supplied the archived IOMAC bytes through the pinned collector's explicit input override. It did not register the fresh host as an authorized computer or import the archived state into the host's system directories.

The real report has `state_source=github_secret_checkpoint`, `authorization_request_attempted=false`, `model_recovered=true`, `status=model_recovered_and_verified`, `decryption_proven=true` and `plaintext_verified=true`. Both recovery validation and the independent complete IPA pass report **62 encrypted images and 12,524 pages**. `runtime_verified=false` and `plaintext_retained=false`. The same 140 Python, 20 Swift and Go/native prerequisite checks passed before the private replay.

The replay also emitted a correctly bound encrypted model candidate, but the existing verified model Secret was not overwritten: the original saved model had already passed independent fresh-runner verification. No new state Secret was generated, no account-wide deauthorization was repeated, and no new computer authorization was requested. The latest directly observed account count remains 4 of 5 from the successful bootstrap.

The current research phase is therefore complete for the tested account and App ID 6599842047: GitHub-only initial native state creation, model recovery, complete original IPA plaintext validation, private Secret persistence, direct model reuse on a fresh runner, and model re-derivation from saved native state all have real evidence. This does not constitute a universal-app guarantee, a retained downloadable IPA, an installation/runtime test, independently verified Apple CMS trust, real Linux-platform decryption, Telegram integration or a deployed paid service. The requested pause on TG integration remains in effect.
