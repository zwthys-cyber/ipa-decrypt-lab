"""Sanitized worker stages and a single Telegram progress card; measured counters and explicitly labelled workflow-step progress."""
import json
import os
import re
import time
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from telegram_api import APIError

LABELS = {
 "auth_retry":"Apple 登录服务暂不可用，正在等待重试",
 "switching":"正在切换备用运行器", "capacity_wait":"运行器容量不足，正在核对切换状态",
 "dispatch_pending":"正在确认任务提交", "queued":"排队中", "preparing":"准备运行环境",
 "building":"构建并测试下载组件", "processing":"正在执行，等待阶段更新", "metadata":"查询应用信息", "authenticating":"验证下载账号", "downloading":"下载原始 IPA",
 "resolving_version":"查询指定历史版本并下载", "auditing":"检查原始文件", "decrypting":"解密并校验页面", "verifying":"复核完整 IPA",
 "encrypting":"加密保存结果", "artifact_ready":"准备文件交付",
 "retrieving":"取回加密文件", "delivery_verifying":"解密并复核交付文件",
 "uploading":"上传到 Telegram", "done":"完成", "failed":"任务未完成",
 "cancelled":"已请求取消", "unknown":"暂时无法获取最新进度",
}
WORKER_STAGES = {"auth_retry","resolving_version","metadata","authenticating","downloading","auditing","decrypting",
                 "verifying","encrypting","artifact_ready","failed"}

def parse_stage(check, rid, run_id):
    if (not isinstance(check,dict) or not isinstance(check.get("app"),dict) or check.get("name")!="delivery-progress-"+rid
            or check.get("external_id")!=rid+":"+str(run_id)
            or check.get("app",{}).get("slug")!="github-actions"):
        return None
    raw=check.get("output",{}).get("summary","")
    if not isinstance(raw,str) or len(raw)>2048:
        return None
    try:
        value=json.loads(raw)
        if (value.get("schema")=="ipa-stage-v1" and value.get("request_id")==rid
                and value.get("run_id")==str(run_id) and value.get("stage") in WORKER_STAGES):
            return value["stage"]
    except (ValueError,TypeError,AttributeError):
        pass
    return None


# Percentages count completed workflow steps; they are not time estimates.
STEPS = ("preparing","metadata","authenticating","downloading","auditing","decrypting",
         "verifying","encrypting","retrieving","delivery_verifying","uploading","done")
ALIASES = {"dispatch_pending":"preparing","queued":"preparing","switching":"preparing",
           "capacity_wait":"preparing","building":"preparing","auth_retry":"authenticating",
           "resolving_version":"downloading","artifact_ready":"retrieving"}
TERMINAL = {"done","failed","cancelled"}

def measurement(value):
    if (isinstance(value,dict) and set(value)=={"unit","completed","total"}
            and value["unit"]=="bytes" and type(value["completed"]) is int
            and type(value["total"]) is int and 0<=value["completed"]<=value["total"]<=2_000_000_000
            and value["total"]>0):
        return {"unit":"bytes","completed":value["completed"],"total":value["total"]}
    return None

def parse_snapshot(value,rid,run_id,commit,sequence=None):
    if not isinstance(value,dict) or not set(value)<= {"schema","request_id","run_id","commit","stage","sequence","updated_at","stage_started","measurement"}:
        return None
    if (value.get("schema")!="ipa-stage-v2" or value.get("request_id")!=rid
            or value.get("run_id")!=str(run_id) or value.get("commit")!=commit
            or value.get("stage") not in WORKER_STAGES
            or type(value.get("sequence")) is not int or not 1<=value["sequence"]<=1_000_000
            or (sequence is not None and sequence!=value["sequence"])
            or type(value.get("updated_at")) is not int
            or not 0<=time.time()-value["updated_at"]+120<=86520):
        return None
    if "stage_started" in value and (type(value["stage_started"]) is not int or not value["updated_at"]-86400<=value["stage_started"]<=value["updated_at"]):
        return None
    result=dict(value)
    if "measurement" in value:
        counter=measurement(value["measurement"])
        if value["stage"]!="downloading" or counter is None:
            return None
        result["measurement"]=counter
    return result

def duration(seconds):
    seconds=max(0,int(seconds))
    days,seconds=divmod(seconds,86400)
    hours,seconds=divmod(seconds,3600)
    minutes,seconds=divmod(seconds,60)
    return (str(days)+"天 " if days else "")+f"{hours:02}:{minutes:02}:{seconds:02}"

def byte_text(value):
    return f"{value/1024/1024:.1f} MiB"

class WorkerProgress:
    def __init__(self, rid):
        self.rid,self.check,self.disabled=rid,None,False
        self.sequence=0
        self.stage_started=0
        self.stage=None
        self.counter=None
        self.run_id=os.environ.get("GITHUB_RUN_ID","")
        self.commit=os.environ.get("GITHUB_SHA","")
        self.valid=bool(re.fullmatch(r"[a-f0-9]{32}",rid or "")
                        and re.fullmatch(r"[0-9]+",self.run_id)
                        and re.fullmatch(r"[a-f0-9]{40}",self.commit)
                        and os.environ.get("GITHUB_REPOSITORY")=="zwthys-cyber/ipa-decrypt-lab"
                        and os.environ.get("GITHUB_ACTIONS")=="true")
    def advance(self,stage):
        if not self.valid or stage not in WORKER_STAGES:
            return
        if stage!=self.stage:
            self.counter=None
            self.stage_started=int(time.time())
        self.stage=stage
        self.snapshot()
        if self.disabled:
            return
        try:
            from telegram_queue import GitHub
            github=GitHub(os.environ.get("GH_TOKEN",""))
            payload={"status":"in_progress", "output":{
                "title":"IPA: "+stage,
                "summary":json.dumps({"schema":"ipa-stage-v1","request_id":self.rid,
                                     "run_id":self.run_id,"stage":stage})}}
            if stage in ("artifact_ready","failed"):
                payload.update(status="completed",conclusion="success" if stage=="artifact_ready" else "failure")
            if self.check is None:
                payload.update(name="delivery-progress-"+self.rid,head_sha=self.commit,
                               external_id=self.rid+":"+self.run_id)
                result=github.call("/check-runs",payload,"POST")
                if not isinstance(result,dict) or type(result.get("id")) is not int:
                    raise ValueError()
                self.check=result["id"]
            else:
                github.call("/check-runs/"+str(self.check),payload,"PATCH")
        except Exception:
            # Progress is best effort; never turn a valid private export into a failed decryption.
            self.disabled=True
            print('{"schema":"ipa-stage-v1","status":"progress_feed_unavailable"}',flush=True)


    def snapshot(self):
        target=os.environ.get("IPA_PROGRESS_FILE","")
        if not self.valid or not target or self.stage not in WORKER_STAGES:
            return
        self.sequence+=1
        value={"schema":"ipa-stage-v2","request_id":self.rid,"run_id":self.run_id,
               "commit":self.commit,"stage":self.stage,"sequence":self.sequence,"updated_at":int(time.time()),"stage_started":self.stage_started}
        if self.counter is not None and self.stage=="downloading":
            value["measurement"]=self.counter
        temporary=None
        try:
            destination=Path(target)
            fd,temporary=tempfile.mkstemp(prefix=".progress-",dir=destination.parent)
            with os.fdopen(fd,"w") as stream:
                json.dump(value,stream,separators=(",",":"))
            os.replace(temporary,destination)
        except (OSError,ValueError):
            pass
        finally:
            if temporary:
                try: os.unlink(temporary)
                except FileNotFoundError: pass

    def measure(self,completed,total):
        counter=measurement({"unit":"bytes","completed":completed,"total":total})
        if counter is None or self.stage not in ("downloading","resolving_version"):
            return
        if self.counter is not None and (self.counter["total"]!=total or completed<self.counter["completed"]):
            return
        if self.stage!="downloading": self.stage_started=int(time.time())
        self.stage="downloading"
        self.counter=counter
        self.snapshot()

class ProgressCard:
    def __init__(self,bot,owner,rid,app="",demo=False,started_at=None,restored=None,save=None):
        self.bot,self.owner,self.rid,self.app=bot,owner,rid,app
        self.demo,self.message_id=demo,None
        self.started=time.monotonic()
        wall=time.time()
        self.offset=max(0,wall-started_at) if type(started_at) in (int,float) and 0<started_at<=wall else 0
        self.started_at=wall-self.offset
        self.stage=None
        self.stage_started=self.started
        self.stage_offset=0
        self.completed=0
        self.counter=None
        self.counter_at=None
        self.finished=None
        self.pending_final=False
        self.final_attempts=0
        self.last=-float("inf")
        self.save=save
        self.lock=threading.RLock()
        if isinstance(restored,dict):
            if type(restored.get("message_id")) is int and restored["message_id"]>0:
                self.message_id=restored["message_id"]
            if isinstance(restored.get("stage"),str) and restored["stage"] in LABELS:
                self.stage=restored["stage"]
            stamp=restored.get("stage_started")
            if type(stamp) in (int,float) and self.started_at<=stamp<=wall:
                self.stage_offset=wall-stamp
            if type(restored.get("completed")) is int and 0<=restored["completed"]<=len(STEPS):
                self.completed=restored["completed"]
            if type(restored.get("finished")) in (int,float) and restored["finished"]>=0:
                self.finished=restored["finished"]

    def elapsed(self):
        return self.finished if self.finished is not None else max(0,self.offset+time.monotonic()-self.started)

    def render(self,stage):
        elapsed=self.elapsed()
        rank=STEPS.index(ALIASES.get(stage,stage)) if ALIASES.get(stage,stage) in STEPS else 0
        complete=max(self.completed,rank)
        if stage=="done": complete=len(STEPS)
        if stage!="done": complete=min(complete,len(STEPS)-1)
        percent=complete*100//len(STEPS)
        filled=percent//10
        lines=["【进度演示，不执行下载】" if self.demo else "IPA 任务进度"]
        if self.app: lines.append("App ID："+self.app)
        lines.extend(["流程进度："+"█"*filled+"░"*(10-filled)+f" {percent}%",
                      f"已完成：{complete}/{len(STEPS)} 步（按步骤，非剩余时间估算）",
                      "阶段："+LABELS[stage]])
        if self.counter is not None and ALIASES.get(stage,stage)=="downloading":
            current,total=self.counter["completed"],self.counter["total"]
            age=max(0,int(time.time()-(self.counter_at or time.time())))
            label="下载进度" if age<=30 else f"最近下载进度（{age}秒前）"
            lines.append(f"{label}：{current*100/total:.1f}% · {byte_text(current)} / {byte_text(total)}")
        phase=max(0,self.stage_offset+time.monotonic()-self.stage_started)
        if self.finished is not None: phase=min(phase,max(0,self.finished))
        lines.extend(["总耗时："+duration(elapsed),"本阶段耗时："+duration(phase),
                      "开始时间："+datetime.fromtimestamp(self.started_at,timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                      "任务编号："+self.rid])
        return "\n".join(lines)

    def _store(self):
        if self.save is None: return
        try:
            self.save({"message_id":self.message_id,"stage":self.stage,
                       "stage_started":time.time()-max(0,self.stage_offset+time.monotonic()-self.stage_started),
                       "completed":self.completed,"finished":self.finished})
        except Exception:
            # A progress persistence failure must not repeat dispatch or delivery.
            pass

    def update(self,stage,force=False,measurement_value=None,heartbeat=False,stage_started_at=None,measurement_at=None):
        with self.lock:
            if stage not in LABELS: stage="unknown"
            now=time.monotonic()
            if heartbeat and (self.message_id is None or (self.finished is not None and not self.pending_final)): return
            throttled=not force and stage==self.stage and now-self.last<5
            group=ALIASES.get(stage,stage)
            old_group=ALIASES.get(self.stage,self.stage)
            if group in STEPS and old_group in STEPS and STEPS.index(group)<STEPS.index(old_group):
                stage=self.stage
                group=old_group
                stage_started_at=None
                measurement_value=None
                measurement_at=None
            if group!=old_group:
                self.stage_started=now
                self.stage_offset=0
                self.counter=None
            if type(stage_started_at) in (int,float) and self.started_at<=stage_started_at<=time.time():
                self.stage_started=now
                self.stage_offset=max(0,time.time()-stage_started_at)
            counter=measurement(measurement_value)
            if counter and group=="downloading" and (self.counter is None or
                    (counter["total"]==self.counter["total"] and counter["completed"]>=self.counter["completed"])):
                if self.counter!=counter:
                    self.counter_at=measurement_at if type(measurement_at) in (int,float) and measurement_at<=time.time() else time.time()
                self.counter=counter
            if group in STEPS: self.completed=max(self.completed,STEPS.index(group))
            if stage=="done": self.completed=len(STEPS)
            if stage in TERMINAL and self.finished is None:
                self.finished=max(0,self.offset+now-self.started)
            # Accept new metrics even when the timer just edited the message.
            # The next heartbeat renders these counters without losing updates.
            if throttled: return
            text=self.render(stage)
            try:
                if self.message_id is None:
                    reply=self.bot.message(self.owner,text)
                    if isinstance(reply,dict) and type(reply.get("message_id")) is int:
                        self.message_id=reply["message_id"]
                else:
                    if heartbeat: self.bot.edit(self.owner,self.message_id,text,timeout=8)
                    else: self.bot.edit(self.owner,self.message_id,text)
                self.stage,self.last=stage,now
                self.pending_final=False
                if not heartbeat: self._store()
                return True
            except APIError:
                self.stage,self.last=stage,now
                if stage in TERMINAL and self.message_id is not None:
                    self.final_attempts+=1
                    self.pending_final=self.final_attempts<3
                return False

    def pulse(self):
        if self.stage is not None:
            return self.update(self.stage,heartbeat=True)
