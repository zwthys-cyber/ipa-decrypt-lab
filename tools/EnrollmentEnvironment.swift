// Account-free capability probe; run only on a disposable GitHub-hosted Mac.
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
        if subrole == kAXSecureTextFieldSubrole { result.secureFields += 1 }
        let strings = [kAXTitleAttribute, kAXDescriptionAttribute, kAXValueAttribute, "AXHelp", "AXPlaceholderValue"].compactMap {
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
        }) { result.emailFields += 1 }
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
    _ = application.terminate()
} else if let application = application {
    _ = application.terminate()
}
report["state_after"] = statePresence()
emit(report)
