// Compile beside the pinned upstream DeviceIdentifier.swift; never print from a public CI command.
import Foundation
struct IdentityError: Error {}
func ensure(_ value: Bool, _ message: String) throws {
    if !value { throw IdentityError() }
}
func ensureFailed(_ message: String) throws { throw IdentityError() }
@main struct LabDeviceIdentity {
    static func main() {
        guard ProcessInfo.processInfo.environment["GITHUB_ACTIONS"] == "true" else { exit(2) }
        do {
            let value = try DeviceIdentifier.system()
            guard value.range(of: "^[A-F0-9]{12}$", options: .regularExpression) != nil else { exit(3) }
            FileHandle.standardOutput.write(Data(value.utf8))
        } catch { exit(4) }
    }
}
