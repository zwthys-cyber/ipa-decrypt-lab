"""Private allowlist, per-user ledgers and admission for one persistent poller."""
import json
import time
from persistent_journal import PersistentJournal
from telegram_api import APIError, private_message
from telegram_controller import event, owner_id
from telegram_menu import configure
from telegram_queue import QueueError, require, request_id
from version_catalog import CatalogAPI

MAX_GUESTS=50
MAX_IDENTITIES=200

class AccessControl:
    def __init__(self,journal,admin,limit):
        self.journal,self.db,self.scope=journal,journal.db,journal.scope
        self.admin,self.limit=admin,limit
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS tenant_access(
            namespace TEXT NOT NULL, uid INTEGER NOT NULL, enabled INTEGER NOT NULL,
            daily_limit INTEGER NOT NULL, at INTEGER NOT NULL, PRIMARY KEY(namespace,uid));
          CREATE TABLE IF NOT EXISTS retired_work(
            namespace TEXT NOT NULL, rid TEXT NOT NULL, kind TEXT NOT NULL,
            app TEXT NOT NULL, at INTEGER NOT NULL, PRIMARY KEY(namespace,rid));
        """)

    def profile(self,uid):
        if uid==self.admin:return {"uid":uid,"daily_limit":self.limit}
        row=self.db.execute("SELECT daily_limit FROM tenant_access WHERE namespace=? AND uid=? AND enabled=1",(self.scope,uid)).fetchone()
        return {"uid":uid,"daily_limit":row[0]} if row else None

    def profiles(self):
        return [{"uid":row[0],"daily_limit":row[1]} for row in self.db.execute(
            "SELECT uid,daily_limit FROM tenant_access WHERE namespace=? AND enabled=1 ORDER BY uid",(self.scope,))]

    def grant(self,uid,limit):
        require(type(uid) is int and 0<uid<2**63 and uid!=self.admin,"invalid_guest_identity")
        require(type(limit) is int and 1<=limit<=self.limit,"invalid_guest_limit")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            count=self.db.execute("SELECT count(*) FROM tenant_access WHERE namespace=? AND enabled=1",(self.scope,)).fetchone()[0]
            total=self.db.execute("SELECT count(*) FROM tenant_access WHERE namespace=?",(self.scope,)).fetchone()[0]
            exists=self.db.execute("SELECT enabled FROM tenant_access WHERE namespace=? AND uid=?",(self.scope,uid)).fetchone()
            require((exists and exists[0]) or count<MAX_GUESTS,"allowlist_full")
            require(exists is not None or total<MAX_IDENTITIES,"identity_history_full")
            self.db.execute("""INSERT INTO tenant_access(namespace,uid,enabled,daily_limit,at) VALUES(?,?,1,?,?)
              ON CONFLICT(namespace,uid) DO UPDATE SET enabled=1,daily_limit=excluded.daily_limit,at=excluded.at""",
              (self.scope,uid,limit,int(time.time())))

    def revoke(self,uid,work):
        require(uid!=self.admin and self.profile(uid) is not None,"invalid_guest_identity")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            for item in work:
                request_id(item["rid"])
                require(item["kind"] in ("export","catalog"),"invalid_retirement")
                self.db.execute("INSERT OR IGNORE INTO retired_work(namespace,rid,kind,app,at) VALUES(?,?,?,?,?)",
                    (self.scope,item["rid"],item["kind"],item["app"],int(time.time())))
            self.db.execute("UPDATE tenant_access SET enabled=0,at=? WHERE namespace=? AND uid=?",(int(time.time()),self.scope,uid))

    def retired(self):
        return [dict(rid=r[0],kind=r[1],app=r[2]) for r in self.db.execute(
            "SELECT rid,kind,app FROM retired_work WHERE namespace=? ORDER BY at",(self.scope,))]

    def release(self,rid):
        with self.db:self.db.execute("DELETE FROM retired_work WHERE namespace=? AND rid=?",(self.scope,rid))

    def submissions(self):
        start=int(time.time())//86400*86400
        return self.db.execute("SELECT count(*) FROM tasks WHERE created>=? AND created<?",(start,start+86400)).fetchone()[0]

    def queries(self):
        now=int(time.time());count=0
        for row in self.db.execute("SELECT value FROM metadata WHERE name='version_browser'"):
            try:
                value=json.loads(row[0]);stamps=value.get("queries",[])
                require(isinstance(stamps,list) and all(type(s) is int for s in stamps),"invalid_query_budget")
                count+=sum(now-86400<s<=now for s in stamps)
            except (ValueError,AttributeError,TypeError):
                raise QueueError("invalid_query_budget") from None
        return count

class ScopedGitHub:
    """Reject unowned exports before any remote lookup, cancellation or delivery."""
    def __init__(self,api,journal,owner,allowed):
        self.api,self.journal,self.owner,self.allowed=api,journal,owner,allowed
    def __getattr__(self,name):return getattr(self.api,name)
    def own(self,rid,revoking=False):
        request_id(rid)
        require(rid in self.journal.records,"task_not_owned")
        require(revoking or self.allowed(),"user_not_authorized")
    def find(self,rid):self.own(rid);return self.api.find(rid)
    def runs(self,rid):self.own(rid);return self.api.runs(rid)
    def dispatch(self,app,rid,**kwargs):self.own(rid);return self.api.dispatch(app,rid,**kwargs)
    def retry(self,app,rid,*args,**kwargs):self.own(rid);return self.api.retry(app,rid,*args,**kwargs)
    def cancel(self,rid):self.own(rid,revoking=True);return self.api.cancel(rid)
    def deliver(self,rid,bot,owner,crypt,**kwargs):
        self.own(rid);require(owner==self.owner,"delivery_recipient_mismatch")
        return self.api.deliver(rid,bot,owner,crypt,**kwargs)

def actor(update):
    if not isinstance(update,dict) or type(update.get("update_id")) is not int:return None
    item=private_message(update)
    if item:
        return (item[0],item[1]) if time.time()-86400<=item[2]<=time.time()+60 else None
    q=update.get("callback_query")
    if not isinstance(q,dict):return None
    sender,message=q.get("from"),q.get("message")
    if not isinstance(sender,dict) or not isinstance(message,dict):return None
    chat,author=message.get("chat"),message.get("from")
    uid=sender.get("id")
    if (type(uid) is not int or uid<=0 or sender.get("is_bot") is not False
            or not isinstance(chat,dict) or chat.get("type")!="private" or chat.get("id")!=uid
            or not isinstance(author,dict) or author.get("is_bot") is not True
            or type(message.get("message_id")) is not int):return None
    return uid,None

class MultiUserService:
    def __init__(self,bot,github,admin,crypt,token,journal,limit,controller_factory):
        self.bot,self.github,self.admin,self.crypt,self.token=bot,github,admin,crypt,token
        self.journal,self.limit,self.factory=journal,limit,controller_factory
        self.access=AccessControl(journal,admin,limit)
        self.controllers={};self.configured={admin};self.denied={}
        self.sync()
        self.tenant(admin)

    def sync(self):
        self.enabled=frozenset([self.admin]+[p["uid"] for p in self.access.profiles()])
        self.retired=self.access.retired()

    def tenant(self,uid):
        require(uid in self.enabled,"user_not_authorized")
        profile=self.access.profile(uid);require(profile is not None,"user_not_authorized")
        if uid not in self.controllers:
            ledger=self.journal if uid==self.admin else PersistentJournal(self.journal.path,uid)
            allowed=lambda:uid in self.enabled
            api=ScopedGitHub(self.github,ledger,uid,allowed)
            controller=self.factory(self.bot,api,uid,self.crypt,self.token,journal=ledger,
                submission_limit=profile["daily_limit"],admission=lambda kind:self.admit(uid,kind),
                authorization=allowed,strict_ownership=True)
            controller.started=time.time()-86400
            self.controllers[uid]=controller
        self.controllers[uid].submission_limit=profile["daily_limit"]
        return self.controllers[uid]

    @property
    def current(self):
        for c in self.controllers.copy().values():
            if c.current is not None:return c.current
            if c.browser.state.get("pending"):return {"catalog":True}
        return {"draining":True} if self.retired else None

    def admit(self,uid,kind):
        require(kind in ("export","catalog"),"invalid_admission")
        text=None
        if uid not in self.enabled:text="授权已失效，请联系管理员。"
        elif self.retired:text="后台正在确认取消结果，请稍后再提交。"
        elif any(other!=uid and (c.current is not None or c.browser.state.get("pending")) for other,c in self.controllers.copy().items()):
            text="服务正在处理其他任务，请稍后再试；你已有的文件和缓存仍可查看。"
        elif kind=="export" and self.access.submissions()>=self.limit:text="服务今日总提交额度已用完，请明天再试。"
        elif kind=="catalog" and self.access.queries()>=20:text="服务最近 24 小时的版本查询额度已用完，请稍后再试。"
        if text:self.bot.message(uid,text);return False
        return True

    def handle(self,update):
        principal=actor(update)
        if principal is None:return
        uid,text=principal
        command=text.split(maxsplit=1)[0].split("@",1)[0] if text else ""
        if uid not in self.enabled:
            now=time.monotonic()
            if command in ("/start","/id") and now-self.denied.get(uid,-float("inf"))>=60:
                if len(self.denied)>=128:self.denied.pop(next(iter(self.denied)))
                self.denied[uid]=now
                self.bot.message(uid,"尚未获得使用授权，请将你的数字 ID 提供给管理员："+str(uid))
            return
        if command in ("/allow","/deny","/users"):
            if uid!=self.admin:self.bot.message(uid,"该命令仅管理员可用。");return
            self.manage(command,text.split());return
        controller=self.tenant(uid)
        if uid not in self.configured:
            try:configure(self.bot,uid);self.configured.add(uid)
            except APIError:event("tenant_menu_unavailable")
        controller.handle(update)

    def manage(self,command,parts):
        if command=="/users" and len(parts)==1:
            profiles=self.access.profiles()
            lines=["管理员："+str(self.admin),"服务每日下载总额度："+str(self.limit),
                   "白名单用户："+str(len(profiles))+"/"+str(MAX_GUESTS)]
            lines.extend(str(p["uid"])+" · 每日 "+str(p["daily_limit"])+" 次" for p in profiles)
            lines.extend(["添加或修改：/allow 用户ID [每日额度]","移除：/deny 用户ID","未指定时每人每日 "+str(min(3,self.limit))+" 次。"])
            self.bot.message(self.admin,"\n".join(lines));return
        try:
            require((command=="/allow" and len(parts) in (2,3)) or (command=="/deny" and len(parts)==2),"invalid_access_command")
            uid=owner_id(parts[1]);require(uid!=self.admin and uid<2**63,"invalid_guest_identity")
            if command=="/allow":
                limit=int(parts[2]) if len(parts)==3 else min(3,self.limit)
                self.access.grant(uid,limit);self.sync();self.tenant(uid)
                self.bot.message(self.admin,"已授权 "+str(uid)+"，每日最多 "+str(limit)+" 次；仍受服务总额度限制。")
            else:
                self.revoke(uid)
                self.bot.message(self.admin,"已移除授权并停止自动交付。后台任务如仍在取消中，会等待平台确认后再接新任务。")
        except (ValueError,APIError,QueueError):
            self.bot.message(self.admin,"操作未完成。用法：/allow 用户ID [每日额度]；/deny 用户ID；/users。管理员身份固定，额度须为 1 到 "+str(self.limit)+"。")

    def revoke(self,uid):
        require(uid!=self.admin and uid in self.enabled,"invalid_guest_identity")
        c=self.tenant(uid);work=[]
        for row in c.journal.pending():work.append(dict(rid=row["rid"],app=row["app"],kind="export"))
        pending=c.browser.state.get("pending")
        if pending:work.append(dict(rid=pending["rid"],app=pending["app"],kind="catalog"))
        self.access.revoke(uid,work);self.sync();self.controllers.pop(uid,None);self.configured.discard(uid)
        try:
            for row in work:
                if row["kind"]=="export":c.journal.write(row["rid"],"cancelled")
            if pending:c.browser.state["pending"]=None;c.browser.save()
            c.current=None
            for row in work:
                try:
                    if row["kind"]=="export":self.github.cancel(row["rid"])
                    else:
                        run=CatalogAPI(self.github).find(row["rid"],row["app"])
                        if run and run.get("status")!="completed":self.github.call("/actions/runs/"+str(run["id"])+"/cancel",{},"POST")
                except (QueueError,APIError):event("revoked_work_cancellation_unconfirmed")
        finally:
            c.journal.close()

    def recover(self):
        for uid in sorted(self.enabled):self.tenant(uid).recover()

    def tick(self):
        for item in tuple(self.retired):
            try:
                run=(self.github.find(item["rid"]) if item["kind"]=="export" else CatalogAPI(self.github).find(item["rid"],item["app"]))
                if run and run.get("status")=="completed":self.access.release(item["rid"])
            except QueueError:event("retired_work_status_unavailable")
        self.retired=self.access.retired()
        for uid,c in self.controllers.copy().items():
            if uid not in self.enabled:continue
            try:c.tick()
            except QueueError:event("tenant_task_poll_unavailable")
            except APIError as exc:
                if exc.status in ("invalid_bot_token","telegram_polling_conflict"):raise
                event("tenant_telegram_unavailable")

    def refresh_progress(self):
        for uid,c in self.controllers.copy().items():
            if uid in self.enabled:c.refresh_progress()

    def close(self):
        for uid,c in self.controllers.copy().items():
            if uid!=self.admin:c.journal.close()
        self.controllers={}
