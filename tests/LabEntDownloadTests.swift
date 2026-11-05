@testable import ApplePackage
import Foundation
import XCTest

final class LabEntDownloadTests: XCTestCase {
    func testCatalogCursorIsExclusiveAndStableWhenNewIDsAppear() throws {
        XCTAssertEqual(try LabVersionResolver.catalogCandidates(["842461702","842461701","842461700"], before: "842461701"), ["842461700"])
        XCTAssertEqual(try LabVersionResolver.catalogCandidates(["999999","1000000"], before: "1000000"), ["999999"])
        XCTAssertThrowsError(try LabVersionResolver.catalogCandidates(["842461700"], before: "../bad"))
    }
    func testHistoricalSelectionBoundsAndOrdering() throws {
        XCTAssertEqual(try LabVersionResolver.candidates(["842461647","842461648","842461647"]),
                       ["842461648","842461647"])
        XCTAssertThrowsError(try LabVersionResolver.candidates(["../bad"]))
        XCTAssertFalse(LabVersionResolver.isDisplay("9.3.55 --output x"))
        XCTAssertTrue(LabVersionResolver.isDisplay("9.3.55"))
        XCTAssertTrue(LabVersionResolver.isID("842461647"))
        XCTAssertFalse(LabVersionResolver.isID("9.3.55"))
    }
    func testEndpointRejectsTokenExfiltrationAndRedirectTargets() {
        for value in [
            "http://downloaddispatch.itunes.apple.com" + LabEntDownload.endpointPath,
            "https://example.com" + LabEntDownload.endpointPath,
            "https://downloaddispatch.itunes.apple.com.evil.test" + LabEntDownload.endpointPath,
            "https://user@downloaddispatch.itunes.apple.com" + LabEntDownload.endpointPath,
            "https://downloaddispatch.itunes.apple.com" + LabEntDownload.endpointPath + "?redirect=1"
        ] { XCTAssertFalse(LabEntDownload.approved(URL(string: value)!)) }
        XCTAssertTrue(LabEntDownload.approved(URL(string: "https://downloaddispatch.itunes.apple.com" + LabEntDownload.endpointPath)!))
    }
    func testPayloadPinsAppVersionAndMachine() throws {
        let data = try LabEntDownload.payload(guid: "001122334455", dsid: "123", appID: 12345, version: "987", blob: "AQID")
        let dict = try XCTUnwrap(PropertyListSerialization.propertyList(from: data, options: [], format: nil) as? [String: String])
        XCTAssertEqual(dict["salableAdamId"], "12345")
        XCTAssertEqual(dict["externalVersionId"], "987")
        XCTAssertEqual(dict["kbsync"], "AQID")
        XCTAssertEqual(Data(base64Encoded: dict["serialNumber"]!), Data([0x54,0xc8,0xb0,0xa9,0x88,0x22,0x33,0x44,0x55]))
        XCTAssertThrowsError(try LabEntDownload.payload(guid: "invalid", dsid: "123", appID: 12345, version: "987", blob: "AQID"))
        XCTAssertThrowsError(try LabEntDownload.payload(guid: "001122334455", dsid: "0", appID: 12345, version: "987", blob: "AQID"))
    }
}
