import Foundation
import CoreFoundation

enum LabCNPurchaseTrace {
    static func lines(_ value: [String:Any]) -> [String] {
        var lines=["IPA_CN_PURCHASE_ROOT:dictionary"]
        for (key,label) in [("failureType","FAILURE"),("status","STATUS")] {
            let value=value[key]
            if let number=value as? NSNumber, CFGetTypeID(number)==CFBooleanGetTypeID() { continue }
            let text=(value as? String) ?? (value as? NSNumber)?.stringValue
            if let text, text.range(of:"^-?[0-9]{1,7}$",options:.regularExpression) != nil,
               let code=Int(text), (-999999...999999).contains(code) {
                lines.append("IPA_CN_PURCHASE_"+label+":"+String(code))
            }
        }
        lines.append("IPA_CN_PURCHASE_MESSAGE:"+String(value["customerMessage"] is String))
        lines.append("IPA_CN_PURCHASE_ACTION:"+String(value["action"] is [String:Any]))
        lines.append("IPA_CN_PURCHASE_SUCCESS_TYPE:"+String((value["jingleDocType"] as? String)=="purchaseSuccess"))
        return lines
    }
}
