import ApplePackage
import ArgumentParser
import Foundation

struct ChinaLogin: AsyncParsableCommand, Sendable {
    static let configuration = CommandConfiguration(commandName: "login-cn", abstract: "Isolated CN login with one live verification response")
    @OptionGroup var globalOptions: GlobalOptions
    @Argument var email: String
    func run() async throws {
        guard let password = ProcessInfo.processInfo.environment["APPLEPACKAGE_PASSWORD"], !password.isEmpty else {
            throw ValidationError("Missing account password environment.")
        }
        globalOptions.apply()
        let session = try await Authenticator()
        let address = email
        let account = try await LabCNLoginFlow.authenticate(perform: { code in
            try await session.authenticate(email: address, password: password, code: code)
        }, nextCode: {
            print("IPA_CN_AUTH:verification_pending")
            fflush(nil)
            guard let value = readLine() else { throw LabCNLoginError.inputClosed }
            return value
        })
        Configuration.saveLoginAccount(account, for: email)
        print("IPA_CN_AUTH:authenticated")
    }
}

// Refresh only the saved CN account, carrying its authenticated cookies. No code prompt or retry.
struct ChinaResume: AsyncParsableCommand, Sendable {
    static let configuration = CommandConfiguration(commandName: "resume-cn", abstract: "Refresh the saved CN account once with its cookies")
    @OptionGroup var globalOptions: GlobalOptions
    @Argument var email: String
    func run() async throws {
        globalOptions.apply()
        let address = email
        try await Configuration.withAccount(email: address) { account in
            guard account.store == "143465", account.email.lowercased() == address.lowercased() else {
                throw ValidationError("CN session binding failed")
            }
            let session = try await Authenticator(cookies: account.cookie)
            let updated = try await session.authenticate(email: address, password: account.password)
            guard updated.store == "143465", updated.email.lowercased() == address.lowercased() else {
                throw ValidationError("CN refreshed session binding failed")
            }
            account = updated
        }
        print("IPA_CN_RESUME:authenticated")
    }
}
