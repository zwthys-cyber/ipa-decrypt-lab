"""Same-virtual-identity lookup controls; no Apple ID, password or cookies."""
import json
import os
from pathlib import Path
import re
import ssl
import subprocess

def header_lines(headers):
    if type(headers) is not dict or not 0<len(headers)<=64:raise ValueError()
    lines=[]
    for key,value in headers.items():
        if type(key) is not str or re.fullmatch(r"[A-Za-z0-9-]{1,96}",key) is None:raise ValueError()
        if key.lower() in {"cookie","authorization","x-dsid","dsid","x-apple-id","x-token"}:raise ValueError()
        if type(value) is not str or not 0<len(value)<=16384 or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError()
        lines.append(key+": "+value)
    return "\n".join(lines)+"\n"

def controls(binary,root,env):
    from tf_virtual import validate, public_env
    child=public_env(env)
    paths=[root/"lookup-headers.json",root/"lookup.headers",root/"lookup-public-ca.pem"]
    try:
        prepared=subprocess.run([binary,"--prepare-lookup",str(root)],input=b"",capture_output=True,timeout=20,env=child)
        if prepared.returncode or len(prepared.stdout)>4096:raise ValueError()
        value=validate(json.loads(prepared.stdout))
        if value["status"]!="lookup_prepared" or value["account_login_attempted"]:raise ValueError()
        if paths[0].stat().st_size>32768:raise ValueError()
        paths[1].write_text(header_lines(json.loads(paths[0].read_text())));paths[1].chmod(0o600)
        prefix=subprocess.run(["brew","--prefix"],capture_output=True,timeout=10,env=child,check=True).stdout.decode().strip()
        curl_prefix=subprocess.run(["brew","--prefix","curl"],capture_output=True,timeout=10,env=child,check=True).stdout.decode().strip()
        source=Path("native-source/apple-auth/src/client/transport.cpp").read_text()
        bundle=""
        for name in ("apple_root_hex","apple_root_g3_hex"):
            match=re.search(r"constexpr char "+name+r'\[\] =\s*((?:"[0-9a-f]+"\s*)+);',source)
            if not match:raise ValueError()
            bundle+=ssl.DER_cert_to_PEM_cert(bytes.fromhex("".join(re.findall(r'"([0-9a-f]+)"',match.group(1)))))
        system=Path(prefix)/"etc/ca-certificates/cert.pem"
        if system.is_file():bundle+=system.read_text()
        paths[2].write_text(bundle);paths[2].chmod(0o600)
        results=[]
        for mode in ("default","http1_ipv4"):
            command=[str(Path(curl_prefix)/"bin/curl"),"--silent","--show-error","--max-time","12",
                "--connect-timeout","6","--proto","=https","--ca-native","--cacert",str(paths[2]),
                "--header","@"+str(paths[1]),"--output",os.devnull,"--write-out","%{http_code} %{time_total}",
                "https://gsa.apple.com/grandslam/GsService2/lookup"]
            if mode=="http1_ipv4":command[1:1]=["--http1.1","--ipv4"]
            process=subprocess.run(command,capture_output=True,timeout=15,env=child)
            result={"mode":mode,"curl_exit":max(-128,min(255,process.returncode)),"http_status":0,"total_ms":0}
            match=re.fullmatch(rb"([0-9]{3}) ([0-9]+(?:\.[0-9]+)?)",process.stdout.strip()) if len(process.stdout)<=128 else None
            if match and 0<=float(match[2])<=20 and 0<=int(match[1])<=599:
                result.update(http_status=int(match[1]),total_ms=int(float(match[2])*1000))
            results.append(result)
        return results
    finally:
        for path in paths:path.unlink(missing_ok=True)
