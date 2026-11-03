import AsyncHTTPClient
import Foundation

// Account-authorized ent/download request. No decryption or entitlement bypass.
enum LabEntDownload {
    static let endpointPath = "/WebObjects/DownloadDispatch.woa/wa/ent/download"

    static func approved(_ url: URL) -> Bool {
        url.scheme == "https" && url.host == "downloaddispatch.itunes.apple.com"
            && url.path == endpointPath && url.user == nil && url.password == nil
            && url.query == nil && url.fragment == nil && (url.port == nil || url.port == 443)
    }

    static func payload(guid: String, dsid: String, appID: Int64, version: String, blob: String) throws -> Data {
        guard guid.count == 12, guid.allSatisfy({ $0.isHexDigit }),
              let accountID = UInt64(dsid), accountID > 0,
              appID > 0, !version.isEmpty,
              let decoded = Data(base64Encoded: blob), !decoded.isEmpty, decoded.count <= 1024 * 1024
        else { throw NSError(domain: "LabEntInput", code: 1) }
        let chars = Array(guid)
        let bytes = stride(from: 0, to: 12, by: 2).compactMap { UInt8(String(chars[$0...($0+1)]), radix: 16) }
        guard bytes.count == 6 else { throw NSError(domain: "LabEntInput", code: 2) }
        let serial = Data([0x54, 0xc8, 0xb0, 0xa9, 0x88] + Array(bytes[2...]))
        return try PropertyListSerialization.data(fromPropertyList: [
            "creditDisplay": "", "guid": guid, "kbsync": blob,
            "salableAdamId": String(appID), "serialNumber": serial.base64EncodedString(),
            "externalVersionId": version
        ], format: .xml, options: 0)
    }

    static func fetch(client: HTTPClient, account: inout Account, app: Software,
                      guid: String, version: String, helper: String) async throws -> [String: Any] {
        print("IPA_LAB_STAGE:resolve_ent_endpoint")
        let bag = try await Bag.fetchBag(redirectConfiguration: .disallow)
        guard let endpoint = bag.entDownloadEndpoint, approved(endpoint) else {
            throw NSError(domain: "LabEntEndpointMissing", code: 1)
        }
        print("IPA_LAB_STAGE:generate_kbsync")
        let process = Process()
        process.executableURL = URL(fileURLWithPath: helper)
        let input = Pipe(), output = Pipe()
        process.standardInput = input
        process.standardOutput = output
        process.standardError = FileHandle.nullDevice
        // Only the two required fields reach the helper; no credentials in argv or logs.
        process.environment = ["PATH": "/usr/bin:/bin", "HOME": NSHomeDirectory(), "LAB_KBSYNC_CHILD": "1"]
        try process.run()
        let requestData = try JSONSerialization.data(withJSONObject: ["guid": guid, "dsid": account.directoryServicesIdentifier])
        try input.fileHandleForWriting.write(contentsOf: requestData)
        try input.fileHandleForWriting.close()
        let result = output.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0, result.count <= 2 * 1024 * 1024,
              let blob = String(data: result, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
        else { throw NSError(domain: "LabKBSyncFailed", code: 1) }
        let data = try payload(guid: guid, dsid: account.directoryServicesIdentifier, appID: app.id,
                               version: version, blob: blob)
        var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "guid", value: guid)]
        var headers = [
            ("Content-Type", "application/x-www-form-urlencoded; charset=utf-8"),
            ("User-Agent", "Configurator/2.18 (Macintosh; OS X 15.3.2; 24D81) AppleWebKit/0620.2.4.11.6"),
            ("iCloud-DSID", account.directoryServicesIdentifier),
            ("X-Dsid", account.directoryServicesIdentifier),
            ("X-Apple-Store-Front", account.labStoreFront ?? "\(account.store)-1"),
            ("X-Token", account.passwordToken)
        ]
        headers += account.cookie.buildCookieHeader(endpoint)
        let request = try HTTPClient.Request(url: components.url!, method: .POST,
                                             headers: .init(headers), body: .data(data))
        print("IPA_LAB_STAGE:request_ent_product")
        // The caller's client disallows redirects: never forward X-Token elsewhere.
        let response = try await client.execute(request: request).get()
        print("IPA_LAB_HTTP:" + String(response.status.code))
        guard response.status == .ok else {
            throw StoreDownloadHTTPError(statusCode: response.status.code, emptyBody: (response.body?.readableBytes ?? 0) == 0)
        }
        guard var body = response.body, body.readableBytes <= 2 * 1024 * 1024,
              let bytes = body.readData(length: body.readableBytes),
              let dict = try PropertyListSerialization.propertyList(from: bytes, options: [], format: nil) as? [String: Any]
        else { throw NSError(domain: "LabEntResponse", code: 1) }
        account.cookie.mergeCookies(response.cookies)
        print("IPA_LAB_STAGE:validate_ent_product")
        return try StoreDownloadEndpoint.validateRecoveryResponse(dict, app: app, version: version)
    }
}
