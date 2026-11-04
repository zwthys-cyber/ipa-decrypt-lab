// Native App Store enrollment research; run only on a disposable GitHub-hosted Mac.
import Foundation
import AppKit
import ApplicationServices
import SystemConfiguration

func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
       let line = String(data: data, encoding: .utf8) { print(line) }
}
guard ProcessInfo.processInfo.environment["GITHUB_ACTIONS"] == "true" else {
    emit(["status": "requires_github_actions", "enrollment_created": false])
    exit(2)
}
func statePresence() -> [String: Bool] {
    let paths = [
        "native_sidb": "/private/var/db/fpsd/SC Info/SC Info.sidb",
        "native_sids": "/private/var/db/fpsd/SC Info/SC Info.sids",
        "shared_sidb": "/Users/Shared/SC Info/SC Info.sidb",
    ]
    return paths.mapValues { FileManager.default.fileExists(atPath: $0) }
}
func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var result: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &result) == .success else { return nil }
    return result
}
func pressTarget(_ start: AXUIElement) -> AXUIElement? {
    var current = start
    for _ in 0..<5 {
        _ = AXUIElementSetMessagingTimeout(current, 0.5)
        let role = attribute(current, kAXRoleAttribute) as? String ?? ""
        var names: CFArray?
        let available = AXUIElementCopyActionNames(current, &names) == .success
            && ((names as? [String]) ?? []).contains(kAXPressAction)
        let enabled = attribute(current, kAXEnabledAttribute) as? Bool
        if ["AXWindow", "AXApplication", "AXMenu", "AXMenuBar", "AXMenuBarItem"].contains(role) { return nil }
        if ["AXButton", "AXLink", "AXRadioButton", "AXMenuItem", "AXRow"].contains(role) {
            if enabled == false { return nil }
            if available { return current }
        }
        guard let parent = attribute(current, kAXParentAttribute),
              CFGetTypeID(parent) == AXUIElementGetTypeID() else { return nil }
        current = unsafeBitCast(parent, to: AXUIElement.self)
    }
    return nil
}
struct UIResult {
    var windows = 0
    var nodes = 0
    var textFields = 0
    var secureFields = 0
    var signIn: AXUIElement?
    var limited = false
    var signInSeen = false
    var welcomeSeen = false
    var welcomeContinue: AXUIElement?
    var storeMenu: AXUIElement?
    var securityPrompt = false
    var signInDisabled = 0
    var signInPressable = 0
    var signInOther = 0
    var knownLabels: Set<String> = []
    var roles: [String: Int] = [:]
    var words: Set<String> = []
    var emailFields = 0
    var emailInput: AXUIElement?
    var passwordInput: AXUIElement?
    var signOut: AXUIElement?
    var declineUpgrade: AXUIElement?
    var otherOptions: AXUIElement?
    var upgradePrompt = false
    var verificationPrompt = false
    var errorPrompt = false
    var errors: Set<String> = []
    var errorCodes: Set<Int> = []
    var report: [String: Any] {
        ["window_count": windows, "nodes_examined": nodes, "text_fields": textFields,
         "secure_fields": secureFields, "sign_in_control_found": signIn != nil,
         "scan_limited": limited, "sign_in_label_seen": signInSeen,
         "welcome_seen": welcomeSeen, "continue_control_found": welcomeContinue != nil,
         "known_labels": knownLabels.sorted(), "roles": roles, "security_prompt": securityPrompt, "sign_in_disabled": signInDisabled,
         "sign_in_pressable": signInPressable, "sign_in_other": signInOther,
         "word_flags": words.sorted(), "email_fields": emailFields]
    }
}
func scan(_ app: AXUIElement) -> UIResult {
    var result = UIResult()
    let windows = attribute(app, kAXWindowsAttribute) as? [AXUIElement] ?? []
    result.windows = windows.count
    var queue = windows
    if let menu = attribute(app, kAXMenuBarAttribute),
       CFGetTypeID(menu) == AXUIElementGetTypeID() {
        queue.append(unsafeBitCast(menu, to: AXUIElement.self))
    }
    var queued: Set<CFHashCode> = Set(queue.map { CFHash($0) })
    let deadline = Date().addingTimeInterval(12)
    var cursor = 0
    var visited: Set<CFHashCode> = []
    while cursor < queue.count && cursor < 512 && Date() < deadline {
        let item = queue[cursor]
        cursor += 1
        guard visited.insert(CFHash(item)).inserted else { continue }
        result.nodes += 1
        _ = AXUIElementSetMessagingTimeout(item, 0.5)
        let role = attribute(item, kAXRoleAttribute) as? String ?? ""
        let subrole = attribute(item, kAXSubroleAttribute) as? String ?? ""
        let knownRole = ["AXWindow", "AXGroup", "AXButton", "AXStaticText", "AXTextField", "AXWebArea", "AXMenuBar", "AXMenuBarItem", "AXMenu", "AXMenuItem", "AXScrollArea", "AXImage"].contains(role) ? role : "other"
        result.roles[knownRole, default: 0] += 1
        if role == kAXTextFieldRole { result.textFields += 1 }
        if subrole == kAXSecureTextFieldSubrole { result.secureFields += 1; result.passwordInput = item }
        // Never read credential field values into text diagnostics.
        let attributes = role == kAXTextFieldRole
            ? [kAXTitleAttribute, kAXDescriptionAttribute, "AXHelp", "AXPlaceholderValue"]
            : [kAXTitleAttribute, kAXDescriptionAttribute, kAXValueAttribute, "AXHelp", "AXPlaceholderValue"]
        let strings = attributes.compactMap {
            attribute(item, $0) as? String
        }.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: ".…")).lowercased()
        }
        let vocabulary = ["app store", "apple account", "apple id", "email", "phone", "password",
                          "welcome", "discover", "privacy", "personalized", "personalised", "ads",
                          "data", "continue", "terms", "conditions", "security", "two-factor",
                          "upgrade", "verify", "verification", "search", "connect", "connection",
                          "unavailable", "cannot", "can’t", "retry", "try again", "done", "get started",
                          "sign out", "signed in"]
        for word in vocabulary where strings.contains(where: { $0.contains(word) }) { result.words.insert(word) }
        if role == kAXTextFieldRole && strings.contains(where: { value in
            ["email", "apple account", "apple id", "phone"].contains(where: { value.contains($0) })
        }) { result.emailFields += 1; result.emailInput = item }
        var actions: CFArray?
        let pressable = AXUIElementCopyActionNames(item, &actions) == .success
            && ((actions as? [String]) ?? []).contains(kAXPressAction)
        let enabled = attribute(item, kAXEnabledAttribute) as? Bool == true
        if strings.contains(where: { $0.hasPrefix("sign in") || ["登录", "登入"].contains($0) }) {
            result.signInSeen = true
            result.knownLabels.insert("sign_in")
            if attribute(item, kAXEnabledAttribute) as? Bool == false { result.signInDisabled += 1 }
            if pressable { result.signInPressable += 1 } else { result.signInOther += 1 }
            if result.signIn == nil { result.signIn = pressTarget(item) }
        }
        if strings.contains(where: { $0.contains("welcome") || $0.contains("欢迎") || $0 == "app store & privacy" }) {
            result.welcomeSeen = true
            result.knownLabels.insert("welcome")
        }
        if strings.contains(where: { ["continue", "get started", "继续", "开始使用"].contains($0) }) {
            result.knownLabels.insert("continue")
            if enabled && pressable && result.welcomeContinue == nil { result.welcomeContinue = item }
        }
        if strings.contains(where: { text in ["security", "two-factor", "authentication", "升级", "认证", "安全"].contains(where: { text.contains($0) }) }) {
            result.securityPrompt = true
        }
        if strings.contains(where: { $0.contains("upgrade") || $0.contains("升级") }) { result.upgradePrompt = true }
        if strings.contains(where: { text in ["verification code", "six-digit", "验证码"].contains(where: { text.contains($0) }) }) {
            result.verificationPrompt = true
        }
        if strings.contains(where: { text in ["incorrect", "could not sign", "cannot sign", "unable to sign", "could not be verified", "account is locked", "密码错误"].contains(where: { text.contains($0) }) }) {
            result.errorPrompt = true
        }
        if strings.contains(where: { ["sign out", "退出登录", "登出"].contains($0) }), let target = pressTarget(item) { result.signOut = target }
        if strings.contains(where: { ["don't upgrade", "don’t upgrade", "do not upgrade", "not now", "不升级", "稍后"].contains($0) }), let target = pressTarget(item) {
            result.declineUpgrade = target
        }
        if strings.contains(where: { ["other options", "其他选项"].contains($0) }), let target = pressTarget(item) {
            result.otherOptions = target
        }
        let errorPhrases: [String: [String]] = [
            "device_unverified": ["device could not be verified", "unable to verify your device", "device cannot be verified"],
            "invalid_credentials": ["password is incorrect", "incorrect password", "apple id or password is incorrect"],
            "cannot_connect": ["cannot connect", "can't connect", "can’t connect", "connection failed"],
            "unknown_error": ["unknown error", "unexpected error", "an error occurred"],
            "account_locked": ["account is locked", "account has been locked", "account is disabled"],
            "terms_required": ["agree to the terms", "review your account"],
        ]
        let codePattern = #"(?i)\b(?:unknown error(?: occurred)?|unexpected error(?: occurred)?|an error occurred|error(?: code)?)\s*(?:[.:]\s*)?\((-?[0-9]{1,6})\)"#
        if let regex = try? NSRegularExpression(pattern: codePattern) {
            for text in strings where text.utf8.count <= 2048 {
                let range = NSRange(text.startIndex..<text.endIndex, in: text)
                for match in regex.matches(in: text, range: range).prefix(8) {
                    if let digits = Range(match.range(at: 1), in: text), let code = Int(text[digits]) {
                        result.errorCodes.insert(code)
                    }
                }
            }
        }
        for (kind, phrases) in errorPhrases where strings.contains(where: { text in phrases.contains(where: { text.contains($0) }) }) {
            result.errors.insert(kind)
        }
        if strings.contains(where: { ["account", "账户", "帐户"].contains($0) }) {
            result.knownLabels.insert("account")
        }
        if strings.contains(where: { ["store", "商店"].contains($0) }) {
            result.knownLabels.insert("store")
            if enabled && pressable && role == kAXMenuBarItemRole { result.storeMenu = item }
        }
        for key in [kAXChildrenAttribute, "AXContents", "AXVisibleChildren", "AXChildrenInNavigationOrder"] {
            if let children = attribute(item, key) as? [AXUIElement] {
                let fresh = children.filter { queued.insert(CFHash($0)).inserted }
                let capacity = max(0, 512 - queue.count)
                queue.append(contentsOf: fresh.prefix(capacity))
                if fresh.count > capacity { result.limited = true }
            }
        }
    }
    if cursor < queue.count { result.limited = true }
    return result
}

func fill(_ field: AXUIElement, _ text: String) -> Bool {
    guard AXUIElementSetAttributeValue(field, kAXFocusedAttribute as CFString, kCFBooleanTrue) == .success else { return false }
    guard AXUIElementSetAttributeValue(field, kAXValueAttribute as CFString, text as CFString) == .success else { return false }
    // Commit the edit without invoking a default security/upgrade action.
    let source = CGEventSource(stateID: .hidSystemState)
    let down = CGEvent(keyboardEventSource: source, virtualKey: 48, keyDown: true)
    let up = CGEvent(keyboardEventSource: source, virtualKey: 48, keyDown: false)
    down?.post(tap: .cghidEventTap)
    up?.post(tap: .cghidEventTap)
    RunLoop.current.run(until: Date().addingTimeInterval(1))
    return true
}
func nativeLogin(_ element: AXUIElement, email: String, password: String) -> [String: Any] {
    var result: [String: Any] = ["status": "native_login_form_unavailable", "account_login_attempted": false,
                                 "password_submitted": false, "optional_upgrade_declined": false,
                                 "enrollment_created": false, "decryption_proven": false]
    var form = scan(element)
    guard !form.scanLimitedForAuthentication, form.emailFields == 1, let field = form.emailInput else { return result }
    guard !form.verificationPrompt && !form.upgradePrompt else { return result }
    guard fill(field, email) else { result["status"] = "native_email_input_failed"; return result }
    form = scan(element)
    var passwordSent = false
    if form.secureFields == 1, let secure = form.passwordInput {
        guard fill(secure, password) else { result["status"] = "native_password_input_failed"; return result }
        passwordSent = true
        form = scan(element)
    }
    guard let submit = form.signIn, AXUIElementPerformAction(submit, kAXPressAction as CFString) == .success else {
        result["status"] = "native_submit_unavailable"; return result
    }
    result["account_login_attempted"] = true
    result["password_submitted"] = passwordSent
    var upgradeActions = 0
    let end = Date().addingTimeInterval(75)
    while Date() < end {
        RunLoop.current.run(until: Date().addingTimeInterval(4))
        let live = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.AppStore").first
        let current = live.map { AXUIElementCreateApplication($0.processIdentifier) } ?? element
        _ = AXUIElementSetMessagingTimeout(current, 0.5)
        form = scan(current)
        result["last_ui"] = [
            "window_count": form.windows, "email_fields": form.emailFields, "secure_fields": form.secureFields,
            "sign_in_enabled": form.signIn != nil, "sign_out_enabled": form.signOut != nil,
            "security_prompt": form.securityPrompt, "upgrade_prompt": form.upgradePrompt,
            "verification_prompt": form.verificationPrompt, "scan_limited": form.limited,
            "error_kinds": form.errors.sorted(), "error_codes": Array(form.errorCodes.sorted().prefix(8)),
        ]
        if form.verificationPrompt { result["status"] = "native_verification_required"; return result }
        if form.errorPrompt || !form.errors.isEmpty { result["status"] = "native_login_rejected"; return result }
        if form.upgradePrompt && form.securityPrompt {
            if let decline = form.declineUpgrade, upgradeActions < 2 {
                guard AXUIElementPerformAction(decline, kAXPressAction as CFString) == .success else { break }
                result["optional_upgrade_declined"] = true
                upgradeActions += 1
                continue
            }
            if let other = form.otherOptions, upgradeActions == 0 {
                guard AXUIElementPerformAction(other, kAXPressAction as CFString) == .success else { break }
                upgradeActions += 1
                continue
            }
            result["status"] = "native_security_choice_unresolved"; return result
        }
        if !passwordSent && form.secureFields == 1, let secure = form.passwordInput {
            guard fill(secure, password) else { result["status"] = "native_password_input_failed"; return result }
            form = scan(element)
            guard let submit = form.signIn, AXUIElementPerformAction(submit, kAXPressAction as CFString) == .success else {
                result["status"] = "native_password_submit_unavailable"; return result
            }
            passwordSent = true
            result["password_submitted"] = true
            continue
        }
        if passwordSent && form.signOut != nil && form.emailFields == 0 && form.secureFields == 0 {
            result["status"] = "native_ui_indicates_signed_in"
            return result
        }
    }
    result["status"] = "native_login_unresolved"
    return result
}
extension UIResult {
    var scanLimitedForAuthentication: Bool { limited }
}

var report: [String: Any] = [
    "schema": "ipa-lab-enrollment-environment-v1", "status": "probe_complete",
    "account_credentials_supplied": false, "account_login_attempted": false,
    "enrollment_created": false, "decryption_proven": false,
    "state_before": statePresence(), "accessibility_trusted": AXIsProcessTrusted(),
]
#if arch(arm64)
report["architecture"] = "arm64"
#else
report["architecture"] = "other"
#endif
let console = SCDynamicStoreCopyConsoleUser(nil, nil, nil) as String?
report["console_user_session"] = console != nil && console != "loginwindow" && console != "_mbsetupuser"
let workspace = NSWorkspace.shared
guard let url = workspace.urlForApplication(withBundleIdentifier: "com.apple.AppStore") else {
    report["status"] = "app_store_not_found"
    emit(report)
    exit(0)
}
report["app_store_installed"] = true
var application: NSRunningApplication?
var launchComplete = false
let configuration = NSWorkspace.OpenConfiguration()
configuration.activates = true
workspace.openApplication(at: url, configuration: configuration) { app, error in
    application = app
    launchComplete = true
}
let launchDeadline = Date().addingTimeInterval(15)
while !launchComplete && Date() < launchDeadline {
    RunLoop.current.run(until: Date().addingTimeInterval(0.1))
}
report["app_store_launched"] = application != nil
if let application = application, AXIsProcessTrusted() {
    RunLoop.current.run(until: Date().addingTimeInterval(8))
    let element = AXUIElementCreateApplication(application.processIdentifier)
    _ = AXUIElementSetMessagingTimeout(element, 0.5)
    var before = scan(element)
    report["ui_before"] = before.report
    // First-launch privacy/recommendation pages can appear asynchronously.
    // This probe has no credentials; never advance a credential/security form.
    var introductionActions = 0
    for _ in 0..<3 {
        if before.signIn != nil || before.securityPrompt || before.emailFields > 0 || before.secureFields > 0 { break }
        guard before.words.contains("privacy") || before.words.contains("personalized") || before.welcomeSeen else { break }
        if let button = before.welcomeContinue {
            let action = AXUIElementPerformAction(button, kAXPressAction as CFString)
            if action != .success { break }
            introductionActions += 1
        }
        RunLoop.current.run(until: Date().addingTimeInterval(5))
        before = scan(element)
        report["ui_after_welcome"] = before.report
    }
    report["introduction_actions"] = introductionActions
    if before.signIn == nil, let menu = before.storeMenu {
        report["store_menu_press_result"] = Int(AXUIElementPerformAction(menu, kAXPressAction as CFString).rawValue)
        RunLoop.current.run(until: Date().addingTimeInterval(2))
        before = scan(element)
        report["ui_after_store_menu"] = before.report
    }
    if CommandLine.arguments.contains("--open-signin"), let button = before.signIn {
        let status = AXUIElementPerformAction(button, kAXPressAction as CFString)
        report["sign_in_press_result"] = Int(status.rawValue)
        RunLoop.current.run(until: Date().addingTimeInterval(3))
        report["ui_after"] = scan(element).report
    }
    if CommandLine.arguments.contains("--authenticate") {
        let env = ProcessInfo.processInfo.environment
        if let email = env["APPLE_ID"], !email.isEmpty, let password = env["APPLE_PASSWORD"], !password.isEmpty {
            report["account_credentials_supplied"] = true
            let auth = nativeLogin(element, email: email, password: password)
            report["authentication"] = auth
            report["account_login_attempted"] = auth["account_login_attempted"]
        } else {
            report["authentication"] = ["status": "missing_credentials"]
        }
    }
    _ = application.terminate()
} else if let application = application {
    _ = application.terminate()
}
report["state_after"] = statePresence()
emit(report)
