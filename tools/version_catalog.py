"""Fixed GitHub metadata query and persistent, owner-only version buttons."""
import hashlib
import hmac
import json
from pathlib import Path
import re
import tempfile
import time
import zipfile
from telegram_api import APIError
from telegram_queue import QueueError, require, request_id, sha256
from version_request import selector, external_id

WORKFLOW="version-catalog.yml"
TTL=21600  # Button lifetime remains six hours.
FRESH_TTL=86400
STALE_TTL=7*86400
MAX_APPS=50
MAX_ROWS=200
PAGE=10

def validate(payload,rid,app,run_id,commit,before=""):
    require(isinstance(payload,dict) and payload.get("schema") in ("ipa-version-catalog-v1","ipa-version-catalog-v2")
            and payload.get("request_id")==rid and payload.get("app_id")==app
            and payload.get("run_id")==str(run_id) and payload.get("source_commit")==commit,
            "invalid_version_catalog")
    paged=payload["schema"]=="ipa-version-catalog-v2"
    rows=payload.get("rows")
    require(isinstance(rows,list) and (0 if paged else 1)<=len(rows)<=(10 if paged else 60)
            and type(payload.get("total")) is int and len(rows)<=payload["total"]<=10000,
            "invalid_version_catalog")
    seen=set()
    for row in rows:
        require(isinstance(row,dict) and set(row)=={"id","version","date"},"invalid_version_catalog")
        try:
            require(external_id(row["id"]) and bool(row["version"]) and selector(row["version"])==row["version"]
                    and not external_id(row["version"]) and row["id"] not in seen,
                    "invalid_version_catalog")
        except (ValueError,TypeError):
            raise QueueError("invalid_version_catalog") from None
        require(isinstance(row["date"],str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",row["date"]),
                "invalid_version_catalog")
        seen.add(row["id"])
    result={"rows":rows,"total":payload["total"]}
    if paged:
        cursor=payload.get("next_before")
        require(payload.get("before")==before and isinstance(cursor,str)
                and (not cursor or external_id(cursor)) and (not before or external_id(before)),
                "invalid_catalog_cursor")
        numbers=[int(row["id"]) for row in rows]
        require(numbers==sorted(numbers,reverse=True)
                and (not before or all(n<int(before) for n in numbers))
                and (not cursor or not before or int(cursor)<int(before))
                and (not cursor or all(n>=int(cursor) for n in numbers)),
                "invalid_catalog_cursor")
        require(bool(rows) or bool(before) or bool(cursor),"empty_version_catalog")
        result["next_before"]=cursor
    else:
        require(not before,"legacy_catalog_cursor")
    return result

class CatalogAPI:
    def __init__(self,github):
        self.github=github

    def find(self,rid,app):
        request_id(rid)
        require(re.fullmatch(r"[1-9][0-9]{4,19}",app or ""),"invalid_app_id")
        for page in (1,2,3):
            data=self.github.call("/actions/workflows/"+WORKFLOW+"/runs?event=workflow_dispatch&per_page=100&page="+str(page))
            require(isinstance(data,dict) and isinstance(data.get("workflow_runs"),list),"invalid_catalog_runs")
            for run in data["workflow_runs"]:
                if (run.get("display_title")=="versions-"+rid+"-app"+app
                        and run.get("event")=="workflow_dispatch" and run.get("head_branch")=="main"
                        and run.get("path")==".github/workflows/"+WORKFLOW):
                    return run
            if len(data["workflow_runs"])<100:
                break
        return None

    def dispatch(self,rid,app,before=""):
        if self.find(rid,app):
            return
        self.github.call("/actions/workflows/"+WORKFLOW+"/dispatches",
                         {"ref":"main","inputs":{"app_id":app,"request_id":rid,"runner":"macos-26-intel","paged":"true","before":before}},"POST")

    def result(self,run,rid,app,before=""):
        require(run.get("status")=="completed" and run.get("conclusion")=="success","catalog_not_ready")
        run_id=run["id"]
        data=self.github.call("/actions/runs/"+str(run_id)+"/artifacts?per_page=100")
        found=[a for a in data.get("artifacts",[]) if a.get("name")=="versions-"+rid and a.get("expired") is False]
        require(len(found)==1 and type(found[0].get("size_in_bytes")) is int
                and 0<found[0]["size_in_bytes"]<=131072,"catalog_artifact_unavailable")
        artifact=found[0]
        require(isinstance(artifact.get("digest"),str)
                and re.fullmatch(r"sha256:[a-f0-9]{64}",artifact["digest"]),"catalog_digest_missing")
        with tempfile.TemporaryDirectory(prefix="version-catalog-") as directory:
            path=Path(directory)/"metadata.zip"
            self.github.archive(artifact["id"],path,max_bytes=131072)
            require(path.stat().st_size<=131072 and sha256(path)==artifact["digest"][7:],"catalog_digest_mismatch")
            with zipfile.ZipFile(path) as archive:
                require(archive.namelist()==["versions.json"] and archive.getinfo("versions.json").file_size<=32768,
                        "invalid_catalog_archive")
                payload=json.loads(archive.read("versions.json"))
        return validate(payload,rid,app,run_id,run["head_sha"],before)

class VersionBrowser:
    def __init__(self,controller):
        self.c=controller
        self.api=CatalogAPI(controller.github)
        self.state={"cache":{},"pending":None,"view":None,"queries":[]}
        if controller.journal is not None and hasattr(controller.journal,"browser_load"):
            saved=controller.journal.browser_load()
            if isinstance(saved,dict):
                self.state=saved
        self.last_poll=0

    def save(self):
        if self.c.journal is not None and hasattr(self.c.journal,"browser_save"):
            self.c.journal.browser_save(self.state)

    def prune(self):
        now=int(time.time())
        cache=self.state.setdefault("cache",{})
        for app in list(cache):
            entry=cache[app]
            if not 0<=now-entry.get("at",0)<STALE_TTL:
                del cache[app]
        while len(cache)>MAX_APPS:
            del cache[min(cache,key=lambda key:cache[key].get("used_at",cache[key]["at"]))]

    def begin(self,app,update_id):
        now=int(time.time())
        self.prune()
        entry=self.state.get("cache",{}).get(app)
        rid=self.query_id(app,update_id,"view")
        if entry:
            entry["used_at"]=now
            self.open(app,rid,entry)
            if now-entry["at"]<FRESH_TTL:
                return
            if self.c.current or self.state.get("pending"):
                self.c.say("已显示缓存列表，空闲时可点击“刷新列表”更新。")
                return
            self.start(app,update_id,background=True)
            return
        self.start(app,update_id)

    def query_id(self,app,update_id,suffix=""):
        text="versions:"+str(self.c.owner)+":"+str(update_id)+":"+app+":"+suffix
        return hmac.new(self.c.token.encode(),text.encode(),hashlib.sha256).hexdigest()[:32]

    def start(self,app,update_id,before="",background=False):
        now=int(time.time())
        if self.c.current:
            self.c.say("已有下载任务处理中；缓存列表仍可查看，新查询请稍后再试。")
            return
        if self.state.get("pending"):
            self.c.say("历史版本正在查询，请稍候；已有列表仍可翻页。")
            return
        queries=[stamp for stamp in self.state.get("queries",[]) if now-86400<stamp<=now]
        interval=5 if before else 60
        if len(queries)>=20 or (queries and now-queries[-1]<interval):
            self.c.say("版本查询较频繁，请稍后再试。缓存列表可直接翻页。")
            return
        self.c.github.preflight_app(app,historical=True)
        rid=self.query_id(app,update_id,before or "first")
        view=self.state.get("view")
        self.state["queries"]=queries+[now]
        self.state["pending"]={"rid":rid,"app":app,"at":now,"before":before,
            "background":background,"view_rid":view["rid"] if before and view else ""}
        self.save()
        self.c.say("已显示缓存，正在后台刷新最近版本。" if background else
                   "正在加载更早版本…" if before else "正在查询最近 10 个历史版本，完成后显示选择列表。")
        try:
            self.api.dispatch(rid,app,before=before)
        except QueueError:
            self.c.say("查询提交结果尚未确认，正在核对，不会重复提交。")

    def cancel(self):
        pending=self.state.get("pending")
        if not pending:
            return
        self.state["pending"]=None
        self.save()
        run=self.api.find(pending["rid"],pending["app"])
        if run and run.get("status")!="completed":
            self.c.github.call("/actions/runs/"+str(run["id"])+"/cancel",{},"POST")
        self.c.say("已停止跟踪并请求取消历史版本查询。")

    def tick(self):
        try:
            self._tick()
        except (QueueError,APIError):
            raise
        except Exception:
            self.state["pending"]=None
            self.save()
            self.c.say("历史版本结果无法读取，请重新使用 /versions。")

    def _tick(self):
        pending=self.state.get("pending")
        if not pending or time.monotonic()-self.last_poll<15:
            return
        self.last_poll=time.monotonic()
        if time.time()-pending["at"]>3600:
            self.state["pending"]=None
            self.save()
            self.c.say("历史版本查询等待超时，请稍后重新使用 /versions。")
            return
        run=self.api.find(pending["rid"],pending["app"])
        if run is None or run.get("status")!="completed":
            if time.time()-pending["at"]>3600:
                self.state["pending"]=None
                self.save()
                self.c.say("历史版本查询等待超时，请稍后重新使用 /versions。")
            return
        if run.get("conclusion")!="success":
            self.state["pending"]=None
            self.save()
            self.c.say("历史版本查询未完成，请稍后重试；仍可使用 /version AppID 版本号。")
            return
        try:
            entry=self.api.result(run,pending["rid"],pending["app"],before=pending.get("before",""))
        except QueueError:
            pending["result_failures"]=pending.get("result_failures",0)+1
            if pending["result_failures"]>=3:
                self.state["pending"]=None
                self.c.say("历史版本结果暂时无法取回，请重新使用 /versions。")
            self.save()
            return
        now=int(time.time())
        cache=self.state.setdefault("cache",{})
        before=pending.get("before","")
        old=cache.get(pending["app"])
        view=self.state.get("view")
        if before:
            # Append only to the exact cursor that was durably dispatched.
            if not old or old.get("next_before")!=before:
                self.state["pending"]=None
                self.save()
                self.c.say("列表已更新，请重新打开 /versions。")
                return
            known={row["id"] for row in old["rows"]}
            merged=old["rows"]+[row for row in entry["rows"] if row["id"] not in known]
            entry=dict(entry,rows=merged[:MAX_ROWS],at=old["at"],used_at=now,
                       total=max(old["total"],entry["total"],len(merged)))
            if len(entry["rows"])>=MAX_ROWS:
                entry["next_before"]=""
        else:
            entry.update(at=now,used_at=now)
        cache[pending["app"]]=entry
        self.prune()
        self.state["pending"]=None
        self.save()
        if (before and view and view["rid"]==pending.get("view_rid") and view["app"]==pending["app"]):
            old_count=len(view["rows"])
            view.update(rows=entry["rows"],total=entry["total"],next_before=entry.get("next_before",""))
            self.save()
            self.render(min(old_count//PAGE,max(0,(len(view["rows"])-1)//PAGE)))
        elif not before and not pending.get("suppress_open"):
            self.open(pending["app"],pending["rid"],entry)

    def open(self,app,rid,entry):
        self.state["view"]={"rid":rid,"app":app,"at":int(time.time()),"rows":entry["rows"],
                            "total":entry["total"],"message_id":0,"used":[],
                            "next_before":entry.get("next_before",""),"cache_at":entry["at"]}
        self.save()
        self.render(0,False)

    def render(self,page,edit=True):
        view=self.state["view"]
        if view.get("closed"):
            return
        rows=view["rows"]
        pages=max(1,(len(rows)+PAGE-1)//PAGE)
        if not 0<=page<pages:
            return
        prefix="vc:"+view["rid"]+":"
        keyboard=[]
        chunk=[]
        text="App ID："+view["app"]+" · 请选择版本\n第 "+str(page+1)+"/"+str(pages)+" 页"
        text+="\n点击版本即提交下载解密；实际可下载性以 Apple 响应为准。"
        if time.time()-view.get("cache_at",view["at"])>=FRESH_TTL:
            text+="\n当前显示旧缓存，可先查看；刷新后会提供新列表。"
        if len(rows)<view["total"]:
            text+="\n已加载 "+str(len(rows))+" 个版本，非完整历史。"
        if not rows:
            text+="\n本批没有可读取的版本，可继续加载更早版本。"
        if len(rows)>=MAX_ROWS and len(rows)<view["total"]:
            text+="\n已达单应用 200 个版本的展示上限。"
        for index in range(page*PAGE,min((page+1)*PAGE,len(rows))):
            row=rows[index]
            chunk.append({"text":row["version"],"callback_data":prefix+"v:"+str(index)})
            if len(chunk)==2:
                keyboard.append(chunk);chunk=[]
        if chunk:
            keyboard.append(chunk)
        navigation=[]
        if page>0:
            navigation.append({"text":"上一页","callback_data":prefix+"p:"+str(page-1)})
        if page+1<pages:
            navigation.append({"text":"下一页","callback_data":prefix+"p:"+str(page+1)})
        if navigation:
            keyboard.append(navigation)
        if view.get("next_before") and page==pages-1 and len(rows)<MAX_ROWS:
            keyboard.append([{"text":"加载更早版本","callback_data":prefix+"m:0"}])
        keyboard.append([{"text":"刷新列表","callback_data":prefix+"r:0"}])
        payload={"chat_id":self.c.owner,"text":text,"reply_markup":{"inline_keyboard":keyboard}}
        if edit:
            payload["message_id"]=view["message_id"]
        reply=self.c.bot.call("editMessageText" if edit else "sendMessage",payload)
        require(isinstance(reply,dict) and type(reply.get("message_id")) is int
                and reply.get("chat",{}).get("id")==self.c.owner,"catalog_message_unconfirmed")
        view["message_id"]=reply["message_id"]
        self.save()

    def callback(self,update):
        query=update.get("callback_query",{})
        if not isinstance(query,dict):
            return None
        sender=query.get("from",{})
        message=query.get("message",{})
        if not isinstance(sender,dict) or not isinstance(message,dict):
            return None
        chat=message.get("chat",{})
        if (sender.get("id")!=self.c.owner or sender.get("is_bot") is not False
                or not isinstance(chat,dict) or chat.get("type")!="private" or chat.get("id")!=self.c.owner):
            return None
        query_id=query.get("id")
        if not isinstance(query_id,str) or not 0<len(query_id)<=128:
            return None
        def answer(text):
            try: self.c.bot.call("answerCallbackQuery",{"callback_query_id":query_id,"text":text})
            except APIError: pass
        data=query.get("data")
        match=re.fullmatch(r"vc:([a-f0-9]{32}):([pvmr]):([0-9]{1,3})",data) if isinstance(data,str) else None
        view=self.state.get("view")
        if (not match or not view or view.get("closed") or match[1]!=view["rid"]
                or message.get("message_id")!=view["message_id"]
                or not 0<=time.time()-view["at"]<TTL):
            answer("列表已过期，请重新发送 /versions AppID。")
            return None
        index=int(match[3])
        if match[2]=="p":
            answer("正在翻页")
            self.render(index)
            return None
        if match[2] in ("m","r"):
            if index!=0:
                answer("按钮无效。")
                return None
            before=view.get("next_before","") if match[2]=="m" else ""
            if match[2]=="m" and (not before or len(view["rows"])>=MAX_ROWS):
                answer("没有更多可加载版本。")
                return None
            answer("正在准备查询")
            try:
                self.start(view["app"],update["update_id"],before=before,background=not before)
            except Exception:
                # Durable dispatch intent, if recorded, is retained; never repost here.
                self.c.say("暂时无法启动查询，已有列表仍可查看。")
            return None
        if not 0<=index<len(view["rows"]):
            answer("版本按钮无效。")
            return None
        if index in view["used"]:
            answer("此按钮已提交过，请用 /status 查看任务。")
            return None
        pending=self.state.get("pending")
        if self.c.current or (pending and not pending.get("background")):
            answer("已有任务处理中，请稍后再选择。")
            return None
        answer("已选择 "+view["rows"][index]["version"]+"，正在检查")
        # Convert only authenticated, bound selections into the normal guarded command path.
        return {"update_id":update["update_id"],"_version_choice":(view["rid"],index),
                "_version_label":view["rows"][index]["version"],
                "message":{"date":int(time.time()),"from":{"id":self.c.owner,"is_bot":False},
                           "chat":{"id":self.c.owner,"type":"private"},
                           "text":"/version "+view["app"]+" "+view["rows"][index]["id"]}}

    def consume(self,choice):
        view=self.state.get("view")
        rid,index=choice
        require(view and rid==view["rid"] and index not in view["used"],"version_button_already_used")
        view["used"].append(index)
        view["closed"]=True
        pending=self.state.get("pending")
        if pending and pending["app"]==view["app"]:
            pending["suppress_open"]=True
        self.save()
        # Cosmetic edit cannot abort or repeat the durable task submission.
        try:
            self.c.bot.call("editMessageText",{
                "chat_id":self.c.owner,"message_id":view["message_id"],
                "text":"已选择版本："+view["rows"][index]["version"],
                "reply_markup":{"inline_keyboard":[]}})
        except APIError:
            pass
