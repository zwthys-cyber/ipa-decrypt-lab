import AsyncHTTPClient
import CoreFoundation
import Foundation

public enum LabCNSummary {
    static let userAgent = "Configurator/2.17 (Macintosh; OS X 15.2; 24C5089c) AppleWebKit/0620.1.16.11.6"
    static let path = "/account/v1/summary/graphql"
    static let body = Data(#"{"query":"query requestAccountSummary { authorizations { authorizedComputers } }"}"#.utf8)
    static func endpoint(pod: String?) throws -> URL {
        let host: String
        if let pod {
            guard pod.range(of: "^[1-9][0-9]{0,2}$", options: .regularExpression) != nil else { throw NSError(domain: "CNSummaryInput", code: 1) }
            host = "p" + pod + "-buy.itunes.apple.com"
        } else { host = "buy.itunes.apple.com" }
        return URL(string: "https://" + host + path)!
    }
    static func approved(_ url: URL) -> Bool {
        guard let c = URLComponents(url: url, resolvingAgainstBaseURL: false), let host = c.host,
              c.scheme == "https", c.user == nil, c.password == nil, c.port == nil || c.port == 443,
              c.query == nil, c.fragment == nil, c.percentEncodedPath == path else { return false }
        return host == "buy.itunes.apple.com" || host.range(of: "^p[1-9][0-9]{0,2}-buy[.]itunes[.]apple[.]com$", options: .regularExpression) != nil
    }
    static func count(_ data: Data) throws -> Int {
        guard data.count <= 1024 * 1024,
              let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              root["failureType"] == nil,
              root["errors"] == nil || (root["errors"] as? [Any])?.isEmpty == true,
              let payload = root["data"] as? [String: Any], let auth = payload["authorizations"] as? [String: Any],
              let value = auth["authorizedComputers"] as? NSNumber,
              CFGetTypeID(value) != CFBooleanGetTypeID(),
              value.doubleValue == Double(value.intValue), (0...5).contains(value.intValue)
        else { throw NSError(domain: "CNSummaryResponse", code: 1) }
        return value.intValue
    }
    public static func query(account: Account) async throws -> Int {
        guard account.store == "143465" else { throw NSError(domain: "CNSummaryInput", code: 2) }
        let url = try endpoint(pod: account.pod)
        var headers = [("Content-Type", "application/json; charset=UTF-8"), ("Accept", "application/json"),
            ("Accept-Encoding", "identity"), ("User-Agent", userAgent),
            ("X-Dsid", account.directoryServicesIdentifier), ("iCloud-DSID", account.directoryServicesIdentifier),
            ("X-Token", account.passwordToken), ("X-Apple-Store-Front", account.labStoreFront ?? "143465-1")]
        headers += account.cookie.buildCookieHeader(url)
        headers += try StoreAMD.cnSummaryHeaders(for: url)
        let client = Configuration.makeHTTPClient(redirectConfiguration: .disallow)
        defer { _ = client.shutdown() }
        let request = try HTTPClient.Request(url: url, method: .POST, headers: .init(headers), body: .data(body))
        let response = try await client.execute(request: request).get()
        print("IPA_CN_SUMMARY:HTTP:" + String(response.status.code))
        guard response.status == .ok, var buffer = response.body, buffer.readableBytes <= 1024 * 1024,
              let data = buffer.readData(length: buffer.readableBytes) else { throw NSError(domain: "CNSummaryHTTP", code: 1) }
        return try count(data)
    }
}
