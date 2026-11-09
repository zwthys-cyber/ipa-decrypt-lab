@testable import ApplePackage
import Foundation
import XCTest

private enum FixtureError: Error { case unrelated, rejected }
private struct AmbiguousLogin: Error, CustomStringConvertible {
    var description: String { "apple_auth_ambiguous_bad_login" }
}
private actor LoginFixture {
    var calls: [String] = []
    let reject: Bool
    init(reject: Bool = false) { self.reject = reject }
    func authenticate(_ code: String) throws -> String {
        calls.append(code)
        if code.isEmpty { throw AmbiguousLogin() }
        if reject { throw FixtureError.rejected }
        return "synthetic-account"
    }
}
final class LabCNLoginFlowTests: XCTestCase {
    func testSameSessionReceivesEmptyThenLiveCode() async throws {
        let client = LoginFixture()
        let result = try await LabCNLoginFlow.authenticate(perform: { try await client.authenticate($0) }, nextCode: { "123456" })
        XCTAssertEqual(result, "synthetic-account")
        let calls = await client.calls
        XCTAssertEqual(calls, ["", "123456"])
    }
    func testImmediateSuccessDoesNotAskForCode() async throws {
        let result = try await LabCNLoginFlow.authenticate(perform: { _ in "synthetic-account" }, nextCode: {
            XCTFail("unneeded code prompt"); return ""
        })
        XCTAssertEqual(result, "synthetic-account")
    }
    func testUnrelatedFailureStopsWithoutPrompt() async {
        do {
            let _: String = try await LabCNLoginFlow.authenticate(perform: { _ in throw FixtureError.unrelated }, nextCode: {
                XCTFail("unrelated errors must not solicit verification"); return "123456"
            })
            XCTFail("accepted failure")
        } catch {}
    }
    func testInvalidCodeDoesNotReachSecondRequest() async {
        let client = LoginFixture()
        do {
            let _: String = try await LabCNLoginFlow.authenticate(perform: { try await client.authenticate($0) }, nextCode: { "１２３４５６" })
            XCTFail("accepted non-ASCII code")
        } catch {}
        let calls = await client.calls
        XCTAssertEqual(calls, [""])
    }
    func testCodeRejectionDoesNotRetry() async {
        let client = LoginFixture(reject: true)
        do {
            let _: String = try await LabCNLoginFlow.authenticate(perform: { try await client.authenticate($0) }, nextCode: { "123456" })
            XCTFail("accepted code rejection")
        } catch {}
        let calls = await client.calls
        XCTAssertEqual(calls, ["", "123456"])
    }
}
