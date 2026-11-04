"""Signed, sanitized GitHub Checks journal for bounded owner sessions.

This is a bounded recovery log, not a production database or distributed lock.
The workflow's single-session concurrency group remains mandatory.
"""
import hashlib
import hmac
import json
import re
import time
from telegram_queue import QueueError, request_id, require

ANCHOR = "482c1fccde988a4ca198251e32935374e83578f1"
STATES = {"pending", "sending", "delivered", "cancelled", "closed"}

class Journal:
    def __init__(self, github, token, owner):
        require(bool(token) and type(owner) is int and owner > 0, "invalid_journal_identity")
        self.github = github
        self.key = hmac.new(token.encode(), ("journal-v1:"+str(owner)).encode(), hashlib.sha256).digest()
        self.name = "delivery-journal-" + hmac.new(self.key,b"namespace",hashlib.sha256).hexdigest()[:32]
        self.records = {}

    def signature(self, record):
        return hmac.new(self.key,json.dumps(record,sort_keys=True,separators=(",",":")).encode(),hashlib.sha256).hexdigest()

    def load(self):
        records = {}
        for page in range(1,6):
            data = self.github.call("/commits/"+ANCHOR+"/check-runs?check_name="+self.name+
                                    "&filter=all&per_page=100&page="+str(page))
            require(isinstance(data,dict) and isinstance(data.get("check_runs"),list), "invalid_journal_response")
            for check in data["check_runs"]:
                try:
                    if (check.get("name")!=self.name or check.get("head_sha")!=ANCHOR
                            or check.get("app",{}).get("slug")!="github-actions"):
                        continue
                    envelope=json.loads(check["output"]["summary"])
                    record=envelope["record"]
                    if not hmac.compare_digest(envelope["mac"],self.signature(record)):
                        continue
                    require(set(record)=={"schema","rid","app","state","at"}, "invalid_journal_record")
                    require(record["schema"]=="delivery-journal-v1", "invalid_journal_record")
                    request_id(record["rid"])
                    require(record["state"] in STATES and isinstance(record["app"],str)
                            and (record["app"]=="" or re.fullmatch(r"[1-9][0-9]{4,19}",record["app"]))
                            and type(record["at"]) is int and record["at"]>0, "invalid_journal_record")
                    require(check.get("external_id")==record["rid"] and type(check.get("id")) is int, "invalid_journal_record")
                    old=records.get(record["rid"])
                    if old is None or check["id"]>old["check_id"]:
                        records[record["rid"]]=dict(record,check_id=check["id"])
                except (KeyError,TypeError,ValueError,QueueError):
                    continue
            if len(data["check_runs"])<100:
                self.records=records
                return records
        raise QueueError("journal_capacity_reached")

    def write(self, rid, state, app=""):
        request_id(rid)
        require(state in STATES and isinstance(app,str)
                and (app=="" or re.fullmatch(r"[1-9][0-9]{4,19}",app)), "invalid_journal_record")
        old=self.records.get(rid,{})
        record={"schema":"delivery-journal-v1","rid":rid,"app":app or old.get("app",""),
                "state":state,"at":int(time.time())}
        envelope={"record":record,"mac":self.signature(record)}
        result=self.github.call("/check-runs",{
            "name":self.name,"head_sha":ANCHOR,"external_id":rid,
            "status":"completed","conclusion":"neutral",
            "output":{"title":"Bounded delivery recovery state","summary":json.dumps(envelope,separators=(",",":"))}
        },"POST")
        require(isinstance(result,dict) and type(result.get("id")) is int, "journal_write_unconfirmed")
        # Read back before allowing the dispatch/send side effect.
        actual=self.github.call("/check-runs/"+str(result["id"]))
        require(actual.get("head_sha")==ANCHOR and actual.get("name")==self.name
                and actual.get("external_id")==rid and actual.get("app",{}).get("slug")=="github-actions"
                and json.loads(actual.get("output",{}).get("summary","{}"))==envelope,
                "journal_write_unconfirmed")
        self.records[rid]=dict(record,check_id=result["id"])

    def pending(self):
        now=int(time.time())
        return [r for r in self.records.values() if r["state"]=="pending" and 0<=now-r["at"]<86400]
