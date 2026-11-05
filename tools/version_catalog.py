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
TTL=21600
PAGE=10

def validate(payload,rid,app,run_id,commit):
    require(isinstance(payload,dict) and payload.get("schema")=="ipa-version-catalog-v1"
            and payload.get("request_id")==rid and payload.get("app_id")==app
            and payload.get("run_id")==str(run_id) and payload.get("source_commit")==commit,
            "invalid_version_catalog")
    rows=payload.get("rows")
    require(isinstance(rows,list) and 0<len(rows)<=60
            and type(payload.get("total")) is int and len(rows)<=payload["total"]<=10000,
            "invalid_version_catalog")
    seen=set()
    for row in rows:
        require(isinstance(row,dict) and set(row)=={"id","version","date"},"invalid_version_catalog")
        try:
            require(external_id(row["id"]) and selector(row["version"])==row["version"]
                    and not external_id(row["version"]) and row["id"] not in seen,
                    "invalid_version_catalog")
        except (ValueError,TypeError):
            raise QueueError("invalid_version_catalog") from None
        require(isinstance(row["date"],str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",row["date"]),
                "invalid_version_catalog")
        seen.add(row["id"])
    return {"rows":rows,"total":payload["total"]}

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

    def dispatch(self,rid,app):
        if self.find(rid,app):
            return
        self.github.call("/actions/workflows/"+WORKFLOW+"/dispatches",
                         {"ref":"main","inputs":{"app_id":app,"request_id":rid,"runner":"macos-26-intel"}},"POST")

    def result(self,run,rid,app):
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
            self.github.archive(artifact["id"],path)
            require(path.stat().st_size<=131072 and sha256(path)==artifact["digest"][7:],"catalog_digest_mismatch")
            with zipfile.ZipFile(path) as archive:
                require(archive.namelist()==["versions.json"] and archive.getinfo("versions.json").file_size<=32768,
                        "invalid_catalog_archive")
                payload=json.loads(archive.read("versions.json"))
        return validate(payload,rid,app,run_id,run["head_sha"])

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

    def begin(self,app,update_id):
        now=int(time.time())
        if self.c.current:
            self.c.say("已有下载任务处理中，请完成后再查询历史版本。")
            return
        if self.state.get("pending"):
            self.c.say("历史版本正在查询，请稍候；用 /status 查看状态。")
            return
        rid=hmac.new(self.c.token.encode(),("versions:"+str(self.c.owner)+":"+str(update_id)+":"+app).encode(),hashlib.sha256).hexdigest()[:32]
        cache=self.state.get("cache",{})
        entry=cache.get(app)
        if entry and 0<=now-entry["at"]<TTL:
            self.open(app,rid,entry)
            return
        queries=[stamp for stamp in self.state.get("queries",[]) if now-86400<stamp<=now]
        if len(queries)>=20 or (queries and now-queries[-1]<60):
            self.c.say("版本查询较频繁，请稍后再试。缓存列表可直接翻页。")
            return
        self.c.github.preflight_app(app,historical=True)
        self.state["queries"]=queries+[now]
        self.state["pending"]={"rid":rid,"app":app,"at":now}
        self.save()  # Durable intent before POST; never repeat an ambiguous dispatch.
        self.c.say("正在查询 Apple 历史版本，首次加载需要等待 GitHub 运行器。完成后会显示可点击列表。")
        try:
            self.api.dispatch(rid,app)
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
        entry=self.api.result(run,pending["rid"],pending["app"])
        entry["at"]=int(time.time())
        cache=self.state.setdefault("cache",{})
        cache[pending["app"]]=entry
        for app in list(cache):
            if time.time()-cache[app]["at"]>=TTL:
                del cache[app]
        while len(cache)>4:
            del cache[min(cache,key=lambda app:cache[app]["at"])]
        self.state["pending"]=None
        self.save()
        self.open(pending["app"],pending["rid"],entry)

    def open(self,app,rid,entry):
        self.state["view"]={"rid":rid,"app":app,"at":int(time.time()),"rows":entry["rows"],
                            "total":entry["total"],"message_id":0,"used":[]}
        self.save()
        self.render(0,False)

    def render(self,page,edit=True):
        view=self.state["view"]
        rows=view["rows"]
        pages=(len(rows)+PAGE-1)//PAGE
        if not 0<=page<pages:
            return
        prefix="vc:"+view["rid"]+":"
        keyboard=[]
        chunk=[]
        text="App ID："+view["app"]+" · 请选择版本\n第 "+str(page+1)+"/"+str(pages)+" 页"
        text+="\n点击版本即提交下载解密；实际可下载性以 Apple 响应为准。"
        if len(rows)<view["total"]:
            text+="\n当前显示 "+str(len(rows))+" 个已查询版本，非完整历史。"
        for index in range(page*PAGE,min((page+1)*PAGE,len(rows))):
            row=rows[index]
            chunk.append({"text":row["version"],"callback_data":prefix+"v:"+str(index)})
            if len(chunk)==2:
                keyboard.append(chunk);chunk=[]
        if chunk: keyboard.append(chunk)
        navigation=[]
        if page>0: navigation.append({"text":"上一页","callback_data":prefix+"p:"+str(page-1)})
        if page+1<pages: navigation.append({"text":"下一页","callback_data":prefix+"p:"+str(page+1)})
        if navigation: keyboard.append(navigation)
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
        match=re.fullmatch(r"vc:([a-f0-9]{32}):([pv]):([0-9]{1,2})",data) if isinstance(data,str) else None
        view=self.state.get("view")
        if (not match or not view or match[1]!=view["rid"]
                or message.get("message_id")!=view["message_id"]
                or not 0<=time.time()-view["at"]<TTL):
            answer("列表已过期，请重新发送 /versions AppID。")
            return None
        index=int(match[3])
        if match[2]=="p":
            answer("正在翻页")
            self.render(index)
            return None
        if not 0<=index<len(view["rows"]):
            answer("版本按钮无效。")
            return None
        if index in view["used"]:
            answer("此按钮已提交过，请用 /status 查看任务。")
            return None
        if self.c.current or self.state.get("pending"):
            answer("已有任务处理中，请稍后再选择。")
            return None
        answer("正在检查并提交所选版本")
        # Convert only authenticated, bound selections into the normal guarded command path.
        return {"update_id":update["update_id"],"_version_choice":(view["rid"],index),
                "message":{"date":int(time.time()),"from":{"id":self.c.owner,"is_bot":False},
                           "chat":{"id":self.c.owner,"type":"private"},
                           "text":"/version "+view["app"]+" "+view["rows"][index]["id"]}}

    def consume(self,choice):
        view=self.state.get("view")
        rid,index=choice
        require(view and rid==view["rid"] and index not in view["used"],"version_button_already_used")
        view["used"].append(index)
        self.save()
