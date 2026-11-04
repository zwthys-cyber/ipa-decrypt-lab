"""Owner-only, bounded Telegram -> GitHub -> private IPA test session."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
from telegram_api import APIError, private_message
from telegram_queue import GitHub, QueueError, request_id
from telegram_runtime import local_bot
from telegram_menu import configure as configure_menu
from task_progress import ProgressCard, LABELS
from delivery_scheduler import app_from_run, queued_too_long, retryable, MAX_RUNS

HELP = ("发送美区免费 App Store 链接或数字 App ID，创建下载与解密任务。\n"
        "/status 查看当前任务\n/cancel 取消当前任务\n"
        "/get 任务编号 重新获取已完成文件（保留约一天）\n/id 查看自己的数字 ID\n"
        "当前为 GitHub 限时测试，一次处理一个任务；文件需要自行重签名安装。")

def target_id(text):
    if not isinstance(text,str) or len(text)>1024:
        raise ValueError("invalid target")
    if re.fullmatch(r"[1-9][0-9]{4,19}",text):
        return text
    value = urllib.parse.urlsplit(text)
    found = re.search(r"/id([1-9][0-9]{4,19})/?$",value.path)
    if (value.scheme!="https" or value.hostname!="apps.apple.com" or value.port not in (None,443)
            or value.username or value.password or value.fragment or not found
            or any(c.isspace() for c in text)):
        raise ValueError("invalid target")
    return found.group(1)

def owner_id(value):
    if not re.fullmatch(r"[1-9][0-9]{4,19}",value or ""):
        raise APIError("missing_or_invalid_telegram_owner")
    return int(value)

def opaque_id(token, owner, update, app):
    raw = str(owner)+":"+str(update)+":"+app
    return hmac.new(token.encode(),raw.encode(),hashlib.sha256).hexdigest()[:32]

def event(status, **fields):
    print(json.dumps({"schema":"telegram-session-v1","status":status,**fields}),flush=True)

class Controller:
    def __init__(self, bot, github, owner, crypt, token):
        self.bot,self.github,self.owner,self.crypt,self.token = bot,github,owner,crypt,token
        self.current = None
        self.started = time.time()
        self.handled = set()
        self.submitted = 0
        self.last_submission = 0
        self.last_notice = 0
        self.delivered = set()
        self.cards = {}

    def say(self,text):
        return self.bot.message(self.owner,text)

    def card(self,rid,app=""):
        if rid not in self.cards:
            self.cards[rid]=ProgressCard(self.bot,self.owner,rid,app)
        return self.cards[rid]

    def handle(self, update):
        item = private_message(update)
        if not item or item[0]!=self.owner or item[2]<self.started-60 or item[2]>time.time()+60:
            return
        uid,text,date = item
        update_number = update["update_id"]
        if update_number in self.handled:
            return
        self.handled.add(update_number)
        if len(self.handled)>2000:
            raise QueueError("session_update_limit_reached")
        command = text.split(" ",1)[0].split("@",1)[0]
        if command in ("/start","/help"):
            self.say(HELP)
            return
        if command=="/decrypt":
            self.say("请发送应用的 App Store 链接或数字 App ID。当前支持美区免费应用。")
            return
        if command=="/id":
            self.say("你的 Telegram 数字用户 ID："+str(self.owner))
            return
        if command=="/status":
            if self.current:
                self.card(self.current["rid"],self.current["app"]).update(self.current.get("stage","queued"),force=True)
            else:
                self.say("当前没有正在处理的任务。")
            return
        if command=="/cancel":
            if not self.current:
                self.say("当前没有可取消的任务。")
                return
            rid = self.current["rid"]
            self.github.cancel(rid)
            self.card(rid).update("cancelled",force=True)
            self.current = None
            event("cancellation_requested",request_id=rid)
            return
        if command=="/get":
            parts = text.split()
            if len(parts)!=2 or not re.fullmatch(r"[a-f0-9]{32}",parts[1]):
                self.say("用法：/get 后跟任务编号。")
                return
            self.deliver(parts[1])
            return
        try:
            app = target_id(text)
        except (ValueError,TypeError):
            self.say("请发送完整 App Store 链接或数字 App ID。用 /help 查看指令。")
            return
        if self.current:
            self.say("已有任务处理中，请用 /status 查询，或先 /cancel。")
            return
        if self.submitted>=3:
            self.say("本次测试会话已提交 3 个任务，请重新启动测试会话后继续。")
            return
        if self.submitted and time.monotonic()-self.last_submission<30:
            self.say("请稍候 30 秒再提交。")
            return
        rid = opaque_id(self.token,self.owner,update_number,app)
        # Record before dispatch: an ambiguous network outcome must not cause a duplicate POST.
        self.current = {"rid":rid,"app":app,"state":"dispatch_pending","since":time.monotonic()}
        self.card(rid,app).update("dispatch_pending")
        self.submitted+=1
        self.last_submission=time.monotonic()
        try:
            result = self.github.dispatch(app,rid)
            self.current["state"] = result.get("status","queued")
            self.card(rid,app).update("queued")
            event("job_submitted",request_id=rid,app_id=app)
        except QueueError:
            self.card(rid,app).update("dispatch_pending")
            event("dispatch_outcome_unknown",request_id=rid)

    def deliver(self,rid):
        card=self.card(rid)
        card.update("retrieving")
        try:
            result=self.github.deliver(rid,self.bot,self.owner,self.crypt,progress=card.update)
            event(**result)
            self.delivered.add(rid)
            card.update("done",force=True)
            return True
        except APIError:
            # sendDocument can time out after Telegram accepted it. No automatic resend.
            card.update("unknown",force=True)
            event("delivery_outcome_unknown",request_id=rid)
            self.say("文件发送结果未确认。请先检查聊天；如未收到，可稍后用 /get "+rid+" 手动重试。")
        except QueueError as exc:
            card.update("failed",force=True)
            event(str(exc),request_id=rid)
            self.say("暂时无法交付文件："+str(exc)+"\n任务编号："+rid)
        return False

    def resume(self,rid,app=""):
        run=self.github.find(rid)
        if run and run.get("status")!="completed":
            self.current={"rid":rid,"app":app or app_from_run(run,rid),"state":run.get("status","queued"),
                          "stage":"processing","since":time.monotonic()}
            self.card(rid).update("processing")
            event("job_tracking_resumed",request_id=rid)
        else:
            self.deliver(rid)

    def failover(self,run):
        current=self.current
        rid=current["rid"]
        if type(run.get("id")) is not int:
            return False
        run_id=run["id"]
        if current.get("retry_posted_for")==run_id:
            # A POST may have succeeded even if its response was lost. Lookup only.
            if time.monotonic()-current.get("retry_started",time.monotonic())>180:
                self.card(rid).update("unknown",force=True)
                self.say("备用线路提交结果仍未确认，已停止自动重试。请保留任务编号，稍后可用 /get 取回结果。")
                self.current=None
            else:
                self.card(rid).update("switching")
            return True
        if current.get("retry_posted_for") and current["retry_posted_for"]!=run_id:
            current.pop("retry_posted_for",None)
            current.pop("cancel_for_switch",None)
        app=current.get("app") or app_from_run(run,rid)
        if not app:
            return False
        if run.get("status") not in ("queued","waiting","pending","requested","completed"):
            return False
        if run.get("status")=="completed" and run.get("conclusion") not in ("failure","cancelled"):
            return False
        runs=self.github.runs(rid)
        if not isinstance(runs,list) or len(runs)>=MAX_RUNS:
            return False
        jobs=self.github.jobs(run)
        if retryable(run,jobs,current.get("cancel_for_switch")==run_id):
            # Set before POST; an ambiguous dispatch is never automatically repeated.
            current["retry_posted_for"]=run_id
            current["retry_started"]=time.monotonic()
            self.card(rid).update("switching",force=True)
            try:
                self.github.retry(app,rid,run_id,current.get("cancel_for_switch")==run_id)
                event("runner_failover_dispatched",request_id=rid)
            except QueueError as exc:
                event("runner_failover_unconfirmed",request_id=rid)
                self.say("备用线路提交结果尚未确认，正在核对；不会重复提交。")
            return True
        if queued_too_long(run,jobs) and self.github.queued_confirmed(run,jobs) is True:
            self.card(rid).update("switching")
            if current.get("cancel_attempted_for")!=run_id:
                current["cancel_attempted_for"]=run_id
                try:
                    self.github.cancel(rid)
                    current["cancel_for_switch"]=run_id
                    self.say("排队超过 3 分钟，已请求停止旧线路；确认停止后自动切换备用运行器。")
                except QueueError:
                    self.card(rid).update("capacity_wait",force=True)
                    self.say("运行器容量不足，平台暂未确认旧线路停止；为防重复执行，保留原任务并继续核对。")
            return True
        return False

    def tick(self):
        if not self.current:
            return
        rid=self.current["rid"]
        run=self.github.find(rid)
        if run is None:
            if time.monotonic()-self.current["since"]>300:
                self.say("未能确认 GitHub 任务状态，请稍后用 /get "+rid+" 查询已完成产物。")
                self.current=None
            return
        reported=None
        if run.get("status")!="completed" and type(run.get("id")) is int:
            try:
                reported=self.github.progress(run,rid)
                if not isinstance(reported,str) or reported not in LABELS:
                    reported=None
            except QueueError:
                pass
            if reported=="failed":
                self.current=None
                self.card(rid).update("failed",force=True)
                self.say("下载或校验未完成。任务编号："+rid)
                return
            try:
                if self.github.artifact_ready(run,rid) is True:
                    self.current=None
                    if rid not in self.delivered:
                        self.deliver(rid)
                    return
            except QueueError:
                pass
        if reported is None and self.failover(run):
            return
        state=run.get("status","unknown")
        if state=="completed":
            self.current=None
            if run.get("conclusion")=="success":
                if rid not in self.delivered:
                    self.deliver(rid)
            else:
                self.say("任务未完成："+str(run.get("conclusion","unknown"))+"\n任务编号："+rid)
                self.card(rid).update("failed",force=True)
                event("worker_not_successful",request_id=rid)
        else:
            self.current["state"]=state
            stage="queued" if state in ("queued","waiting","pending","requested") else "processing"
            if reported is not None:
                stage=reported
            self.current["stage"]=stage
            self.card(rid,self.current["app"]).update(stage)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("check","menu","progress-demo","session","deliver"),default="check")
    p.add_argument("--minutes",type=int,default=30)
    p.add_argument("--request-id",default="")
    p.add_argument("--resume-app-id",default="")
    p.add_argument("--server",required=True)
    p.add_argument("--crypt",required=True)
    args=p.parse_args()
    os.umask(0o077)
    try:
        if os.environ.get("GITHUB_ACTIONS")!="true":
            raise APIError("requires_github_actions")
        if not 1<=args.minutes<=45:
            raise APIError("invalid_session_duration")
        if args.resume_app_id and not re.fullmatch(r"[1-9][0-9]{4,19}",args.resume_app_id):
            raise APIError("invalid_resume_app")
        owner=owner_id(os.environ.get("TELEGRAM_OWNER_ID",""))
        github=GitHub(os.environ.get("GH_TOKEN",""))
        crypt=str(Path(args.crypt).resolve())
        with local_bot(args.server) as bot:
            controller=Controller(bot,github,owner,crypt,os.environ["TELEGRAM_BOT_TOKEN"])
            event("local_bot_authenticated")
            event(**configure_menu(bot,owner))
            if args.mode=="progress-demo":
                card=ProgressCard(bot,owner,"0"*32,demo=True)
                for stage in ("queued","downloading","decrypting","verifying","uploading","done"):
                    if not card.update(stage,force=True):
                        raise APIError("progress_demo_edit_unconfirmed")
                    time.sleep(2)
                event("progress_demo_verified",edits=5)
                return 0
            if args.mode=="menu":
                return 0
            if args.mode=="check":
                controller.say("大文件上传通道已连接，管理员身份限制已生效。")
                event("owner_message_confirmed")
                return 0
            if args.mode=="deliver":
                return 0 if controller.deliver(request_id(args.request_id)) else 2
            controller.say("IPA 机器人限时测试已启动，约 "+str(args.minutes)+" 分钟。\n\n"+HELP)
            if args.request_id:
                controller.resume(request_id(args.request_id),args.resume_app_id)
            deadline=time.monotonic()+args.minutes*60
            offset=0
            while time.monotonic()<deadline:
                try:
                    updates=bot.call("getUpdates",{"offset":offset,"limit":20,"timeout":15,
                                                   "allowed_updates":["message"]},timeout=35)
                    if not isinstance(updates,list):
                        raise APIError("telegram_invalid_response")
                    for update in updates:
                        if isinstance(update,dict) and type(update.get("update_id")) is int:
                            offset=max(offset,update["update_id"]+1)
                            controller.handle(update)
                    controller.tick()
                except QueueError as exc:
                    event(str(exc))
                    time.sleep(5)
                except APIError as exc:
                    event(exc.status)
                    if exc.status in ("invalid_bot_token","telegram_polling_conflict"):
                        raise
                    time.sleep(5)
            controller.say("本次限时测试会话已结束。已提交的任务会继续执行，加密文件保留约一天。")
            event("bounded_session_finished")
            return 0
    except APIError as exc:
        event(exc.status)
        return 2
    except QueueError as exc:
        event(str(exc))
        return 2
    except Exception:
        event("telegram_session_failed")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
