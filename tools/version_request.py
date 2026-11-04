"""Strict historical version selectors shared by controller, worker and delivery."""
import re

class VersionError(ValueError):
    pass

def selector(value):
    if not isinstance(value, str) or len(value)>32:
        raise VersionError("invalid_version")
    if not value:
        return ""
    if re.fullmatch(r"[1-9][0-9]{5,19}",value):
        return value
    if re.fullmatch(r"[0-9]{1,5}(?:\.[0-9]{1,5}){0,4}",value):
        return value
    raise VersionError("invalid_version")

def external_id(value):
    return bool(re.fullmatch(r"[1-9][0-9]{5,19}",selector(value)))

def resolved_marker(output, requested):
    requested=selector(requested)
    found=re.findall(r"^IPA_LAB_VERSION:([1-9][0-9]{5,19}):([0-9]{1,5}(?:\.[0-9]{1,5}){0,4})$",output,re.M)
    if len(found)!=1:
        raise VersionError("version_resolution_unconfirmed")
    identifier,version=found[0]
    if (external_id(requested) and requested!=identifier) or (not external_id(requested) and requested!=version):
        raise VersionError("downloaded_version_mismatch")
    return identifier,version

def verify_version(info, requested, resolved):
    if requested and info.get("version")!=resolved:
        raise VersionError("downloaded_version_mismatch")
