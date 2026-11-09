@testable import ApplePackage
import XCTest
final class LabCNPurchaseTraceTests:XCTestCase {
    func testNumericTypesAndPrivacy() {
        let lines=LabCNPurchaseTrace.lines(["failureType":"-5000","status":NSNumber(value:0),"customerMessage":"PRIVATE_EMAIL_AND_TOKEN","action":["url":"PRIVATE_URL"],"jingleDocType":"purchaseSuccess"])
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_FAILURE:-5000"))
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_STATUS:0"))
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_SUCCESS_TYPE:true"))
        XCTAssertFalse(lines.joined().contains("PRIVATE"))
    }
    func testMalformedAndUnboundedCodesAreNotPublished() {
        let invalid:[Any]=["PRIVATE",true,99999999,"4\nSECRET",["token":"PRIVATE"]]
        for value in invalid {
            let lines=LabCNPurchaseTrace.lines(["failureType":value])
            XCTAssertFalse(lines.contains(where:{$0.hasPrefix("IPA_CN_PURCHASE_FAILURE:")}))
        }
    }
}
