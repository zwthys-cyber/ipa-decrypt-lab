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
            fflush(stdout)
            guard let value = readLine() else { throw LabCNLoginError.inputClosed }
            return value
        })
        Configuration.saveLoginAccount(account, for: email)
        print("IPA_CN_AUTH:authenticated")
    }
}
