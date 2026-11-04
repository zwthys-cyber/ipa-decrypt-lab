"""Read two native method implementations in an account-free disposable process."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

METHODS = (
    "-[AMSAuthorizeMachineTask _buildRequestParametersWithError:]",
    "-[AMSAuthorizeMachineTask _buildRequest]",
    "-[ACAccountStore ams_secureTokenForAccount:]",
    "-[NSDictionary ams_secureToken]",
    "+[AMSAnisette _accountIDForType:account:]",
    "+[AMSAnisette _headersForRequest:account:type:]",
    "+[AMSURLRequestDecoration addAnisetteHeadersToRequest:account:type:bag:]",
    "-[AMSAuthorizeMachineTask initWithUsername:authorizeReason:bag:presentationDelegate:]",
    "-[AMSKeybag importKeybagWithData:error:]",
    "__40-[AMSKeybag importKeybagWithData:error:]_block_invoke",
)
LINE = re.compile(r"^\s*(?:->\s*)?0x[0-9a-fA-F]+\s+<\+([0-9]+)>:\s+(.+)$")
HEADER = re.compile(r"^([^\s\x60]+)\x60(.+):$")
FOCUS = re.compile(r"xToken|needDiv|ownerDsid|kbsync|setAnisetteType|ams_.*(?:[Tt]oken|[Pp]assword)|[Aa]uthentication|[Aa]nisette|MDM|AMD|[Ee]phemeral|setCredentialSource|setAuthenticationType|[Ii]mport|[Ss]tatus|AMSError|ha0d|[Ff]air[Pp]lay")

def extract(output):
    methods = {}
    current = None
    if not isinstance(output, str) or len(output) > 524288:
        return methods
    for line in output.splitlines():
        header = HEADER.fullmatch(line.strip())
        if header:
            name = re.sub(r"\([^)]*\)", "", header[2])
            current = name if header[1] == "AppleMediaServices" and name in METHODS else None
            continue
        match = LINE.fullmatch(line)
        if current and match and len(match[2]) <= 1024:
            offset = int(match[1])
            if offset > 16384 or not match[2].isascii():
                continue
            methods.setdefault(current, []).append({"offset": offset, "instruction": match[2]})
        elif line.startswith("(lldb)") or line.startswith("Process "):
            current = None
    result = {}
    for name, rows in methods.items():
        selected = set()
        for i, row in enumerate(rows):
            if FOCUS.search(row["instruction"]):
                selected.update(range(max(0, i-12), min(len(rows), i+9)))
        calls = [row for row in rows if re.search(r"\b(?:callq?|bl|blr)\b", row["instruction"])]
        result[name] = {
            "instruction_count": len(rows),
            "calls": calls[:100],
            "field_context": (rows if ("ams_secureToken" in name or "_accountIDForType" in name or "importKeybag" in name) else [rows[i] for i in sorted(selected)])[:180],
        }
    return result

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    report = {"schema": "ipa-lab-native-authorization-code-v1",
        "account_login_attempted": False, "authorization_request_attempted": False,
        "enrollment_created": False, "decryption_proven": False}
    binary = str(Path("native-authorization-code").resolve())
    commands = ["settings set target.disable-aslr false",
                "breakpoint set --name lab_frameworks_loaded", "run"]
    commands += ['disassemble --name "' + name + '"' for name in METHODS[:2] + METHODS[4:]]
    for variable in ("lab_store_token_impl", "lab_dictionary_token_impl"):
        commands.append("script import json; t=lldb.debugger.GetSelectedTarget(); "
            "v=t.FindFirstGlobalVariable('" + variable + "'); "
            "a=v.GetValueAsUnsigned(); s=t.ResolveLoadAddress(a).GetSymbol(); "
            "lldb.debugger.HandleCommand('disassemble --name ' + json.dumps(s.GetName())) if a and s.IsValid() else None")
    commands += ["process kill", "quit"]
    argv = ["xcrun", "lldb", "--batch", binary]
    for command in commands:
        argv += ["-o", command]
    with tempfile.TemporaryDirectory(prefix="ipa-lab-code-inspect-") as tmp:
        env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "GITHUB_ACTIONS": "true"}
        if os.environ.get("DEVELOPER_DIR"):
            env["DEVELOPER_DIR"] = os.environ["DEVELOPER_DIR"]
        process = subprocess.Popen(argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            out, err = process.communicate(timeout=45)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            report["status"] = "debugger_timeout"
        else:
            output = out.decode("utf-8", errors="replace")
            report["methods"] = extract(output)
            report["status"] = "code_inspected" if len(report["methods"]) == len(METHODS) else "code_unavailable"
            report["debugger_exit_code"] = process.returncode
            # Never print debugger errors, process output, paths, heap/register data or environment.
            report["launch_denied"] = b"not allowed to attach" in err + out
            report["symbol_not_found"] = b"Unable to find symbol" in err + out
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "code_inspected" else 2

if __name__ == "__main__":
    raise SystemExit(main())
