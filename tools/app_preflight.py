"""Credential-free, bounded public App Store eligibility check shared by bot and worker."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from capacity import MAX_IPA_BYTES

MESSAGES = {
    "app_not_found_in_us": "美区未查询到此应用，可能仅在其他地区上架或已下架。当前仅支持美区。",
    "paid_app_not_supported": "此应用在美区不是免费应用，当前仅支持免费应用。",
    "source_too_large": "商店标注的应用大小超过 2000 MB 上限，当前不支持。",
    "metadata_network_failed": "暂时无法查询 App Store，请稍后再试；网络异常不代表应用下架。",
    "metadata_invalid_response": "App Store 返回的信息不完整，暂时无法确认能否下载，请稍后再试。",
    "invalid_app_id": "应用 ID 格式不正确。",
}
STEP_NAMES = {
    "app_not_found_in_us": "App unavailable in US storefront",
    "paid_app_not_supported": "Paid app unsupported",
    "source_too_large": "IPA exceeds 2000 MB capacity",
    "metadata_network_failed": "App Store lookup unavailable",
    "metadata_invalid_response": "App Store metadata invalid",
    "invalid_app_id": "Invalid App Store ID",
}
MAX_RESPONSE = 2 * 1024 * 1024

class PreflightError(ValueError):
    def __init__(self, status):
        self.status = status if status in MESSAGES else "metadata_invalid_response"
        super().__init__(self.status)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def check_app(identifier, historical=False):
    if not isinstance(identifier,str) or not re.fullmatch(r"[1-9][0-9]{4,19}",identifier):
        raise PreflightError("invalid_app_id")
    url="https://itunes.apple.com/lookup?"+urllib.parse.urlencode(
        {"id":identifier,"country":"us","entity":"software"})
    try:
        opener=urllib.request.build_opener(NoRedirect())
        with opener.open(url,timeout=8) as response:
            raw=response.read(MAX_RESPONSE+1)
    except (OSError,urllib.error.URLError):
        raise PreflightError("metadata_network_failed") from None
    try:
        if len(raw)>MAX_RESPONSE:
            raise ValueError()
        payload=json.loads(raw)
        if not isinstance(payload,dict) or not isinstance(payload.get("results"),list):
            raise ValueError()
        results=payload["results"]
        if payload.get("resultCount")==0 and results==[]:
            raise PreflightError("app_not_found_in_us")
        if len(results)!=1 or not isinstance(results[0],dict):
            raise ValueError()
        info=results[0]
        if str(info.get("trackId"))!=identifier or not isinstance(info.get("bundleId"),str) or not info["bundleId"]:
            raise ValueError()
        price=info.get("price")
        if type(price) not in (int,float) or price<0:
            raise ValueError()
        if price!=0:
            raise PreflightError("paid_app_not_supported")
        size=info.get("fileSizeBytes")
        if size is not None:
            if isinstance(size,str) and size.isdecimal() and len(size)<=20:
                size=int(size)
            if type(size) is not int or size<=0:
                raise ValueError()
            if size>MAX_IPA_BYTES and not historical:
                raise PreflightError("source_too_large")
        return info
    except PreflightError:
        raise
    except (ValueError,TypeError,KeyError):
        raise PreflightError("metadata_invalid_response") from None

def main():
    status="eligible"
    try:
        check_app(os.environ.get("DELIVERY_APP_ID",""), historical=bool(os.environ.get("DELIVERY_VERSION","")))
    except PreflightError as exc:
        status=exc.status
    output=os.environ.get("GITHUB_OUTPUT")
    if output and os.environ.get("GITHUB_ACTIONS")=="true":
        with open(output,"a") as stream:
            stream.write("eligibility="+status+"\n")
    print(json.dumps({"schema":"ipa-preflight-v1","status":status}),flush=True)
    return 0 if status=="eligible" else 2

if __name__=="__main__":
    raise SystemExit(main())
