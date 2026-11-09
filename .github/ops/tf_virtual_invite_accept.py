"""One fixed invitation acceptance, gated by a durable run-bound encrypted intent.

No password login, automatic POST retry, extra agreements, download or decryption.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from tf_invitation import InvitationJournal
from tf_virtual import pack_private, public_env, validate as validate_native

INVITE="yoNuHexZ"
RECIPIENT="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"
class Stop(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def need(value,code="invalid_state"):
    if not value:raise Stop(code)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":")).encode()
def runtime(env):
    need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REF")=="refs/heads/main" and env.get("GITHUB_RUN_ATTEMPT")=="1","run_not_eligible")
    need(re.fullmatch(r"[1-9][0-9]{0,19}",env.get("GITHUB_RUN_ID","")) and re.fullmatch(r"[a-f0-9]{40}",env.get("GITHUB_SHA","")),"run_not_eligible")
def validate_packet(value,env,now=None):
    now=int(time.time() if now is None else now)
    keys={"schema","worker_run","source_commit","nonce","expires","account_binding","record_path","ciphertext_b64","cipher_sha256"}
    need(type(value) is dict and set(value)==keys,"packet_invalid")
    need(value["schema"]=="tf-invite-intent-packet-v1" and value["worker_run"]==env["GITHUB_RUN_ID"] and value["source_commit"]==env["GITHUB_SHA"],"packet_binding")
    need(type(value["nonce"]) is str and re.fullmatch(r"[a-f0-9]{32}",value["nonce"]),"packet_invalid")
    need(type(value["expires"]) is int and now<value["expires"]<=now+600,"intent_expired")
    need(type(value["account_binding"]) is str and re.fullmatch(r"[a-f0-9]{64}",value["account_binding"]),"packet_invalid")
    need(value["record_path"]==".github/ops/tf_invite_intents/"+value["account_binding"]+".json","packet_invalid")
    need(type(value["ciphertext_b64"]) is str and 0<len(value["ciphertext_b64"])<12000,"packet_invalid")
    cipher=base64.b64decode(value["ciphertext_b64"],validate=True)
    need(cipher.startswith(b"age-encryption.org/v1\n") and 0<len(cipher)<=8192 and hashlib.sha256(cipher).hexdigest()==value["cipher_sha256"],"packet_invalid")
    return value
def raw_record(packet):
    url="https://raw.githubusercontent.com/zwthys-cyber/ipa-decrypt-lab/main/"+packet["record_path"]+"?poll="+str(int(time.time()))
    request=urllib.request.Request(url,headers={"User-Agent":"ipa-fixed-invitation-journal","Cache-Control":"no-cache"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=10) as response:
            raw=response.read(16385)
    except urllib.error.HTTPError as error:
        status=error.code;error.close()
        if status==404:return None
        raise Stop("intent_record_unavailable") from None
    need(0<len(raw)<=16384,"intent_record_invalid")
    return json.loads(raw)
def objects(value):
    queue=[value];count=0
    while queue:
        item=queue.pop();count+=1
        need(count<=20000,"catalog_too_large")
        if type(item) is dict:
            yield item;queue.extend(v for v in item.values() if type(v) in (dict,list))
        elif type(item) is list:queue.extend(v for v in item if type(v) in (dict,list))
def target(root):
    info=json.loads((root/"invitation.json").read_bytes())
    need(type(info) is dict and type(info.get("app")) is dict,"invitation_shape")
    app=info["app"];bundle=app.get("bundleId");identifier=app.get("appAdamId")
    need(type(bundle) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{1,254}",bundle),"invitation_shape")
    need(type(identifier) in (str,int) and re.fullmatch(r"[0-9]{1,20}",str(identifier)),"invitation_shape")
    need(app.get("name") in {"A.I.","A.I. beta"},"target_mismatch")
    for item in objects(info):
        need(item.get("requiresAgreement") is not True and item.get("termsAccepted") is not False and item.get("isBetaAgreementAccepted") is not False,"agreement_requires_review")
    return info,bundle,str(identifier)
def membership(catalog,bundle,identifier):
    matches=set()
    for item in objects(catalog):
        name=item.get("bundleId",item.get("bundleIdentifier",item.get("bundleID")))
        value=item.get("appAdamId",item.get("appAdamID",item.get("adamId",item.get("appId"))))
        if name==bundle and type(value) in (str,int) and str(value)==identifier:matches.add((name,str(value)))
    return len(matches)==1
def native(mode,root,env):
    child=public_env(env)
    child.update({key:env[key] for key in ("GITHUB_RUN_ID","GITHUB_SHA","GITHUB_RUN_ATTEMPT")})
    result=subprocess.run([str(Path("tf-sdk-build/tf_virtual_client").resolve()),mode,str(root)],input=b"",
        capture_output=True,timeout=120,env=child)
    need(len(result.stdout)<=4096,"native_result_invalid")
    value=validate_native(json.loads(result.stdout))
    return result.returncode,value
def identity(root,env):
    context=json.loads((root/"tf-session.json").read_bytes())
    key=hashlib.sha256(env["DELIVERY_AGE_IDENTITY"].encode()).digest()
    binding=hmac.new(key,(context["accountId"]+"\0"+INVITE).encode(),hashlib.sha256).hexdigest()
    return context,binding
def seal(root,env,receipt):
    encrypted=subprocess.run(["age","-r",RECIPIENT],input=pack_private(root),capture_output=True,timeout=30,env=public_env(env))
    need(encrypted.returncode==0 and encrypted.stdout.startswith(b"age-encryption.org/v1\n"),"sealing_failed")
    Path("tf-accept-state.age").write_bytes(encrypted.stdout)
    receipt.update(sealed_state_sha256=hashlib.sha256(encrypted.stdout).hexdigest(),sealed_state_bytes=len(encrypted.stdout))
def encrypt_payload(payload,env):
    encrypted=subprocess.run(["age","-r",RECIPIENT],input=canonical(payload),capture_output=True,timeout=30,env=public_env(env))
    need(encrypted.returncode==0 and encrypted.stdout.startswith(b"age-encryption.org/v1\n") and len(encrypted.stdout)<=8192,"sealing_failed")
    return encrypted.stdout
def decrypt_payload(packet,root,env):
    key=root/"intent-key.txt";key.write_text(env["DELIVERY_AGE_IDENTITY"]);key.chmod(0o600)
    try:
        result=subprocess.run(["age","-d","-i",str(key)],input=base64.b64decode(packet["ciphertext_b64"],validate=True),
            capture_output=True,timeout=30,env=public_env(env))
        need(result.returncode==0 and len(result.stdout)<=4096,"intent_decryption_failed")
        return json.loads(result.stdout)
    finally:key.unlink(missing_ok=True)
def payload_valid(payload,packet,app_binding,profile,now):
    keys={"schema","worker_run","source_commit","nonce","issued_at","expires","account_binding","app_binding","invite","origin_run","origin_source"}
    need(type(payload) is dict and set(payload)==keys and payload["schema"]=="tf-invite-intent-v1","intent_payload_invalid")
    need(all(payload[key]==packet[key] for key in ("worker_run","source_commit","nonce","expires","account_binding")),"intent_payload_binding")
    need(payload["invite"]==INVITE and payload["app_binding"]==app_binding and payload["origin_run"]==profile["run_id"] and payload["origin_source"]==profile["source_commit"],"intent_payload_binding")
    need(type(payload["issued_at"]) is int and 0<=now-payload["issued_at"]<=600 and now<payload["expires"]<=payload["issued_at"]+600,"intent_expired")
def main():
    os.umask(0o077);env=dict(os.environ)
    receipt={"schema":"tf-accept-control-v1","status":"failed","stage":"initialization",
        "run_id":env.get("GITHUB_RUN_ID"),"source_commit":env.get("GITHUB_SHA"),
        "acceptance_attempted":False,"invitation_accepted":False,"downloaded":False,"decryption_proven":False,
        "existing_credentials_changed":False}
    try:
        runtime(env);need(sys.argv[1:] in (["prepare"],["consume"]),"mode_invalid")
        need(json.loads(Path("config/delivery.json").read_text())["recipient"]==RECIPIENT,"recipient_invalid")
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(prefix="tf-accept-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder);root.chmod(0o700)
            receipt["stage"]="restore";restore(root,env)
            try:
                receipt["stage"]="refresh_before_intent"
                code,result=native("--invite-refresh",root,env);receipt["result"]=result
                need(code==0 and result["tf_authenticated"] and result["catalog_received"],"read_preflight_failed")
                info,bundle,identifier=target(root)
                if membership(json.loads((root/"catalog.json").read_bytes()),bundle,identifier):
                    receipt["invitation_accepted"]=True;receipt["status"]="already_joined"
                else:
                    need(info.get("status")=="OPEN","invitation_not_open")
                    context,binding=identity(root,env)
                    app_binding=hashlib.sha256((bundle+"\0"+identifier).encode()).hexdigest()
                    profile=json.loads((root/"profile.json").read_bytes())
                    if sys.argv[1]=="prepare":
                        issued=int(time.time());nonce=secrets.token_hex(16)
                        payload={"schema":"tf-invite-intent-v1","worker_run":env["GITHUB_RUN_ID"],"source_commit":env["GITHUB_SHA"],
                            "nonce":nonce,"issued_at":issued,"expires":issued+600,"account_binding":binding,
                            "app_binding":app_binding,"invite":INVITE,"origin_run":profile["run_id"],"origin_source":profile["source_commit"]}
                        cipher=encrypt_payload(payload,env)
                        packet={"schema":"tf-invite-intent-packet-v1","worker_run":env["GITHUB_RUN_ID"],"source_commit":env["GITHUB_SHA"],
                            "nonce":nonce,"expires":issued+600,"account_binding":binding,
                            "record_path":".github/ops/tf_invite_intents/"+binding+".json",
                            "ciphertext_b64":base64.b64encode(cipher).decode(),"cipher_sha256":hashlib.sha256(cipher).hexdigest()}
                        validate_packet(packet,env)
                        need(raw_record(packet) is None,"intent_already_recorded")
                        Path("tf-invite-pending.json").write_bytes(canonical(packet))
                        receipt["status"]="awaiting_durable_intent";receipt["stage"]="intent_prepared"
                        receipt["pending"]={key:packet[key] for key in ("worker_run","source_commit","nonce","expires","account_binding","record_path","cipher_sha256")}
                    else:
                        packet=validate_packet(json.loads(Path("tf-invite-pending.json").read_bytes()),env)
                        need(packet["account_binding"]==binding,"packet_binding")
                        receipt["stage"]="waiting_for_durable_intent"
                        print(json.dumps({"schema":"tf-accept-progress-v1","stage":"waiting_for_durable_intent","run_id":env["GITHUB_RUN_ID"]}),flush=True)
                        record=None
                        while int(time.time())<packet["expires"]:
                            record=raw_record(packet)
                            if record is not None:break
                            time.sleep(5)
                        need(record is not None,"intent_expired")
                        need(record==packet,"intent_already_recorded")
                        payload=decrypt_payload(packet,root,env)
                        payload_valid(payload,packet,app_binding,profile,int(time.time()))
                        receipt["stage"]="verify_before_post"
                        code,result=native("--invite-refresh",root,env);receipt["result"]=result
                        need(code==0,"read_preflight_failed")
                        info,bundle_now,identifier_now=target(root)
                        need((bundle_now,identifier_now)==(bundle,identifier),"target_mismatch")
                        if membership(json.loads((root/"catalog.json").read_bytes()),bundle,identifier):
                            receipt["invitation_accepted"]=True;receipt["status"]="already_joined"
                        else:
                            need(info.get("status")=="OPEN","invitation_not_open")
                            with sqlite3.connect(root/"invitation-intents.sqlite") as connection:
                                need(InvitationJournal(connection).claim(context["accountId"],INVITE,env["GITHUB_RUN_ID"]+"_"+packet["nonce"]),"local_intent_exists")
                            connection.close()
                            approved={"schema":"tf-invite-approved-v1","approved":True,"worker_run":env["GITHUB_RUN_ID"],
                                "source_commit":env["GITHUB_SHA"],"invite":INVITE,"nonce":packet["nonce"],"expires":packet["expires"]}
                            (root/"invitation-intent-approved.json").write_bytes(canonical(approved))
                            need(int(time.time())<packet["expires"],"intent_expired")
                            receipt["stage"]="single_acceptance_post";receipt["acceptance_attempted"]=True
                            Path("tf-accept-receipt.json").write_bytes(canonical(receipt))
                            try:
                                code,result=native("--invite-accept",root,env);receipt["post_result"]=result
                                receipt["post_response_confirmed"]=code==0 and result["status"]=="acceptance_response_received"
                            except Exception:receipt["post_response_confirmed"]=False
                            receipt["stage"]="verify_membership"
                            code,result=native("--invite-refresh",root,env);receipt["result"]=result
                            receipt["invitation_accepted"]=code==0 and membership(json.loads((root/"catalog.json").read_bytes()),bundle,identifier)
                            receipt["status"]="invitation_accepted" if receipt["invitation_accepted"] else "acceptance_outcome_unverified"
            finally:
                seal(root,env,receipt)
    except Stop as error:receipt["failure_category"]=str(error)
    except Exception:receipt["failure_category"]="control_failed"
    Path("tf-accept-receipt.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"] in {"awaiting_durable_intent","already_joined","invitation_accepted"} else 2
if __name__=="__main__":raise SystemExit(main())
