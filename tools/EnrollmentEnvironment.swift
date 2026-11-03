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
    var report: [String: Any] {
        ["window_count": windows, "nodes_examined": nodes, "text_fields": textFields,
         "secure_fields": secureFields, "sign_in_control_found": signIn != nil,
         "scan_limited": limited]
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
    let deadline = Date().addingTimeInterval(12)
    var cursor = 0
    while cursor < queue.count && cursor < 160 && Date() < deadline {
        let item = queue[cursor]
        cursor += 1
        result.nodes += 1
        _ = AXUIElementSetMessagingTimeout(item, 0.5)
        let role = attribute(item, kAXRoleAttribute) as? String ?? ""
        let subrole = attribute(item, kAXSubroleAttribute) as? String ?? ""
        if role == kAXTextFieldRole { result.textFields += 1 }
        if subrole == kAXSecureTextFieldSubrole { result.secureFields += 1 }
        if role == kAXButtonRole || role == kAXMenuItemRole {
            let title = (attribute(item, kAXTitleAttribute) as? String ?? "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: ".…"))
                .lowercased()
            if ["sign in", "登录", "登入"].contains(title), result.signIn == nil,
               attribute(item, kAXEnabledAttribute) as? Bool == true {
                result.signIn = item
            }
        }
        if let children = attribute(item, kAXChildrenAttribute) as? [AXUIElement] {
            let capacity = max(0, 160 - queue.count)
            queue.append(contentsOf: children.prefix(capacity))
            if children.count > capacity { result.limited = true }
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
    RunLoop.current.run(until: Date().addingTimeInterval(3))
    let element = AXUIElementCreateApplication(application.processIdentifier)
    _ = AXUIElementSetMessagingTimeout(element, 0.5)
    let before = scan(element)
    report["ui_before"] = before.report
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
