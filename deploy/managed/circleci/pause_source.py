"""Verified runtime operation: bounded idle-source pause, frozen encrypted-backup stream, and restore."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from preserve_source import collect

def need(ok,code="canary_source_invalid"):
 if not ok:raise ValueError(code)
def command(args):
 return subprocess.run(args,capture_output=True,timeout=45,check=True)
def bindings(nonce,source,run):
 need(re.fullmatch("[a-f0-9]{32}",nonce) and re.fullmatch("[a-f0-9]{40}",source) and re.fullmatch("[1-9][0-9]{0,19}",run))
 return dict(nonce=nonce,source_sha=source,run_id=run)
def marker_path(nonce):
 root=Path("/var/lib/ipazake/circleci-canary");root.mkdir(mode=0o700,exist_ok=True)
 need(not root.is_symlink() and root.stat().st_mode&0o077==0)
 return root/(nonce+".json")
def restore(expected):
 path=marker_path(expected["nonce"])
 if not path.exists():
  command(["/usr/bin/systemctl","is-active","--quiet","ipazake.service"]);return dict(source_restored=True,was_paused=False)
 need(not path.is_symlink() and path.is_file() and path.stat().st_mode&0o077==0)
 value=json.loads(path.read_bytes());need(all(value.get(k)==v for k,v in expected.items()))
 command(["/usr/bin/systemctl","start","ipazake.service"])
 command(["/usr/bin/systemctl","is-active","--quiet","ipazake.service"])
 subprocess.run(["/usr/bin/systemctl","stop","ipazake-canary-"+expected["nonce"]+".timer"],capture_output=True,timeout=20)
 value["restored_at"]=int(time.time())
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW),"w") as out:json.dump(value,out)
 return dict(source_restored=True)
def pause(expected):
 command(["/usr/bin/systemctl","is-active","--quiet","ipazake.service"])
 health=json.loads(Path("/var/lib/ipazake/health.json").read_bytes())
 need(health.get("task_active") is False and 0<=time.time()-int(health["at"])<120,"canary_source_busy_or_stale")
 path=marker_path(expected["nonce"]);now=int(time.time())
 value=dict(expected,paused_at=now,expires_at=now+900,restore_after=now+1200)
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),"w") as out:json.dump(value,out)
 command(["/usr/bin/systemd-run","--quiet","--on-active=20m","--unit=ipazake-canary-"+expected["nonce"],
  "/usr/bin/systemctl","start","ipazake.service"])
 stopped=False
 try:
  command(["/usr/bin/systemctl","stop","ipazake.service"]);stopped=True
  check=subprocess.run(["/usr/bin/systemctl","is-active","--quiet","ipazake.service"],capture_output=True,timeout=15)
  need(check.returncode!=0,"canary_source_not_stopped")
  with tempfile.TemporaryDirectory(prefix=".circle-canary-",dir="/var/tmp") as directory:
   root=Path(directory)
   manifest=collect(Path("/var/lib/ipazake"),Path("/etc/ipazake"),root)
   manifest.update(frozen=True,bounded_pause=value)
   (root/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
   with tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz") as archive:
    for file in sorted(root.rglob("*")):
     if file.is_file():archive.add(file,arcname=file.relative_to(root).as_posix(),recursive=False)
 except BaseException:
  if stopped:
   try:restore(expected)
   except BaseException:pass
  raise
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--nonce",required=True);parser.add_argument("--source",required=True);parser.add_argument("--run",required=True);parser.add_argument("--resume",action="store_true")
 args=parser.parse_args()
 try:
  need(os.environ.get("LAB_RUNTIME")=="vps" and os.geteuid()==0);os.umask(0o077)
  expected=bindings(args.nonce,args.source,args.run)
  if args.resume:print(json.dumps(restore(expected)))
  else:pause(expected)
  return 0
 except BaseException:
  print("canary_source_operation_failed",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
