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
        func text(_ node:Any?,depth:Int=0) -> [String] {
            guard depth<=3 else { return [] }
            if let value=node as? String { return value.utf8.count<=8192 ? [value] : [] }
            if let value=node as? [String:Any] {
                return ["customerMessage","message","title","explanation","description","text","reason","dialog","buttons","buttonString","buttonLabel"].flatMap { text(value[$0],depth:depth+1) }
            }
            if let value=node as? [Any],value.count<=20 { return value.flatMap { text($0,depth:depth+1) } }
            return []
        }
        let message=text(value).joined(separator:" ").lowercased()
        let categories:[(String,[String])]=[
            ("license",["license","licence","entitle","not purchased","授权","授權","许可","許可","购买","購買"]),
            ("storefront",["storefront","country","region","in this store","地区","地區","国家","國家","standort","nicht verfügbar"]),
            ("network_location",["ip address","network location","outside your","所在网络","网络环境","網路環境","境外","海外","当前网络"]),
            ("unavailable",["not available","unavailable","cannot be downloaded","cannot be purchased","不可用","无法下载","無法下載","无法获取","未提供","暂不提供","不支持"]),
            ("terms",["terms","条款","條款","协议","協議"]),
            ("account_setup",["not yet been used","review your account","billing","payment information","尚未","付款","帐户信息","账户信息"]),
            ("authentication",["sign in","login","password","authentication","认证","驗證","密码","密碼","登录","登入"]),
            ("age",["age restriction","age verification","年龄","年齡"]),
            ("restriction",["disabled","restricted","not permitted","not allowed","限制","停用","禁用","不允许","不允許"]),
            ("temporary",["temporar","try again","later","稍后","稍後","重试","重試"])
        ]
        let matched=categories.filter { $0.1.contains(where: { message.contains($0) }) }.map { $0.0 }
        lines.append("IPA_CN_PURCHASE_MESSAGE_KINDS:"+matched.joined(separator:","))
        lines.append("IPA_CN_PURCHASE_HAS_FAILURE_TYPE:"+String(value["failureType"] != nil))
        lines.append("IPA_CN_PURCHASE_FAILURE_EMPTY:"+String((value["failureType"] as? String)?.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty == true))
        lines.append("IPA_CN_PURCHASE_MESSAGE_EMPTY:"+String((value["customerMessage"] as? String)?.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty == true))
        lines.append("IPA_CN_PURCHASE_MESSAGE:"+String(value["customerMessage"] is String))
        lines.append("IPA_CN_PURCHASE_ACTION:"+String(value["action"] is [String:Any]))
        lines.append("IPA_CN_PURCHASE_SUCCESS_TYPE:"+String((value["jingleDocType"] as? String)=="purchaseSuccess"))
        return lines
    }
    static func entitlement(_ value:[String:Any], app:Software, version:String) -> [String] {
        var lines=lines(value).map { $0.replacingOccurrences(of:"IPA_CN_PURCHASE_",with:"IPA_CN_ENTITLEMENT_") }
        let items=value["songList"] as? [[String:Any]]
        if let items, items.count<=10000 { lines.append("IPA_CN_ENTITLEMENT_ITEMS:"+String(items.count)) }
        let metadata=items?.first?["metadata"] as? [String:Any] ?? [:]
        lines.append("IPA_CN_ENTITLEMENT_APP_MATCH:"+String(metadata["itemId"].map { String(describing:$0) } == String(app.id)))
        lines.append("IPA_CN_ENTITLEMENT_VERSION_MATCH:"+String(metadata["softwareVersionExternalIdentifier"].map { String(describing:$0) } == version))
        lines.append("IPA_CN_ENTITLEMENT_BUNDLE_MATCH:"+String(metadata["softwareVersionBundleId"] as? String == app.bundleID))
        lines.append("IPA_CN_ENTITLEMENT_DIALOG:"+String(value["dialog"] != nil))
        return lines
    }

}
