"""Account-free crash stack names only. No heap, registers, arguments, or raw debugger output."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from machine_enrollment import stop_private_group

MODULES = {"native-commerce-keybag", "CommerceKit", "StoreFoundation", "AppleMediaServices",
    "Foundation", "CoreFoundation", "AppKit", "libobjc.A.dylib", "libsystem_c.dylib",
    "libsystem_kernel.dylib", "libsystem_pthread.dylib", "dyld"}
NAME = re.compile(r"^[A-Za-z0-9_$+.,:\-\[\]()<> *&=?]+$")
PREFIX = "LAB_COMMERCE_STACK "

def extract(raw):
    if type(raw) is not str or len(raw) > 131072:
        return {}
    for line in raw.splitlines():
        if not line.startswith(PREFIX):
            continue
        try:
            value = json.loads(line[len(PREFIX):])
        except (ValueError, TypeError):
            return {}
        if type(value) is not dict or type(value.get("frames")) is not list or len(value["frames"]) > 24:
            return {}
        result = {"frames": []}
        for key in ("stop_reason", "process_state", "exit_status"):
            if type(value.get(key)) is int and -128 <= value[key] <= 255:
                result[key] = value[key]
        for row in value["frames"]:
            if type(row) is not dict:
                continue
            module, name, offset = row.get("module"), row.get("function"), row.get("offset")
            if (type(module) is str and module in MODULES and type(name) is str and len(name) <= 256
                    and NAME.fullmatch(name) and type(offset) is int and 0 <= offset <= 1048576):
                result["frames"].append({"module": module, "function": name, "offset": offset})
        return result
    return {}

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    with tempfile.TemporaryDirectory(prefix="ipa-lab-commerce-stack-") as temp:
        binary = str(Path("native-commerce-keybag").resolve())
        script = """import json, lldb
p=lldb.debugger.GetSelectedTarget().GetProcess()
t=p.GetSelectedThread()
frames=[]
for i in range(min(t.GetNumFrames(),24)):
 f=t.GetFrameAtIndex(i); s=f.GetSymbol()
 start=s.GetStartAddress().GetLoadAddress(p.GetTarget()) if s.IsValid() else f.GetPC()
 frames.append(dict(module=f.GetModule().GetFileSpec().GetFilename(),function=f.GetFunctionName() or s.GetName() or "unknown",offset=f.GetPC()-start))
print("LAB_COMMERCE_STACK "+json.dumps(dict(process_state=p.GetState(),exit_status=p.GetExitStatus(),stop_reason=t.GetStopReason(),frames=frames)))
"""
        command = "script exec(" + repr(script) + ")"
        env = {"PATH": "/usr/bin:/bin", "HOME": temp, "GITHUB_ACTIONS": "true"}
        if os.environ.get("DEVELOPER_DIR"):
            env["DEVELOPER_DIR"] = os.environ["DEVELOPER_DIR"]
        argv = ["xcrun", "lldb", "--batch", "--no-lldbinit", "-k", command,
            "-k", "script lldb.debugger.GetSelectedTarget().GetProcess().Kill()", "-o", "settings set target.disable-aslr false",
            "-o", "run", "-o", command, "-o", "script lldb.debugger.GetSelectedTarget().GetProcess().Kill()",
            "--", binary, str(Path(temp) / "report.json"), "nonzero"]
        process = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            out, err = process.communicate(timeout=45)
            result = extract(out.decode("utf-8", errors="replace"))
            diagnostic = (out + err).lower()
            result.update(debugger_exit_code=process.returncode,
                debugger_script_error=b"traceback" in diagnostic or b"syntaxerror" in diagnostic,
                debugger_attribute_error=b"attributeerror" in diagnostic,
                debugger_launch_denied=b"not allowed to attach" in diagnostic,
                stack_marker_present=PREFIX.encode() in out, output_size_exceeded=len(out)>131072)
        except subprocess.TimeoutExpired:
            stop_private_group(process)
            process.communicate(timeout=5)
            result = {}
    result.update(schema="ipa-lab-commerce-stack-v1", account_login_attempted=False,
        authorization_request_attempted=False, enrollment_created=False, decryption_proven=False)
    print(json.dumps(result, sort_keys=True))
    return 0 if "frames" in result else 2

if __name__ == "__main__":
    raise SystemExit(main())
