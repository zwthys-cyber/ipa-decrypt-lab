"""Credential-free transport controls. Never publish response bodies, headers or IPs."""
import json
import math
import os
from pathlib import Path
import re
import ssl
import subprocess

def main():
    env={key:os.environ[key] for key in ("HOME","PATH","LANG") if key in os.environ}
    prefix=subprocess.run(["brew","--prefix"],capture_output=True,timeout=10,env=env,check=True).stdout.decode().strip()
    curl_prefix=subprocess.run(["brew","--prefix","curl"],capture_output=True,timeout=10,env=env,check=True).stdout.decode().strip()
    source=Path("native-source/apple-auth/src/client/transport.cpp").read_text()
    bundle=""
    for name in ("apple_root_hex","apple_root_g3_hex"):
        match=re.search(r"constexpr char "+name+r'\[\] =\s*((?:"[0-9a-f]+"\s*)+);',source)
        if not match:raise ValueError()
        der=bytes.fromhex("".join(re.findall(r'"([0-9a-f]+)"',match.group(1))))
        bundle+=ssl.DER_cert_to_PEM_cert(der)
    system=Path(prefix)/"etc/ca-certificates/cert.pem"
    if system.is_file():bundle+=system.read_text()
    trust=Path("tf-public-ca.pem");trust.write_text(bundle)
    backends={"system":"/usr/bin/curl","sdk_curl":str(Path(curl_prefix)/"bin/curl")}
    endpoints={"gsa_lookup":"https://gsa.apple.com/grandslam/GsService2/lookup",
               "public_bag":"https://init.itunes.apple.com/bag.xml?ix=6",
               "gsa_service":"https://gsa.apple.com/grandslam/GsService2",
               "gsas_service":"https://gsas.apple.com/grandslam/GsService2"}
    results=[]
    for backend,binary in backends.items():
        for endpoint,url in endpoints.items():
            modes=("default","http1","http1_ipv4") if endpoint=="gsa_lookup" else ("default",)
            for mode in modes:
                command=[binary,"--silent","--show-error","--max-time","10","--connect-timeout","6",
                         "--proto","=https","--cacert",str(trust.resolve()),
                         "--output",os.devnull,"--write-out","%{http_code} %{time_total} %{http_version}",url]
                if backend=="sdk_curl":command[1:1]=["--ca-native"]
                if mode in ("http1","http1_ipv4"):command[1:1]=["--http1.1"]
                if mode=="http1_ipv4":command[1:1]=["--ipv4"]
                item={"backend":backend,"endpoint":endpoint,"mode":mode,"curl_exit":-1,
                      "http_status":0,"total_ms":0,"http_version":"unavailable"}
                try:
                    process=subprocess.run(command,capture_output=True,timeout=13,env=env)
                    item["curl_exit"]=max(-128,min(255,process.returncode))
                    if len(process.stdout)<=128:
                        match=re.fullmatch(rb"([0-9]{3}) ([0-9]+(?:\.[0-9]+)?) ([0-9.]+)",process.stdout.strip())
                        if match:
                            elapsed=float(match[2]);status=int(match[1]);version=match[3].decode()
                            if math.isfinite(elapsed) and 0<=elapsed<=20 and 0<=status<=599 and version in {"0","1","1.0","1.1","2","3"}:
                                item.update(http_status=status,total_ms=int(elapsed*1000),http_version=version)
                except Exception:pass
                results.append(item)
                print(json.dumps({"schema":"tf-public-connectivity-probe-v1",**item}),flush=True)
    report={"schema":"tf-public-connectivity-v1","account_operation_attempted":False,
            "response_values_published":False,"results":results}
    Path("tf-connectivity.json").write_text(json.dumps(report,sort_keys=True))
    return 0
if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception:raise SystemExit("tf_public_connectivity_unavailable")
