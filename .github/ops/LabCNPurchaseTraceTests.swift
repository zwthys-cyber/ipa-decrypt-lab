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
    func testMessageClassificationNeverPublishesMessage() {
        let lines=LabCNPurchaseTrace.lines(["customerMessage":"License required in this storefront PRIVATE_ACCOUNT"])
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_MESSAGE_KINDS:license,storefront"))
        XCTAssertFalse(lines.joined().contains("PRIVATE"))
    }
    func testDialogClassificationAndEmptyFailureDoNotExposeText() {
        let lines=LabCNPurchaseTrace.lines(["failureType":"","customerMessage":"","dialog":["title":"This app is not available in your country or region PRIVATE_ACCOUNT","message":"IP address outside your network location PRIVATE_TOKEN"]])
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_FAILURE_EMPTY:true"))
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_MESSAGE_EMPTY:true"))
        XCTAssertTrue(lines.contains("IPA_CN_PURCHASE_MESSAGE_KINDS:storefront,network_location,unavailable"))
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
