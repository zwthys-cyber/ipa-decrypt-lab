"""Bounded local cooldown before one saved-session Store resume; no HTTP retry loop."""
import json
import time

def wait_until(env,now=time.time,sleep=time.sleep):
    text=env.get("TF_VIRTUAL_NOT_BEFORE","")
    if not isinstance(text,str) or not text.isdigit():raise ValueError("tf_cooldown_invalid")
    target=int(text);remaining=target-int(now())
    if remaining>600:raise ValueError("tf_cooldown_out_of_bounds")
    if remaining>0:
        print(json.dumps({"schema":"tf-virtual-resume-v1","status":"cooldown_pending",
                          "remaining_seconds":remaining,"policy":"local_600s_fallback"}),flush=True)
    while int(now())<target:
        sleep(min(15,max(1,target-int(now()))))
