"""Persistent owner-only VPS controller. Built and tested on GitHub before deployment."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import time
from telegram_api import APIError
from telegram_queue import GitHub, QueueError
from telegram_runtime import local_bot
from telegram_session import Controller, owner_id, event
from telegram_menu import configure
from persistent_journal import PersistentJournal

KEYS={"TELEGRAM_BOT_TOKEN","TELEGRAM_OWNER_ID","TELEGRAM_API_ID",
      "TELEGRAM_API_HASH","DELIVERY_AGE_IDENTITY","GH_TOKEN"}
HELP=("发送美区免费 App Store 链接或数字 App ID创建任务。\n"
      "/status 查看进度\n/get 任务编号 取回文件\n/cancel 取消当前任务\n/id 查看身份\n"
      "当前仅向管理员开放；尚未开放付费服务。")

def load_credentials(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_size>32768:
        raise QueueError("insecure_credentials_file")
    values=json.loads(path.read_text())
    if (not isinstance(values,dict) or set(values)!=KEYS
            or not all(isinstance(v,str) and v and "\n" not in v for v in values.values())):
        raise QueueError("invalid_service_credentials")
    return values

def heartbeat(path, state, current=None):
    payload={"schema":"ipa-service-health-v1","state":state,"at":int(time.time()),
             "task_active":current is not None}
    temp=path.with_suffix(".next")
    temp.write_text(json.dumps(payload))
    os.replace(temp,path)

class ServerController(Controller):
    def handle(self,update):
        self.submitted=self.journal.daily_submissions()
        item=update.get("message",{}) if isinstance(update,dict) else {}
        text=item.get("text","")
        # Retain the base class's owner, private-chat and timestamp validation.
        if text.split(" ",1)[0].split("@",1)[0] in ("/start","/help"):
            from telegram_api import private_message
            parsed=private_message(update)
            if parsed and parsed[0]==self.owner and self.started-60<=parsed[2]<=time.time()+60:
                self.say(HELP)
            return
        super().handle(update)

    def deliver(self,rid):
        scratch=Path(os.environ["TMPDIR"])
        if shutil.disk_usage(scratch).free<6*1024**3:
            self.say("可用磁盘空间不足，已暂停文件交付；请保留任务编号。")
            return False
        return super().deliver(rid)

def process_update(controller,journal,update):
    if not isinstance(update,dict) or type(update.get("update_id")) is not int or update["update_id"]<0:
        return
    uid=update["update_id"]
    if uid<journal.offset():
        return
    if journal.claim_update(uid):
        try:
            controller.handle(update)
        except QueueError as exc:
            event(str(exc))
        except APIError as exc:
            event(exc.status)
    # Claim precedes effects; after a crash, an uncertain /get is never replayed.
    journal.finish_update(uid)

def backup(journal,root):
    target=root/"recovery-backup.next"
    with sqlite3.connect(target) as destination:
        journal.db.backup(destination)
    os.chmod(target,0o600)
    os.replace(target,root/"recovery-backup.sqlite3")

def main():
    os.umask(0o077)
    os.environ["LAB_RUNTIME"]="vps"
    root=Path(os.environ.get("IPAZAKE_STATE","/var/lib/ipazake"))
    root.mkdir(parents=True,mode=0o700,exist_ok=True)
    lock=(root/"controller.lock").open("a")
    journal=None
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        credentials=Path(os.environ["CREDENTIALS_DIRECTORY"])/"bot.json"
        os.environ.update(load_credentials(credentials))
        owner=owner_id(os.environ["TELEGRAM_OWNER_ID"])
        cap=int(os.environ.get("IPAZAKE_DAILY_TASK_LIMIT","20"))
        if not 1<=cap<=1000:
            raise QueueError("invalid_daily_task_limit")
        scratch=root/"transfers"
        scratch.mkdir(mode=0o700,exist_ok=True)
        # No shared upload directory: these are exclusively this service's temporary exports.
        for child in scratch.iterdir():
            if child.name.startswith("tg-private-delivery-") and child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
        os.environ["TMPDIR"]=str(scratch)
        import tempfile
        tempfile.tempdir=str(scratch)
        github=GitHub(os.environ["GH_TOKEN"])
        workflow=github.call("/actions/workflows/private-delivery.yml")
        if not isinstance(workflow,dict) or workflow.get("state")!="active":
            raise QueueError("worker_workflow_unavailable")
        journal=PersistentJournal(root/"state.sqlite3",owner)
        stop=False
        def stopping(signum,frame):
            nonlocal stop
            stop=True
        signal.signal(signal.SIGTERM,stopping)
        signal.signal(signal.SIGINT,stopping)
        base=Path(__file__).resolve().parents[1]
        heartbeat(root/"health.json","starting")
        with local_bot(base/"bin/telegram-bot-api",state_directory=root/"telegram") as bot:
            controller=ServerController(bot,github,owner,str(base/"bin/delivery-crypt"),
                os.environ["TELEGRAM_BOT_TOKEN"],journal=journal,submission_limit=cap)
            # Accept queued owner messages from at most the last day; SQLite prevents replay.
            controller.started=time.time()-86400
            event(**configure(bot,owner))
            controller.recover()
            controller.say("机器人常驻服务已启动，任务记录已恢复。\n\n"+HELP)
            heartbeat(root/"health.json","ready",controller.current)
            event("persistent_service_ready")
            last_backup=0
            while not stop:
                if getattr(bot,"process",None) is not None and bot.process.poll() is not None:
                    raise APIError("local_bot_server_exited")
                try:
                    updates=bot.call("getUpdates",{"offset":journal.offset(),"limit":20,"timeout":15,
                        "allowed_updates":["message"]},timeout=35)
                    if not isinstance(updates,list):
                        raise APIError("telegram_invalid_response")
                    for update in updates:
                        if stop:
                            break
                        process_update(controller,journal,update)
                    controller.tick()
                    heartbeat(root/"health.json","ready",controller.current)
                    if time.monotonic()-last_backup>3600:
                        backup(journal,root)
                        last_backup=time.monotonic()
                except QueueError as exc:
                    event(str(exc))
                    heartbeat(root/"health.json","github_unavailable",controller.current)
                    time.sleep(5)
                except APIError as exc:
                    event(exc.status)
                    heartbeat(root/"health.json","telegram_unavailable",controller.current)
                    if exc.status in ("invalid_bot_token","telegram_polling_conflict"):
                        raise
                    time.sleep(5)
            backup(journal,root)
            heartbeat(root/"health.json","stopped",controller.current)
        return 0
    except BlockingIOError:
        event("controller_already_running")
        return 2
    except (APIError,QueueError) as exc:
        event(str(exc))
        heartbeat(root/"health.json","failed")
        return 2
    except Exception:
        event("persistent_service_failed")
        heartbeat(root/"health.json","failed")
        return 2
    finally:
        if journal is not None:
            journal.close()
        lock.close()

if __name__=="__main__":
    raise SystemExit(main())
