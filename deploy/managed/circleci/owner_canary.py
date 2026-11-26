"""GitHub-only bounded real owner task; no webhook switch, source replay or project execution on the workspace."""
import argparse
import base64
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipapp
from cloud_inventory import api,WORKER
from control_cloud import prepared_metadata,multipart
from runtime_cloud import deploy,call,ORIGIN
from read_preserved import decrypt
from verify_preservation import verify,PROMOTED

RECIPIENT="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"
def need(ok,code):
 if not ok:raise ValueError(code)
def public_env(env):
 return {k:env[k] for k in ("PATH","HOME","LANG","TMPDIR") if k in env}
def context(env):
 need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")=="zwthys-cyber/ipa-decrypt-lab" and
  env.get("GITHUB_REF")=="refs/heads/upgrade/managed-runtime-v0.2" and env.get("GITHUB_RUN_ATTEMPT")=="1" and
  env.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and env.get("GITHUB_ACTOR_ID")=="246379322","canary_context")
def preflight(app):
 need(re.fullmatch("[1-9][0-9]{4,19}",app),"canary_app")
 request=urllib.request.Request("https://itunes.apple.com/lookup?id="+app+"&country=us",headers={"User-Agent":"ipa-owner-canary/0.2"})
 from runtime_cloud import NoRedirect
 with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
  raw=response.read(262145);need(response.status==200 and len(raw)<=262144,"canary_metadata")
 rows=json.loads(raw).get("results",[])
 need(len(rows)==1 and str(rows[0].get("trackId"))==app and rows[0].get("kind")=="software" and rows[0].get("price")==0 and
  str(rows[0].get("fileSizeBytes","")).isdecimal() and 0<int(rows[0]["fileSizeBytes"])<=2000000000,"canary_free_app_required")
def build_transport(root):
 source=root/"transport-src";source.mkdir(mode=0o700)
 for name in ("pause_source.py","preserve_source.py"):
  (source/name).write_bytes(Path(__file__).with_name(name).read_bytes())
 (source/"__main__.py").write_text("from pause_source import main\nraise SystemExit(main())\n")
 package=root/"pause.pyz";zipapp.create_archive(source,package)
 return package.read_bytes()
def bootstrap(raw,nonce,source,run,resume=False):
 digest=hashlib.sha256(raw).hexdigest()
 path="/var/tmp/ipazake-canary-"+source+"-"+nonce+".pyz"
 args=["python3",path,"--nonce",nonce,"--source",source,"--run",run]+(["--resume"] if resume else [])
 # Only public, digest-verified runtime code and bounded identifiers cross this command channel.
 return ("import base64,hashlib,os,sys,pathlib\n"+
  "raw=base64.b64decode("+repr(base64.b64encode(raw).decode())+")\n"+
  "assert hashlib.sha256(raw).hexdigest()=="+repr(digest)+"\n"+
  "path=pathlib.Path("+repr(path)+")\n"+
  "try:\n f=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n with os.fdopen(f,'wb') as out:out.write(raw)\n"+
  "except FileExistsError:\n assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()=="+repr(digest)+"\n"+
  "os.execv(sys.executable,"+repr(args)+")\n").encode()
def ssh_args(env,known):
 need(env.get("VPS_HOST") and env.get("SSHPASS") and env.get("VPS_KNOWN_HOSTS"),"canary_ssh_configuration")
 return ["sshpass","-e","ssh","-4","-o","UserKnownHostsFile="+str(known),"-o","StrictHostKeyChecking=yes",
  "-o","ConnectTimeout=15","-o","ServerAliveInterval=15","-o","ServerAliveCountMax=2","-o","LogLevel=ERROR",
  "root@"+env["VPS_HOST"],"env LAB_RUNTIME=vps PYTHONDONTWRITEBYTECODE=1 python3 -"]
def pause_archive(env,root,raw,nonce,output):
 known=root/"known_hosts";known.write_text(env["VPS_KNOWN_HOSTS"]);known.chmod(0o600)
 args=ssh_args(env,known);child=public_env(env);child["SSHPASS"]=env["SSHPASS"]
 with (root/"ssh-error").open("wb") as err,output.open("xb") as dest:
  remote=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=child)
  age=subprocess.Popen(["age","--encrypt","--recipient",RECIPIENT],stdin=remote.stdout,stdout=dest,stderr=err,env=public_env(env))
  remote.stdout.close()
  remote.stdin.write(bootstrap(raw,nonce,env["GITHUB_SHA"],env["GITHUB_RUN_ID"]));remote.stdin.close()
  try:
   code=remote.wait(timeout=180);sealed=age.wait(timeout=30)
  except BaseException:
   remote.kill();age.kill();remote.wait();age.wait();raise
  need(code==0 and sealed==0,"canary_source_snapshot_failed")
 return known
def restore_source(env,known,raw,nonce):
 child=public_env(env);child["SSHPASS"]=env["SSHPASS"]
 result=subprocess.run(ssh_args(env,known),input=bootstrap(raw,nonce,env["GITHUB_SHA"],env["GITHUB_RUN_ID"],True),
  capture_output=True,timeout=100,env=child)
 need(result.returncode==0 and len(result.stdout)<=4096 and json.loads(result.stdout).get("source_restored") is True,"canary_source_restore_failed")
def snapshot_packet(compressed,root,env,nonce,app,cipher_digest):
 verify(io.BytesIO(compressed),root/"verified",expected_frozen=True)
 with tarfile.open(fileobj=io.BytesIO(compressed),mode="r:gz") as archive:
  def read(name,limit):
   item=archive.getmember(name);need(item.isfile() and item.size<=limit,"canary_snapshot_member")
   data=archive.extractfile(item).read(limit+1);need(len(data)==item.size,"canary_snapshot_member");return data
  manifest=json.loads(read("manifest.json",65536));pause=manifest.get("bounded_pause",{})
  need(pause.get("nonce")==nonce and pause.get("source_sha")==env["GITHUB_SHA"] and
   pause.get("run_id")==env["GITHUB_RUN_ID"] and int(time.time())<pause.get("expires_at",0),"canary_pause_binding")
  config=json.loads(read("config/bot.json",65536))
  need(config.get("TELEGRAM_OWNER_ID")==env["RUNTIME_OWNER_ID"],"canary_owner_mismatch")
  database=root/"snapshot.sqlite";database.write_bytes(read("state/state.sqlite3",16*1024*1024));database.chmod(0o600)
 owner=env["RUNTIME_OWNER_ID"];scope=hashlib.sha256(("telegram-owner:"+owner).encode()).hexdigest();legacy=[]
 with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
  need(db.execute("SELECT count(*) FROM updates WHERE done!=1 OR done IS NULL").fetchone()[0]==0,"canary_unfinished_updates")
  for item in db.execute("SELECT scope,rid,app,state,at,created FROM tasks"):
   original=dict(zip(("scope","rid","app","state","at","created"),item))
   profile="tf" if item[1].startswith("tf_") else "cn" if item[1].startswith("cn_") else "default"
   legacy.append(dict(owner_id=owner if item[0]==scope else "legacy:"+item[0],request_id=item[1],profile=profile,
    target=item[2],state=item[3],created_at=item[5],source_json=json.dumps(original,sort_keys=True,separators=(",",":")),
    held=1 if item[3] in ("pending","sending") else 0))
  offset=db.execute("SELECT value FROM metadata WHERE scope=? AND name='offset'",(scope,)).fetchone()
  floor=int(offset[0]) if offset else 0
 legacy.sort(key=lambda r:(r["owner_id"],r["request_id"]))
 encoded=json.dumps(legacy,separators=(",",":"),ensure_ascii=False)
 request_id=hashlib.sha256(("owner-canary:"+env["GITHUB_RUN_ID"]+":"+nonce+":"+app).encode()).hexdigest()[:32]
 packet=dict(nonce=nonce,snapshot_sha256=cipher_digest,session_sha256=PROMOTED,paused_at=pause["paused_at"],
  expires_at=pause["expires_at"],request_id=request_id,target=app,telegram_update_floor=floor,legacy=legacy,
  rows_sha256=hashlib.sha256(encoded.encode()).hexdigest())
 return packet,config["TELEGRAM_BOT_TOKEN"]
def mode(env,bundle,active):
 path="/workers/scripts/"+WORKER;before=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path+"/settings")
 metadata=prepared_metadata(before,env["GITHUB_SHA"],ORIGIN)
 values=dict(RUNTIME_MODE="production" if active else "staging",RUNTIME_EXPORT_ENABLED="1" if active else "0",
  RUNTIME_TELEGRAM_ENABLED="1" if active else "0")
 metadata["bindings"]=[x for x in metadata["bindings"] if x.get("name") not in values]+[dict(type="plain_text",name=k,text=v) for k,v in values.items()]
 content,kind=multipart(metadata,Path(bundle).read_bytes())
 api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path,content,method="PUT",content_type=kind)
def run(bundle,app):
 env=os.environ;context(env);preflight(app);os.umask(0o077)
 output=Path("owner-canary-output");output.mkdir(mode=0o700,exist_ok=False)
 proof=dict(schema="circleci-owner-canary-proof-v1",source_sha=env["GITHUB_SHA"],app_id=app,
  production_cutover=False,source_restored=False,status="prepared")
 def save():
  (output/"receipt.json").write_text(json.dumps(proof,sort_keys=True)+"\n")
  print(json.dumps(proof,sort_keys=True),flush=True)
 save();prepared=deploy(bundle,prepare_only=True);token=prepared["control_token"]
 nonce=secrets.token_hex(16);known=None;paused=False;terminal=False;deadline=0;installed=False;admission_attempted=False
 with tempfile.TemporaryDirectory(prefix="owner-canary-private-") as directory:
  root=Path(directory);raw=build_transport(root)
  # Prepare trusted host keys before attempting a pause so finally can restore even if streaming fails.
  known=root/"known_hosts";known.write_text(env["VPS_KNOWN_HOSTS"]);known.chmod(0o600)
  try:
   paused=True
   archive=output/"source.tar.gz.age";pause_archive(env,root,raw,nonce,archive)
   cipher=archive.read_bytes();compressed=decrypt(cipher,env["DELIVERY_AGE_IDENTITY"],env)
   packet,bot=snapshot_packet(compressed,root,env,nonce,app,hashlib.sha256(cipher).hexdigest());deadline=packet["expires_at"]
   imported=call("canary/install",token,dict(packet=packet));installed=True
   need(imported.get("legacy_rows")==len(packet["legacy"]),"canary_import_readback")
   proof.update(status="source_paused_and_preserved",snapshot_sha256=packet["snapshot_sha256"],
    legacy_rows=imported["legacy_rows"],held_rows=imported["held_rows"]);save()
   api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],"/workers/scripts/"+WORKER+"/secrets",
    dict(name="TELEGRAM_BOT_TOKEN",type="secret_text",text=bot),method="PUT")
   mode(env,bundle,True)
   request=dict(request_id=packet["request_id"],profile="default",target=app,version="")
   admission_attempted=True
   for attempt in range(30):
    try:
     admitted=call("admit-export",token,request);need(admitted.get("job_id"),"canary_admission");break
    except ValueError as error:
     if not any(s in str(error) for s in ("runtime_entry_disabled","runtime_source_not_ready","runtime_fields","http_503")) or attempt==29:raise
     time.sleep(2)
   proof.update(status="admitted_once",job_id=admitted["job_id"],run_id=admitted.get("run_id"));save()
   while time.time()<deadline:
    try:status=call("status",token,dict(job_id=admitted["job_id"]))
    except ValueError as error:
     if "runtime_provider_pending" not in str(error):raise
     time.sleep(3);continue
    if status["state"] in ("completed","closed","cancelled","dispatch_unknown"):
     terminal=status["state"]!="dispatch_unknown";break
    time.sleep(5)
   else:raise ValueError("canary_deadline_no_replay")
   need(status["state"]=="completed" and status.get("export_verified") is True and status.get("ciphertext_cleared") is True and
    status.get("encrypted_images",0)>0 and status.get("decrypted_pages",0)>0,"canary_export_unconfirmed_no_replay")
   proof.update(status="verified",decryption_proven=True,plaintext_bytes=status["plaintext_bytes"],encrypted_images=status["encrypted_images"],
    decrypted_pages=status["decrypted_pages"],file_uploaded=True,telegram_notification_confirmed=status["notification_confirmed"],
    publisher_run_id=status["publisher_run_id"],ciphertext_cleared=True);save()
  finally:
   try:
    if installed:call("canary/revoke",token,dict(nonce=nonce))
    mode(env,bundle,False)
   finally:
    if paused:
     # A stalled worker is killed by its independent deadline watchdog before source admission resumes.
     if admission_attempted and not terminal and deadline:
      while time.time()<deadline+30:time.sleep(min(10,deadline+30-time.time()))
     restore_source(env,known,raw,nonce);proof["source_restored"]=True;save()
  need(proof.get("decryption_proven") is True,"canary_not_verified")
 return proof
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--bundle",required=True);parser.add_argument("--app-id",required=True);args=parser.parse_args()
 try:run(args.bundle,args.app_id);return 0
 except Exception as error:
  code=str(error) if isinstance(error,ValueError) and re.fullmatch("[a-z0-9_]{1,90}",str(error)) else "owner_canary_failed"
  print(code,file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
