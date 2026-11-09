"""One fixed verified beta return through the existing owner-only local Bot API."""
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
sys.path.insert(0,"/opt/ipazake/current/tools")
from telegram_api import Telegram
from telegram_queue import GitHub,sha256,personalized
from telegram_daemon import load_credentials
from ipa_audit import audit

RUN=42701117321
SOURCE="c59a1e37bf111b21b6571f0e06b07bf533155b70"
ARCHIVE="be78eb57904398be2da324112c62cd8f251868fac6cefd8cfcddb5a0de530b5b"
REQUEST="tf-yoNuHexZ-42701117321"
STATE=Path("/var/lib/ipazake")
MAX=8*1024*1024

def need(value):
    if not value:raise ValueError()

def receipt_valid(value):
    need(type(value) is dict and value.get("schema")=="ipa-private-delivery-v1"
        and value.get("status")=="encrypted_artifact_ready" and value.get("request_id")==REQUEST
        and value.get("run_id")==str(RUN) and value.get("source_commit")==SOURCE
        and value.get("account_profile")=="cn" and value.get("plaintext_verified") is True
        and value.get("account_data_removed") is True and value.get("plaintext_published") is False
        and value.get("runtime_verified") is False
        and value.get("encrypted_images")==1 and value.get("decrypted_pages")==148)
    for key in ("plaintext_bytes","ciphertext_bytes"):
        need(type(value.get(key)) is int and 0<value[key]<MAX)
    for key in ("plaintext_sha256","ciphertext_sha256"):
        need(type(value.get(key)) is str and re.fullmatch("[a-f0-9]{64}",value[key]))
    return value

def claim(connection):
    connection.execute("BEGIN IMMEDIATE")
    try:
        if connection.execute("SELECT state FROM deliveries WHERE request=?",(REQUEST,)).fetchone():
            connection.rollback();return False
        connection.execute("INSERT INTO deliveries VALUES (?,?)",(REQUEST,"intent"))
        connection.commit();return True
    except Exception:connection.rollback();raise

def package(api,root):
    run=api.call("/actions/runs/"+str(RUN))
    need(run.get("head_sha")==SOURCE and run.get("head_branch")=="main" and run.get("run_attempt")==1
        and run.get("path")==".github/workflows/testflight-virtual.yml"
        and run.get("status")=="completed" and run.get("conclusion")=="success")
    items=api.call("/actions/runs/"+str(RUN)+"/artifacts?per_page=100")["artifacts"]
    found=[item for item in items if item.get("name")=="tf-beta-model-"+str(RUN)+"-attempt-1" and item.get("expired") is False]
    need(len(found)==1);item=found[0]
    need(item.get("digest")=="sha256:"+ARCHIVE and 0<item.get("size_in_bytes",0)<MAX)
    archive=root/"sealed.zip";api.archive(item["id"],archive,max_bytes=MAX);need(sha256(archive)==ARCHIVE)
    with zipfile.ZipFile(archive) as zipped:
        expected={"tf-model-export/package.ipa.age","tf-model-export/receipt.json","tf-accept-state.age","tf-beta-receipt.json"}
        need(len(zipped.infolist())==4 and set(zipped.namelist())==expected and all(item.file_size<MAX for item in zipped.infolist()))
        need(zipped.getinfo("tf-model-export/receipt.json").file_size<16384 and zipped.getinfo("tf-beta-receipt.json").file_size<16384)
        outer=json.loads(zipped.read("tf-beta-receipt.json"))
        need(outer.get("source_commit")==SOURCE and outer.get("run_id")==str(RUN)
            and outer.get("status")=="beta_plaintext_verified" and outer.get("decryption_proven") is True)
        receipt=receipt_valid(json.loads(zipped.read("tf-model-export/receipt.json")))
        cipher=root/"package.age"
        with zipped.open("tf-model-export/package.ipa.age") as src,cipher.open("xb") as dst:shutil.copyfileobj(src,dst,1024*1024)
    need(cipher.stat().st_size==receipt["ciphertext_bytes"] and sha256(cipher)==receipt["ciphertext_sha256"])
    return cipher,receipt

def verify_plain(path,receipt):
    need(path.is_file() and path.stat().st_size==receipt["plaintext_bytes"] and sha256(path)==receipt["plaintext_sha256"])
    info=audit(path);need(info["encrypted_slice_count"]==0)
    with zipfile.ZipFile(path) as archive:
        need(not any(personalized(item.filename) for item in archive.infolist()) and archive.testzip() is None)

def main():
    os.umask(0o077)
    result={"schema":"tf-private-return-v1","input_run":str(RUN),"status":"return_failed","delivered":False}
    try:
        need(os.environ.get("LAB_RUNTIME")=="vps" and os.geteuid()!=0)
        values=load_credentials(Path(os.environ["CREDENTIALS_DIRECTORY"])/"bot.json",systemd=True)
        owner=int(values["TELEGRAM_OWNER_ID"]);need(owner>0)
        database=STATE/"tf-private-return.sqlite"
        need(not database.is_symlink())
        connection=sqlite3.connect(database,timeout=20);database.chmod(0o600)
        connection.execute("CREATE TABLE IF NOT EXISTS deliveries(request TEXT PRIMARY KEY,state TEXT NOT NULL)")
        previous=connection.execute("SELECT state FROM deliveries WHERE request=?",(REQUEST,)).fetchone()
        if previous:
            result.update(status="already_delivered" if previous[0]=="confirmed" else "prior_send_outcome_unknown",delivered=previous[0]=="confirmed")
        else:
            bot=Telegram(values["TELEGRAM_BOT_TOKEN"],base="http://127.0.0.1:8081");bot.check()
            need(json.loads((STATE/"health.json").read_text()).get("state")=="ready")
            with tempfile.TemporaryDirectory(prefix="tf-private-return-",dir=STATE) as directory:
                root=Path(directory);root.chmod(0o700)
                encrypted,receipt=package(GitHub(values["GH_TOKEN"]),root)
                output=root/"A.I._TestFlight_decrypted.ipa"
                child={key:os.environ[key] for key in ("PATH","HOME","LANG") if key in os.environ}
                child.update(LAB_RUNTIME="vps",DELIVERY_AGE_IDENTITY=values["DELIVERY_AGE_IDENTITY"])
                completed=subprocess.run(["/opt/ipazake/current/bin/delivery-crypt","decrypt",str(encrypted),str(output)],
                    env=child,stdin=subprocess.DEVNULL,capture_output=True,timeout=120)
                need(completed.returncode==0);verify_plain(output,receipt)
                need(claim(connection))
                result["status"]="send_outcome_unknown"
                reply=bot.document({"chat_id":owner,"document":output.as_uri(),"disable_content_type_detection":True,
                    "caption":"A.I. TestFlight 测试版：1 个镜像、148 页完整解密验证通过。"},None,timeout=180)
                need(type(reply) is dict and type(reply.get("message_id")) is int and
                    reply.get("chat",{}).get("id")==owner and reply.get("chat",{}).get("type")=="private" and
                    reply.get("document",{}).get("file_size")==receipt["plaintext_bytes"])
                connection.execute("UPDATE deliveries SET state='confirmed' WHERE request=?",(REQUEST,));connection.commit()
                result.update(status="telegram_file_delivered",delivered=True,bytes=receipt["plaintext_bytes"])
        connection.close()
    except Exception:pass
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0 if result["delivered"] else 2
if __name__=="__main__":raise SystemExit(main())
