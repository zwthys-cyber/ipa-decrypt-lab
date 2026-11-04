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

Before another authenticated trial, integration must establish a compatible way to supply the independently provisioned data to the account-authentication path, obey any real verification challenge, and preserve the user's refusal of the optional security upgrade. Even successful account authentication must then create and recover matching FairPlay state and validate a real IPA. Copying an Android ADI blob into native macOS storage, renaming it as FAIRPLAY_MODEL_B64, or treating the successful prerequisite probe as decryption would be unsupported.

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

This work remains GitHub-only. It does not use the Debian server, an external Mac, the user's phone or Telegram.

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

### User-supplied candidate projects

[EEliberto/Pastel-macOS at 82576f2](https://github.com/EEliberto/Pastel-macOS/tree/82576f2295516e84b6eaa99a4e364af5e8de7664) is a downloader. Its active StoreHelper calls ipatool Download followed by ReplicateSinf, using the same pinned ipatool d9c0247 dependency already investigated here. Its November 2 fix adds missing account license files to downloaded IPAs; it does not remove Mach-O encryption. The README requires a physical Apple-silicon Mac and says virtual machines are unsupported. It is a download-flow reference, not evidence of GitHub-only enrollment.

[EthanArbuckle/fairplay-decrypt at bb09a610](https://github.com/EthanArbuckle/fairplay-decrypt/tree/bb09a61046f5c99eb1795589a307646df04b26d0) implements offline decryption using a matching 16-byte account credential. Its Python decryptor runs on macOS/Linux; its credential-retrieval workflow requires a paired jailbroken iOS device with root SSH and an installed app owned by the account. The Mac build produces iPhoneOS arm64 retriever/driver/trigger binaries; compiling them does not create a credential. This is a possible alternative offline backend, not a verified credential bootstrap for a fresh GitHub runner. No code has been imported from this GPL-3.0 repository, and no user phone has been used.

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

The user-supplied fairplay-decrypt repository's [Mac credential discussion](https://github.com/EthanArbuckle/fairplay-decrypt/issues/21) points to UnfairPlay. This matches the backend already reviewed here; that discussion supplies no first-time GitHub-runner enrollment implementation. The currently listed credential-bundle CI changes build the iOS retrieval helper, while the retrieval and device compatibility changes still rely on an enrolled device. No reviewed issue or PR is treated as proof of a device-free credential bootstrap.

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
