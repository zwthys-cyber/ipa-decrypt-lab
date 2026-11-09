@testable import ApplePackage
import Foundation
import XCTest

final class LabCNSummaryTests: XCTestCase {
    func testCountIsBoundedAndRejectsAuthenticationErrors() throws {
        for count in [0, 1, 5] {
            let data = try JSONSerialization.data(withJSONObject: ["data": ["authorizations": ["authorizedComputers": count]]])
            XCTAssertEqual(try LabCNSummary.count(data), count)
        }
        for count: Any in [true, -1, 6, "2", 2.5, NSNull()] {
            let data = try JSONSerialization.data(withJSONObject: ["data": ["authorizations": ["authorizedComputers": count]]])
            XCTAssertThrowsError(try LabCNSummary.count(data))
        }
        let data = Data(#"{"errors":[{"message":"PRIVATE"}],"data":{"authorizations":{"authorizedComputers":0}}}"#.utf8)
        XCTAssertThrowsError(try LabCNSummary.count(data))
    }
    func testOnlyExactAppleSummaryTargetsReceiveProofs() throws {
        XCTAssertTrue(LabCNSummary.approved(try LabCNSummary.endpoint(pod: nil)))
        XCTAssertTrue(LabCNSummary.approved(try LabCNSummary.endpoint(pod: "71")))
        for pod in ["0", "71.evil.invalid", "71:443", "71/..", "0001"] { XCTAssertThrowsError(try LabCNSummary.endpoint(pod: pod)) }
        for url in ["http://buy.itunes.apple.com/account/v1/summary/graphql", "https://user:password@buy.itunes.apple.com/account/v1/summary/graphql", "https://buy.itunes.apple.com.evil.invalid/account/v1/summary/graphql", "https://buy.itunes.apple.com:8443/account/v1/summary/graphql", "https://buy.itunes.apple.com/account/v1/summary/graphql?private=1", "https://buy.itunes.apple.com/account/v1/summary/graphql#x", "https://buy.itunes.apple.com/account/v1/summary%2fgraphql"] {
            XCTAssertFalse(LabCNSummary.approved(URL(string: url)!))
        }
    }
    func testBodyIsOnlyTheReadOnlyCountQuery() throws {
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: LabCNSummary.body) as? [String: String])
        XCTAssertEqual(json, ["query": "query requestAccountSummary { authorizations { authorizedComputers } }"])
    }
}
