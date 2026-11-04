"""Sanitized worker stages and a single Telegram progress card; no estimated percentages."""
import json
import os
import re
import time
from telegram_api import APIError

LABELS = {
 "dispatch_pending":"正在确认任务提交", "queued":"排队中", "preparing":"准备运行环境",
 "processing":"正在执行，等待阶段更新", "metadata":"查询应用信息", "authenticating":"验证下载账号", "downloading":"下载原始 IPA",
 "auditing":"检查原始文件", "decrypting":"解密并校验页面", "verifying":"复核完整 IPA",
 "encrypting":"加密保存结果", "artifact_ready":"准备文件交付",
 "retrieving":"取回加密文件", "delivery_verifying":"解密并复核交付文件",
 "uploading":"上传到 Telegram", "done":"完成 · 100%", "failed":"任务未完成",
 "cancelled":"已请求取消", "unknown":"暂时无法获取最新进度",
}
WORKER_STAGES = {"metadata","authenticating","downloading","auditing","decrypting",
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

class WorkerProgress:
    def __init__(self, rid):
        self.rid,self.check,self.disabled=rid,None,False
        self.run_id=os.environ.get("GITHUB_RUN_ID","")
        self.commit=os.environ.get("GITHUB_SHA","")
        self.valid=bool(re.fullmatch(r"[a-f0-9]{32}",rid or "")
                        and re.fullmatch(r"[0-9]+",self.run_id)
                        and re.fullmatch(r"[a-f0-9]{40}",self.commit)
                        and os.environ.get("GITHUB_REPOSITORY")=="zwthys-cyber/ipa-decrypt-lab"
                        and os.environ.get("GITHUB_ACTIONS")=="true")
    def advance(self,stage):
        if not self.valid or self.disabled or stage not in WORKER_STAGES:
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

class ProgressCard:
    def __init__(self,bot,owner,rid,app="",demo=False):
        self.bot,self.owner,self.rid,self.app=bot,owner,rid,app
        self.demo,self.message_id=demo,None
        self.started=time.monotonic()
        self.stage=None
        self.last=-float("inf")
    def render(self,stage):
        elapsed=max(0,int(time.monotonic()-self.started))
        return (("【进度演示，不执行下载】\n" if self.demo else "IPA 任务进度\n")
                +("App ID："+self.app+"\n" if self.app else "")
                +"阶段："+LABELS[stage]+"\n已用时间："+str(elapsed//60)+"分"+str(elapsed%60)+"秒"
                +"\n任务编号："+self.rid)
    def update(self,stage,force=False):
        if stage not in LABELS:
            stage="unknown"
        now=time.monotonic()
        if not force and stage==self.stage and now-self.last<15:
            return
        text=self.render(stage)
        try:
            if self.message_id is None:
                reply=self.bot.message(self.owner,text)
                if isinstance(reply,dict) and type(reply.get("message_id")) is int:
                    self.message_id=reply["message_id"]
            else:
                self.bot.edit(self.owner,self.message_id,text)
            self.stage,self.last=stage,now
            return True
        except APIError:
            # An edit timeout cannot trigger a duplicate job or file upload.
            self.last=now
            return False
