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

 
// Historical selection uses authenticated Apple metadata, never a third-party index.
public enum LabVersionResolver {
    static let limit = 120
    static func valid(_ value: String, pattern: String) -> Bool {
        value.range(of: pattern, options: .regularExpression) != nil
    }
    static func isID(_ value: String) -> Bool {
        valid(value, pattern: "^[1-9][0-9]{5,19}$")
    }
    static func isDisplay(_ value: String) -> Bool {
        value.count <= 32 && valid(value, pattern: "^[0-9]{1,5}(\\.[0-9]{1,5}){0,4}$")
    }
    static func candidates(_ values: [String]) throws -> [String] {
        guard values.count <= 10000, values.allSatisfy({ isID($0) }) else {
            throw NSError(domain: "LabVersionInvalidList", code: 1)
        }
        return Array(Set(values)).sorted {
            $0.count == $1.count ? $0 > $1 : $0.count > $1.count
        }
    }
    static func older(_ value: String, than boundary: String) -> Bool {
        value.count == boundary.count ? value < boundary : value.count < boundary.count
    }
    static func catalogCandidates(_ values: [String], before: String) throws -> [String] {
        guard before.isEmpty || isID(before) else {
            throw NSError(domain: "LabVersionCursor", code: 1)
        }
        return try candidates(values).filter { before.isEmpty || older($0, than: before) }
    }
    public static func catalog(account: inout Account, app: Software, seed: String) async throws {
        let before = ProcessInfo.processInfo.environment["LAB_CATALOG_BEFORE"] ?? ""
        let identifiers = try candidates(try await VersionFinder.list(
            account: &account, bundleIdentifier: app.bundleID,
            entityType: .iPhone, externalVersionID: seed))
        let remaining = try catalogCandidates(identifiers, before: before)
        print("IPA_LAB_CATALOG_TOTAL:" + String(identifiers.count))
        let deadline = Date().addingTimeInterval(180)
        var failures = 0
        var examined = 0
        var cursor = before
        let pageLimit = ProcessInfo.processInfo.environment["LAB_CATALOG_PAGED"] == "1" ? 10 : 60
        for identifier in remaining.prefix(pageLimit) {
            if Date() >= deadline || failures >= 3 { break }
            examined += 1
            cursor = identifier
            do {
                let metadata = try await VersionLookup.getVersionMetadata(
                    account: &account, app: app, versionID: identifier)
                guard isDisplay(metadata.displayVersion) else {
                    throw NSError(domain: "LabVersionMetadata", code: 1)
                }
                let date = String(ISO8601DateFormatter().string(from: metadata.releaseDate).prefix(10))
                print("IPA_LAB_CATALOG_ITEM:" + identifier + ":" + metadata.displayVersion + ":" + date)
                failures = 0
            } catch {
                failures += 1
            }
        }
        // Advance past attempted IDs, including inaccessible versions; never loop on a failed ID.
        let next = examined < remaining.count && examined > 0 ? cursor : ""
        print("IPA_LAB_CATALOG_NEXT:" + (next.isEmpty ? "end" : next))
    }

    public static func resolve(account: inout Account, app: Software, seed: String,
                               requested: String) async throws -> String {
        guard isID(requested) || isDisplay(requested) else {
            print("IPA_LAB_VERSION_ERROR:invalid_version")
            throw NSError(domain: "LabVersionInput", code: 1)
        }
        let deadline = Date().addingTimeInterval(180)
        do {
            let identifiers: [String]
            if isID(requested) {
                identifiers = [requested]
            } else {
                identifiers = try candidates(try await VersionFinder.list(
                    account: &account, bundleIdentifier: app.bundleID,
                    entityType: .iPhone, externalVersionID: seed))
            }
            for identifier in identifiers.prefix(limit) {
                guard Date() < deadline else {
                    print("IPA_LAB_VERSION_ERROR:version_search_limit")
                    throw NSError(domain: "LabVersionReported", code: 1)
                }
                let metadata = try await VersionLookup.getVersionMetadata(
                    account: &account, app: app, versionID: identifier)
                guard isDisplay(metadata.displayVersion) else {
                    throw NSError(domain: "LabVersionMetadata", code: 1)
                }
                if isID(requested) || metadata.displayVersion == requested {
                    print("IPA_LAB_VERSION:" + identifier + ":" + metadata.displayVersion)
                    return identifier
                }
            }
            print("IPA_LAB_VERSION_ERROR:" + (identifiers.count > limit ? "version_search_limit" : "version_not_found"))
            throw NSError(domain: "LabVersionReported", code: 1)
        } catch {
            if (error as NSError).domain != "LabVersionReported" {
                print("IPA_LAB_VERSION_ERROR:version_lookup_unavailable")
            }
            throw error
        }
    }
}
