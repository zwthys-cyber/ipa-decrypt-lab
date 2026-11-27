"""Explicit HTTPS-only state RPC; no automatic retry or downgrade to SSH."""
import base64
import hashlib
import http.client
import json
import re
import ssl
from urllib.parse import urlsplit
import tf_task_ssh

MAX_RESPONSE=400000
ORIGIN="42650873653"

def mode(env):
    value=env.get("TF_STATE_TRANSPORT","ssh")
    if value not in {"ssh","https"}:raise ValueError("tf_state_transport_invalid")
    return value

def settings(env):
    url=env.get("TF_STATE_API_URL","")
    token=env.get("TF_STATE_API_TOKEN","")
    endpoint=urlsplit(url)
    if (not re.fullmatch(r"https://[A-Za-z0-9.-]{1,253}(?::443)?/?",url) or
        not endpoint.hostname or endpoint.port not in (None,443) or
        not re.fullmatch(r"[A-Za-z0-9_-]{43,128}",token)):
        raise ValueError("tf_state_transport_invalid")
    return endpoint.hostname,token

def https_rpc(operation,value,env):
    if operation not in {"status","fetch","claim","finish"}:raise ValueError("tf_state_operation_invalid")
    host,token=settings(env)
    conn=http.client.HTTPSConnection(host,443,timeout=45,context=ssl.create_default_context())
    try:
        raw=json.dumps(value,separators=(",",":")).encode()
        if not 0<len(raw)<=16384:raise ValueError("tf_state_request_invalid")
        conn.request("POST","/v1/"+operation,body=raw,headers={"Authorization":"Bearer "+token,
            "Content-Type":"application/json","Accept":"application/json","Cache-Control":"no-store"})
        response=conn.getresponse()
        if response.status!=200 or response.getheader("Content-Type")!="application/json":
            raise ValueError("tf_state_operation_failed")
        body=response.read(MAX_RESPONSE+1)
        if not 0<len(body)<=MAX_RESPONSE:raise ValueError("tf_state_response_invalid")
        parsed=json.loads(body)
        if type(parsed) is not dict or parsed.get("status")=="failed":raise ValueError("tf_state_operation_failed")
        return parsed
    except Exception:
        # Do not log remote bodies, headers, URL, token or low-level exceptions.
        raise ValueError("tf_state_transport_failed") from None
    finally:conn.close()

def rpc(operation,value,env):
    if mode(env)=="https":return https_rpc(operation,value,env)
    return tf_task_ssh.rpc(operation,value,env)

def fetch(env):
    if mode(env)=="ssh":return tf_task_ssh.fetch(env)
    value=https_rpc("fetch",{},env)
    if (set(value)!={"schema","ready","origin_run","sha256","bytes","ciphertext_b64"} or
        value["schema"]!="tf-state-status-v1" or value["ready"] is not True or value["origin_run"]!=ORIGIN or
        type(value["bytes"]) is not int or not 0<value["bytes"]<=256*1024 or
        not isinstance(value["sha256"],str) or not re.fullmatch(r"[a-f0-9]{64}",value["sha256"])):
        raise ValueError("tf_session_not_ready")
    cipher=base64.b64decode(value["ciphertext_b64"],validate=True)
    if (len(cipher)!=value["bytes"] or not cipher.startswith(b"age-encryption.org/v1\n") or
        hashlib.sha256(cipher).hexdigest()!=value["sha256"]):
        raise ValueError("tf_state_response_invalid")
    return cipher
