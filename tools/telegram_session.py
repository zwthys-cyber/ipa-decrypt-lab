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

    def say(self,text):
        return self.bot.message(self.owner,text)

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
            self.say("当前任务："+self.current["rid"]+"\n状态："+self.current["state"] if self.current else "当前没有正在处理的任务。")
            return
        if command=="/cancel":
            if not self.current:
                self.say("当前没有可取消的任务。")
                return
            rid = self.current["rid"]
            self.github.cancel(rid)
            self.current = None
            self.say("已请求取消任务："+rid)
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
        self.submitted+=1
        self.last_submission=time.monotonic()
        try:
            result = self.github.dispatch(app,rid)
            self.current["state"] = result.get("status","queued")
            self.say("任务已提交。\nApp ID："+app+"\n任务编号："+rid+"\n用 /status 查询进度。")
            event("job_submitted",request_id=rid,app_id=app)
        except QueueError:
            self.say("提交结果尚未确认，正在查询，请勿重复提交。\n任务编号："+rid)
            event("dispatch_outcome_unknown",request_id=rid)

    def deliver(self,rid):
        self.say("正在私有校验并上传文件，请稍候。\n任务编号："+rid)
        try:
            result=self.github.deliver(rid,self.bot,self.owner,self.crypt)
            event(**result)
            self.delivered.add(rid)
            return True
        except APIError:
            # sendDocument can time out after Telegram accepted it. No automatic resend.
            event("delivery_outcome_unknown",request_id=rid)
            self.say("文件发送结果未确认。请先检查聊天；如未收到，可稍后用 /get "+rid+" 手动重试。")
        except QueueError as exc:
            event(str(exc),request_id=rid)
            self.say("暂时无法交付文件："+str(exc)+"\n任务编号："+rid)
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
        state=run.get("status","unknown")
        if state=="completed":
            self.current=None
            if run.get("conclusion")=="success":
                if rid not in self.delivered:
                    self.deliver(rid)
            else:
                self.say("任务未完成："+str(run.get("conclusion","unknown"))+"\n任务编号："+rid)
                event("worker_not_successful",request_id=rid)
        elif state!=self.current["state"]:
            self.current["state"]=state
            self.say("任务状态："+state+"\n任务编号："+rid)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("check","menu","session","deliver"),default="check")
    p.add_argument("--minutes",type=int,default=30)
    p.add_argument("--request-id",default="")
    p.add_argument("--server",required=True)
    p.add_argument("--crypt",required=True)
    args=p.parse_args()
    os.umask(0o077)
    try:
        if os.environ.get("GITHUB_ACTIONS")!="true":
            raise APIError("requires_github_actions")
        if not 1<=args.minutes<=45:
            raise APIError("invalid_session_duration")
        owner=owner_id(os.environ.get("TELEGRAM_OWNER_ID",""))
        github=GitHub(os.environ.get("GH_TOKEN",""))
        crypt=str(Path(args.crypt).resolve())
        with local_bot(args.server) as bot:
            controller=Controller(bot,github,owner,crypt,os.environ["TELEGRAM_BOT_TOKEN"])
            event("local_bot_authenticated")
            event(**configure_menu(bot,owner))
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
                controller.deliver(request_id(args.request_id))
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
