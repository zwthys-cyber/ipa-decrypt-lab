"""Bounded runner failover decisions. Never retry work that reached a runner."""
from datetime import datetime, timezone
import re

RUNNERS=("macos-26-intel","macos-26","macos-15-intel","macos-15")
QUEUE_SECONDS=180
MAX_RUNS=2

def matches(run,rid):
    title=run.get("display_title","")
    return (title=="delivery-"+rid or
            re.fullmatch(r"delivery-"+re.escape(rid)+r"-app[1-9][0-9]{4,19}-(?:macos-(?:15|26)(?:-intel)?)",title) is not None)

def app_from_run(run,rid):
    m=re.fullmatch(r"delivery-"+re.escape(rid)+r"-app([1-9][0-9]{4,19})-(?:macos-(?:15|26)(?:-intel)?)",
                   run.get("display_title",""))
    return m.group(1) if m else ""

def unassigned(jobs):
    return bool(jobs) and all(isinstance(j,dict) and not j.get("runner_id")
        and not j.get("runner_name") and j.get("steps")==[] for j in jobs)

def queued_too_long(run,jobs,now=None):
    if run.get("status") not in ("queued","waiting","pending","requested") or not unassigned(jobs):
        return False
    try:
        created=datetime.fromisoformat(run["created_at"].replace("Z","+00:00"))
        if created.tzinfo is None:
            return False
        age=((now or datetime.now(timezone.utc))-created).total_seconds()
        return age>=QUEUE_SECONDS
    except (KeyError,ValueError,TypeError):
        return False

def retryable(run,jobs,cancel_requested=False):
    return (run.get("status")=="completed" and
            (run.get("conclusion")=="failure" or
             (cancel_requested and run.get("conclusion")=="cancelled"))
            and unassigned(jobs) and all(j.get("status")=="completed" for j in jobs))

def alternate(jobs):
    labels={label for j in jobs for label in j.get("labels",[]) if isinstance(label,str)}
    return "macos-15" if "macos-15-intel" in labels else "macos-15-intel"
