"""Strict App Store link routing and durable account binding in request IDs."""
import re
import urllib.parse

REQUEST_ID_PATTERN = r"(?:cn_)?[a-f0-9]{32}"

def profile_for_request(rid):
    if not isinstance(rid,str) or not re.fullmatch(REQUEST_ID_PATTERN,rid):
        raise ValueError("invalid_request_id")
    return "cn" if rid.startswith("cn_") else "default"

def workflow_for_request(rid):
    return "china-private-delivery.yml" if profile_for_request(rid)=="cn" else "private-delivery.yml"

def parse_target(text):
    if not isinstance(text,str) or len(text)>1024:
        raise ValueError("invalid target")
    if re.fullmatch(r"[1-9][0-9]{4,19}",text):
        return text,"default"
    value=urllib.parse.urlsplit(text)
    found=re.search(r"/id([1-9][0-9]{4,19})/?$",value.path)
    if (value.scheme!="https" or value.hostname!="apps.apple.com" or value.port not in (None,443)
            or value.username or value.password or value.fragment or not found
            or any(c.isspace() for c in text)):
        raise ValueError("invalid target")
    country=value.path.split("/")[1].lower()
    return found.group(1),"cn" if country=="cn" else "default"
