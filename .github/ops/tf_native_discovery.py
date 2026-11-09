"""Run credential-free native discovery without exposing framework logs."""
import json
import os
from pathlib import Path
import subprocess

def validate(value):
    if type(value) is not dict or set(value) != {
        "schema","frameworks","candidates","testflight_surface","account_operation_attempted","raw_values_published"
    }:
        raise ValueError()
    if value["schema"] != "testflight-native-discovery-v1":
        raise ValueError()
    if value["account_operation_attempted"] is not False or value["raw_values_published"] is not False:
        raise ValueError()
    if type(value["frameworks"]) is not dict or set(value["frameworks"]) != {
        "AuthKit","AppleMediaServices","StoreServices","TestFlightCore"
    } or any(type(v) is not bool for v in value["frameworks"].values()):
        raise ValueError()
    if type(value["candidates"]) is not dict or set(value["candidates"]) != {
        "authkit","store_services","deviceGUID","deviceGUIDData","deviceIdentifier",
        "uniqueDeviceIdentifier","deviceUDID"
    }:
        raise ValueError()
    for candidate in value["candidates"].values():
        if type(candidate) is not dict or set(candidate) != {"available","value"} or type(candidate["available"]) is not bool:
            raise ValueError()
        shape=candidate["value"]
        if type(shape) is not dict or set(shape) != {"kind","length","hardware20_shape"}:
            raise ValueError()
        if shape["kind"] not in ("string","data","other","absent") or type(shape["hardware20_shape"]) is not bool:
            raise ValueError()
        if type(shape["length"]) is not int or not 0 <= shape["length"] <= 256:
            raise ValueError()
    surface=value["testflight_surface"]
    if type(surface) is not list or len(surface)>128:
        raise ValueError()
    for entry in surface:
        if type(entry) is not dict or set(entry)!={"class","selector","class_method"} or type(entry["class_method"]) is not bool:
            raise ValueError()
        for key in ("class","selector"):
            if type(entry[key]) is not str or not 0<len(entry[key])<=192 or any(ord(c)<32 or ord(c)>126 for c in entry[key]):
                raise ValueError()
    return value

def main():
    os.umask(0o077)
    env={key:os.environ[key] for key in ("HOME","PATH","LANG","RUNNER_TEMP") if key in os.environ}
    try:
        binary=str(Path("tf-native-discovery").resolve())
        check=subprocess.run([binary,"--self-test"],stdin=subprocess.DEVNULL,capture_output=True,timeout=15,env=env)
        if check.returncode:raise ValueError()
        result=subprocess.run([binary],stdin=subprocess.DEVNULL,capture_output=True,timeout=60,env=env)
        if result.returncode or len(result.stdout)>65536:raise ValueError()
        value=validate(json.loads(result.stdout))
        print(json.dumps(value,sort_keys=True),flush=True)
        return 0
    except Exception:
        print('{"schema":"testflight-native-discovery-v1","status":"discovery_unavailable"}',flush=True)
        return 2

if __name__=="__main__":raise SystemExit(main())
