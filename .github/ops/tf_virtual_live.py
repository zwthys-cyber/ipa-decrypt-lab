"""Keep the exact SDK process alive and consume one run/source/nonce-bound age packet."""
import base64
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from cn_protocol import request, code_payload

MARKER=b"TF_VIRTUAL_OTP:waiting"
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None

def envelope(value,waiting):
    if type(value) is not dict or set(value)!={"schema","auth_run","commit","nonce","ciphertext_b64"}:
        raise ValueError()
    if value["schema"]!="tf-virtual-live-relay-v1" or any(value[key]!=waiting[key] for key in ("auth_run","commit","nonce")):
        raise ValueError()
    encoded=value["ciphertext_b64"]
    if type(encoded) is not str or not 0<len(encoded)<=12000:raise ValueError()
    cipher=base64.b64decode(encoded,validate=True)
    if not 0<len(cipher)<=8192 or not cipher.startswith(b"age-encryption.org/v1\n"):raise ValueError()
    return cipher

def decrypt_cipher(cipher,waiting,identity,env):
    with tempfile.TemporaryDirectory(prefix="tf-code-",dir=env["RUNNER_TEMP"]) as folder:
        root=Path(folder);root.chmod(0o700)
        key=root/"identity";key.write_text(identity);key.chmod(0o600)
        child={k:env[k] for k in ("HOME","PATH","LANG") if k in env}
        result=subprocess.run(["age","-d","-i",str(key)],input=cipher,capture_output=True,timeout=15,env=child)
        if result.returncode or not 0<len(result.stdout)<=2048:raise ValueError()
        return code_payload(json.loads(result.stdout),waiting)

def relay_url(waiting):
    request(waiting,waiting["auth_run"],waiting["commit"])
    branch="tf-virtual-code-"+waiting["auth_run"]+"-"+waiting["nonce"]
    return "https://raw.githubusercontent.com/zwthys-cyber/ipa-decrypt-lab/"+branch+"/relay.json"

def poll(waiting,env):
    url=relay_url(waiting)+"?poll="+str(int(time.time()))
    opener=urllib.request.build_opener(NoRedirect())
    req=urllib.request.Request(url,headers={"User-Agent":"ipa-lab-live-verification","Cache-Control":"no-cache"})
    try:
        with opener.open(req,timeout=5) as response:
            raw=response.read(16385)
    except urllib.error.HTTPError as error:
        if error.code==404:return None
        raise ValueError() from None
    if not 0<len(raw)<=16384:raise ValueError()
    cipher=envelope(json.loads(raw),waiting)
    return decrypt_cipher(cipher,waiting,env["DELIVERY_AGE_IDENTITY"],env)

def live(binary,root,env,email,password):
    from tf_virtual import public_env
    child=public_env(env);child["TF_VIRTUAL_LIVE_OTP"]="1"
    process=subprocess.Popen([binary,"--authenticate",str(root)],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=child)
    selector=selectors.DefaultSelector()
    selector.register(process.stdout,selectors.EVENT_READ,"stdout")
    selector.register(process.stderr,selectors.EVENT_READ,"stderr")
    buffers={"stdout":bytearray(),"stderr":bytearray()}
    waiting=None;sent=False;last_poll=0;deadline=time.monotonic()+660
    try:
        process.stdin.write((email+"\n"+password+"\n").encode());process.stdin.flush()
        while process.poll() is None:
            for key,_ in selector.select(timeout=1):
                data=os.read(key.fileobj.fileno(),4096)
                if not data:selector.unregister(key.fileobj);continue
                buffers[key.data].extend(data)
                if len(buffers[key.data])>65536:raise ValueError()
            if not waiting and MARKER in buffers["stderr"].splitlines():
                waiting={"schema":"cn-live-request-v1","auth_run":env["GITHUB_RUN_ID"],
                         "commit":env["GITHUB_SHA"],"nonce":secrets.token_hex(16),
                         "expires":int(time.time())+300}
                request(waiting,env["GITHUB_RUN_ID"],env["GITHUB_SHA"])
                handshake=Path(env["CN_HANDSHAKE_FILE"])
                if handshake.is_symlink():raise ValueError()
                handshake.write_text(json.dumps(waiting));handshake.chmod(0o600)
                print(json.dumps({"schema":"tf-virtual-live-v1","status":"verification_pending","request":waiting}),flush=True)
            if waiting and not sent:
                if int(time.time())>=waiting["expires"]:raise subprocess.TimeoutExpired(binary,300)
                if time.monotonic()-last_poll>=3:
                    last_poll=time.monotonic()
                    code=poll(waiting,env)
                    if code is not None:
                        process.stdin.write((code+"\n").encode());process.stdin.flush()
                        process.stdin.close();sent=True
                        print('{"schema":"tf-virtual-live-v1","status":"verification_submitted_to_bound_process"}',flush=True)
            if time.monotonic()>deadline:raise subprocess.TimeoutExpired(binary,660)
        for name,stream in (("stdout",process.stdout),("stderr",process.stderr)):
            buffers[name].extend(stream.read(65537-len(buffers[name])))
            if len(buffers[name])>65536:raise ValueError()
        return subprocess.CompletedProcess([binary],process.returncode,bytes(buffers["stdout"]),bytes(buffers["stderr"]))
    finally:
        selector.close()
        if process.poll() is None:process.kill();process.wait()
        if process.stdin and not process.stdin.closed:process.stdin.close()
