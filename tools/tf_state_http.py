"""Private managed state transport. No Apple requests or plaintext session handling."""
import base64
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import socket
import sys
from testflight_state import status, connect, claim, finish

MAX_REQUEST=16384
MAX_RESPONSE=400000
OPERATIONS={"status","fetch","claim","finish"}

def token_valid(token):
    return isinstance(token,str) and re.fullmatch(r"[A-Za-z0-9_-]{43,128}",token) is not None

def ready(root):
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid!=os.geteuid() or root.stat().st_mode&0o077:
        raise ValueError("state_volume_not_private")
    for name in ("session.age","acceptance.sqlite"):
        path=root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_uid!=os.geteuid() or path.stat().st_mode&0o077:
            raise ValueError("state_migration_required")
    if status(root).get("ready") is not True:
        raise ValueError("state_migration_required")
    # Never create a replacement ledger on an empty or malformed volume.
    import sqlite3
    with sqlite3.connect((root/"acceptance.sqlite").as_uri()+"?mode=ro",uri=True) as db:
        columns={r[1] for r in db.execute("PRAGMA table_info(invitations)")}
        if columns!={"invite","request_id","run_id","source_commit","nonce","expires","state"}:
            raise ValueError("state_migration_required")
        if db.execute("PRAGMA quick_check").fetchone()!=("ok",):
            raise ValueError("state_migration_required")

def operation(root,kind,value):
    if kind not in OPERATIONS or not isinstance(value,dict):
        raise ValueError("state_operation_invalid")
    if kind in {"status","fetch"}:
        if value:raise ValueError("state_operation_invalid")
        result=status(root)
        if not result.get("ready"):raise ValueError("state_migration_required")
        if kind=="fetch":
            import hashlib
            cipher=(root/"session.age").read_bytes()
            if len(cipher)!=result["bytes"] or hashlib.sha256(cipher).hexdigest()!=result["sha256"]:
                raise ValueError("state_changed")
            result=dict(result,ciphertext_b64=base64.b64encode(cipher).decode("ascii"))
        return result
    # Use the existing durable ledger semantics, including denial after unknown results.
    if not (root/"acceptance.sqlite").is_file() or (root/"acceptance.sqlite").is_symlink():
        raise ValueError("state_migration_required")
    db=connect(root)
    try:return claim(db,value) if kind=="claim" else finish(db,value)
    finally:db.close()

def handler(root,token):
    if not token_valid(token):raise ValueError("invalid_state_service_token")
    class Handler(BaseHTTPRequestHandler):
        protocol_version="HTTP/1.0"
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
        def log_message(self,*args):
            pass
        def reply(self,code,value):
            body=json.dumps(value,separators=(",",":")).encode()
            if len(body)>MAX_RESPONSE:raise ValueError("state_response_too_large")
            self.send_response(code)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Connection","close")
            self.end_headers()
            self.wfile.write(body)
        def do_POST(self):
            try:
                supplied=self.headers.get_all("Authorization",[])
                if len(supplied)!=1 or not hmac.compare_digest(supplied[0].encode(),("Bearer "+token).encode()):
                    self.reply(401,{"status":"failed"});return
                if self.path not in {"/v1/"+name for name in OPERATIONS}:
                    self.reply(404,{"status":"failed"});return
                lengths=self.headers.get_all("Content-Length",[])
                if (self.headers.get("Transfer-Encoding") or len(lengths)!=1 or
                    not re.fullmatch(r"[0-9]{1,5}",lengths[0]) or
                    not 0<int(lengths[0])<=MAX_REQUEST or
                    self.headers.get("Content-Type")!="application/json"):
                    self.reply(400,{"status":"failed"});return
                raw=self.rfile.read(int(lengths[0]))
                if len(raw)!=int(lengths[0]):raise ValueError()
                result=operation(root,self.path[4:],json.loads(raw))
                self.reply(200,result)
            except (BrokenPipeError,ConnectionResetError,socket.timeout):
                pass
            except Exception:
                try:self.reply(409,{"status":"failed"})
                except OSError:pass
    return Handler

class StateServer(HTTPServer):
    def handle_error(self,request,client_address):
        pass

def main():
    os.umask(0o077)
    try:
        from telegram_daemon import require_managed_volume
        volume=Path(os.environ.get("TF_STATE_VOLUME","/var/lib/ipazake"))
        require_managed_volume(volume)
        root=volume/"testflight"
        ready(root)
        token=os.environ.get("TF_STATE_API_TOKEN","")
        port=int(os.environ.get("PORT","8080"))
        if not 1024<=port<=65535:raise ValueError()
        # Only expose via a trusted TLS-terminating platform proxy. No plaintext public port.
        bind=os.environ.get("TF_STATE_BIND","127.0.0.1")
        if bind not in {"127.0.0.1","0.0.0.0"}:raise ValueError()
        if bind=="0.0.0.0" and os.environ.get("TF_STATE_TRUSTED_TLS_PROXY")!="1":raise ValueError()
        with StateServer((bind,port),handler(root,token)) as server:
            server.serve_forever()
    except Exception:
        print("state_service_failed",file=sys.stderr);return 2
    return 0

if __name__=="__main__":raise SystemExit(main())
