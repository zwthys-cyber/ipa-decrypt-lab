"""Inspect allowlisted native implementations in an account-free disposable process."""
import argparse
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
    "-[AMSFairPlayContext fairplayContextIDWithError:]",
    "ha0dkchaters6",
    "c7866effa",
    "-[AMSFairPlayContext _validateFairPlayPath]",
    "__48-[AMSAuthorizeMachineTask _performAuthorization]_block_invoke_2",
    "-[AMSKeybag importDiversityBagWithData:error:]",
    "__46-[AMSKeybag importDiversityBagWithData:error:]_block_invoke",
)
COMMERCE_METHODS = (
    "-[CKStoreClient initWithClientIdentifier:]",
    "+[CKStoreClient storeClientForIdentifier:]",
    "-[CKStoreClient initWithClientIdentifier:serverType:]",
    "-[CKStoreAccount _initWithStoreClient:plist:]",
    "-[CKMachineAuthorizationContext _requestBodyForAccount:bagURLKey:]",
    "-[CKMachineAuthorizationContext _runRequestWithAccount:bagURLKey:authenticationContext:completionHandler:]",
    "+[ServiceProxy _commerceConnection]",
    "+[ServiceProxy commerceServiceInterface]",
    "-[CKStoreAccount _legacyStoreAccount]",
    "+[CKStoreAccount _storeAccountFromACAccount:client:]",
)
COMMERCE_RESPONSE_METHODS = (
    "__106-[CKMachineAuthorizationContext _runRequestWithAccount:bagURLKey:authenticationContext:completionHandler:]_block_invoke",
    "__66-[CKMachineAuthorizationContext _requestBodyForAccount:bagURLKey:]_block_invoke",
)
COMMERCE_REQUEST_METHODS = (
    "-[CKStoreRequest _URLRequestWithError:]",
    "-[CKStoreRequest initWithStoreClient:URL:]",
    "-[CKStoreRequest initWithStoreClient:bagURLKey:]",
    "-[CKStoreRequest _cookieHeader]",
    "+[CKStoreRequest userAgentForStoreClient:]",
    "-[CKMachineAuthorizationContext initWithStoreClient:]",
)
AMS_CORE_METHODS = METHODS
COMMERCE_ACCOUNT_METHODS = (
    "-[CKAccountStore viewAccount]",
    "-[CKMachineAuthorizationContext deauthorizeMachineWithCompletionHandler:]",
)
ACCOUNT_INFO_METHODS = (
    "-[AMSAccountDeviceInfoTask _deviceInfoRequest]",
    "-[AMSAccountDeviceInfoTask _requestWithURL:]",
    "-[AMSAccountDeviceInfoTask _updateAccountWithInfo:]",
    "-[AMSAccountDeviceInfoResult initWithAccount:responseDictionary:]",
)
COMMERCE_SYMBOLS = COMMERCE_METHODS + COMMERCE_RESPONSE_METHODS + COMMERCE_REQUEST_METHODS + COMMERCE_ACCOUNT_METHODS
METHODS += COMMERCE_SYMBOLS + ACCOUNT_INFO_METHODS
LINE = re.compile(r"^\s*(?:->\s*)?0x[0-9a-fA-F]+\s+<\+([0-9]+)>:\s+(.+)$")
HEADER = re.compile(r"^([^\s\x60]+)\x60(.+):$")
FOCUS = re.compile(r"xToken|needDiv|ownerDsid|kbsync|setAnisetteType|ams_.*(?:[Tt]oken|[Pp]assword)|[Aa]uthentication|[Aa]nisette|MDM|AMD|[Ee]phemeral|setCredentialSource|setAuthenticationType|[Ii]mport|[Ss]tatus|AMSError|ha0d|[Ff]air[Pp]lay|[Cc]ontext|SC Info|fpsd|Shared|XtCq|directory|Directory|42023|42032|42018|5bd9|5bd0|5bde|a427|a430|a422|open|mkdir|stat|access|fcntl|File|[Dd]iversity|divbag|keybag|kbSync|dsID|_legacy|[Rr]eply|[Ee]ntitle|MachService|viewAccount|accountInfo|deviceInfo|[Aa]uthoriz|[Aa]ssociate|[Cc]omputer|[Mm]achine|_deviceInfo|_updateAccount")

def extract(output):
    methods = {}
    current = None
    if not isinstance(output, str) or len(output) > 524288:
        return methods
    for line in output.splitlines():
        header = HEADER.fullmatch(line.strip())
        if header:
            name = re.sub(r"\([^)]*\)", "", header[2])
            current = name if name in METHODS and header[1] == ("CommerceKit" if name in COMMERCE_SYMBOLS else "AppleMediaServices") else None
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
            "field_context": (rows if (len(rows) <= 180 or "ams_secureToken" in name or "_accountIDForType" in name or "importKeybag" in name) else [rows[i] for i in sorted(selected)])[:180],
        }
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("ams", "commerce", "commerce-response", "commerce-request", "account-management"), default="ams")
    args = parser.parse_args()
    methods = {"commerce": COMMERCE_METHODS, "commerce-response": COMMERCE_RESPONSE_METHODS, "commerce-request": COMMERCE_REQUEST_METHODS,
               "ams": AMS_CORE_METHODS, "account-management": COMMERCE_ACCOUNT_METHODS + ACCOUNT_INFO_METHODS}[args.scope]
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    report = {"schema": "ipa-lab-native-authorization-code-v1",
        "account_login_attempted": False, "authorization_request_attempted": False,
        "enrollment_created": False, "decryption_proven": False}
    binary = str(Path("native-authorization-code").resolve())
    commands = ["settings set target.disable-aslr false",
                "breakpoint set --name lab_frameworks_loaded", "run"]
    commands += ["script lldb.debugger.HandleCommand(" + repr('disassemble --name "' + name + '"') + ")"
                 for name in methods if name not in ("-[ACAccountStore ams_secureTokenForAccount:]", "-[NSDictionary ams_secureToken]")]
    for variable in (("lab_store_token_impl", "lab_dictionary_token_impl") if args.scope == "ams" else ()):
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
            report["inspection_scope"] = args.scope
            report["output_size_exceeded"] = len(output)>524288
            report["methods"] = extract(output)
            report["status"] = "code_inspected" if set(report["methods"]) == set(methods) else "code_unavailable"
            report["debugger_exit_code"] = process.returncode
            # Never print debugger errors, process output, paths, heap/register data or environment.
            report["launch_denied"] = b"not allowed to attach" in err + out
            report["symbol_not_found"] = b"Unable to find symbol" in err + out
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "code_inspected" else 2

if __name__ == "__main__":
    raise SystemExit(main())
