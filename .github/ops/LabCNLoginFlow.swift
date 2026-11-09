import Foundation

public enum LabCNLoginError: Error { case invalidVerificationCode, inputClosed }

public enum LabCNLoginFlow {
    // Keep the supplied Authenticator actor alive across both requests.
    // Ambiguous BadLogin is NOT asserted to prove a verification challenge.
    // Only this owner-selected CN flow offers one explicit code submission.
    public static func authenticate<T: Sendable>(
        perform: @Sendable (String) async throws -> T,
        nextCode: @Sendable () throws -> String
    ) async throws -> T {
        do { return try await perform("") }
        catch {
            let allowed: Bool
            if case AuthenticationError.verificationCodeRequired = error { allowed = true }
            else { allowed = String(describing: error).contains("apple_auth_ambiguous_bad_login") }
            guard allowed else { throw error }
        }
        let code = try nextCode().trimmingCharacters(in: .whitespacesAndNewlines)
        guard code.utf8.count == 6, code.utf8.allSatisfy({ (48 ... 57).contains($0) })
        else { throw LabCNLoginError.invalidVerificationCode }
        return try await perform(code)
    }
}
