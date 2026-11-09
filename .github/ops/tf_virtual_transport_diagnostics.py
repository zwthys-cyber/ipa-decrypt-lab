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
