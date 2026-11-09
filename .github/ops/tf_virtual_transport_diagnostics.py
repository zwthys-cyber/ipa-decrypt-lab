"""Closed numeric transport observations; never forward raw stderr."""
import json

KEYS={"phase","fresh_connection","curl_exit","http_status","connect_ms","tls_ms",
      "first_byte_ms","total_ms","upload_complete","received_body","new_connections","http_version"}

def observations(raw):
    result=[]
    for line in raw.splitlines():
        if not line.startswith(b"TF_NET:") or len(line)>2048:continue
        try:value=json.loads(line[7:])
        except (ValueError,UnicodeError):continue
        if type(value) is not dict or set(value)!=KEYS:continue
        if type(value["phase"]) is not str or value["phase"] not in {"lookup","srp_init","srp_complete","gsa_service"}:continue
        if any(type(value[k]) is not bool for k in ("fresh_connection","upload_complete","received_body")):continue
        bounds={"curl_exit":100,"http_status":599,"connect_ms":240000,"tls_ms":240000,
                "first_byte_ms":240000,"total_ms":240000,"new_connections":16,"http_version":32}
        if any(type(value[k]) is not int or not 0<=value[k]<=limit for k,limit in bounds.items()):continue
        result.append(value)
        if len(result)==16:break
    return result

def verification_observations(raw):
    result=[]
    keys={"envelope","object","ec_present","ec_integer","ec_in_range","ec_code"}
    for line in raw.splitlines():
        if not line.startswith(b"TF_VERIFY:") or len(line)>1024:continue
        try:value=json.loads(line[10:])
        except (ValueError,UnicodeError):continue
        if type(value) is not dict or set(value)!=keys:continue
        if type(value["envelope"]) is not str or value["envelope"] not in {"response","status","top"}:continue
        if any(type(value[k]) is not bool for k in ("object","ec_present","ec_integer","ec_in_range")):continue
        if type(value["ec_code"]) is not int or not -99999999<=value["ec_code"]<=99999999:continue
        result.append(value)
        if len(result)==4:break
    return result

def session_observations(raw):
    result=[]
    keys={"parsed","id_matches","pet_matches","expiry_kind","remaining_seconds",
          "has_root_key","has_root_challenge","has_idms_token"}
    for line in raw.splitlines():
        if not line.startswith(b"TF_SESSION:") or len(line)>1024:continue
        try:value=json.loads(line[11:])
        except (ValueError,UnicodeError):continue
        if type(value) is not dict or set(value)!=keys:continue
        if any(type(value[k]) is not bool for k in ("parsed","id_matches","pet_matches",
            "has_root_key","has_root_challenge","has_idms_token")):continue
        if type(value["expiry_kind"]) is not str or value["expiry_kind"] not in {"absent","integer","floating","string","other"}:continue
        if type(value["remaining_seconds"]) is not int or not -86400<=value["remaining_seconds"]<=86400:continue
        result.append(value)
        if len(result)==4:break
    return result

def store_observations(raw):
    result=[]
    keys={"body_bytes","format","content_type","content_encoding","parsed","object","status_kind",
        "status_zero","status_code","status_in_range","person_id_present","password_token_present",
        "failure_present","error_code_present","message_present","dialog_present","parse_failure"}
    flags={"parsed","object","status_zero","status_in_range","person_id_present","password_token_present",
        "failure_present","error_code_present","message_present","dialog_present"}
    enums={"format":{"empty","other","gzip","json","binary_plist","xml","html"},
        "content_type":{"missing","other","html","plist","json","binary"},
        "content_encoding":{"missing","other","gzip","deflate","br"},
        "status_kind":{"absent","integer","string","boolean","floating","other"},
        "parse_failure":{"none","empty","oversized","json_error","invalid_plist","unsupported_plist","other"}}
    for line in raw.splitlines():
        if not line.startswith(b"TF_STORE:") or len(line)>2048:continue
        try:value=json.loads(line[9:])
        except (ValueError,UnicodeError):continue
        if type(value) is not dict or set(value)!=keys:continue
        if any(type(value[k]) is not bool for k in flags):continue
        if any(type(value[k]) is not str or value[k] not in options for k,options in enums.items()):continue
        if type(value["body_bytes"]) is not int or not 0<=value["body_bytes"]<=16777217:continue
        if type(value["status_code"]) is not int or not -99999999<=value["status_code"]<=99999999:continue
        result.append(value)
        if len(result)==4:break
    return result
