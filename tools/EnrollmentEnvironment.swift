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
    var knownLabels: Set<String> = []
    var roles: [String: Int] = [:]
    var report: [String: Any] {
        ["window_count": windows, "nodes_examined": nodes, "text_fields": textFields,
         "secure_fields": secureFields, "sign_in_control_found": signIn != nil,
         "scan_limited": limited, "sign_in_label_seen": signInSeen,
         "welcome_seen": welcomeSeen, "continue_control_found": welcomeContinue != nil,
         "known_labels": knownLabels.sorted(), "roles": roles]
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
        let strings = [kAXTitleAttribute, kAXDescriptionAttribute, kAXValueAttribute].compactMap {
            attribute(item, $0) as? String
        }.map {
            $0.trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: ".…")).lowercased()
        }
        var actions: CFArray?
        let pressable = AXUIElementCopyActionNames(item, &actions) == .success
            && ((actions as? [String]) ?? []).contains(kAXPressAction)
        let enabled = attribute(item, kAXEnabledAttribute) as? Bool == true
        if strings.contains(where: { ["sign in", "sign in to the app store", "登录", "登入"].contains($0) }) {
            result.signInSeen = true
            result.knownLabels.insert("sign_in")
            if enabled && pressable && result.signIn == nil { result.signIn = item }
        }
        if strings.contains(where: { $0.contains("welcome") || $0.contains("欢迎") || $0 == "app store & privacy" }) {
            result.welcomeSeen = true
            result.knownLabels.insert("welcome")
        }
        if strings.contains(where: { ["continue", "继续"].contains($0) }) {
            result.knownLabels.insert("continue")
            if enabled && pressable && result.welcomeContinue == nil { result.welcomeContinue = item }
        }
        if strings.contains(where: { ["account", "账户", "帐户"].contains($0) }) {
            result.knownLabels.insert("account")
        }
        if strings.contains(where: { ["store", "商店"].contains($0) }) {
            result.knownLabels.insert("store")
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
    if before.signIn == nil && before.welcomeSeen, let button = before.welcomeContinue {
        report["welcome_continue_result"] = Int(AXUIElementPerformAction(button, kAXPressAction as CFString).rawValue)
        RunLoop.current.run(until: Date().addingTimeInterval(5))
        before = scan(element)
        report["ui_after_welcome"] = before.report
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
