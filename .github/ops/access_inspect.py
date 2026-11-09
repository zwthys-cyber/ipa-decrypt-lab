"""Read-only operational inspection. Never emit private IDs, request IDs or keys."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

SOURCE="b92dc1575123e1b7eab2283b62d355539fc71e4d"
STATES={"pending","sending","delivered","cancelled","closed"}

def inspect(root,request,nonce,now=None):
    now=int(time.time() if now is None else now)
    if (not isinstance(request,dict) or set(request)!={"uid","admin","nonce","expires","expected_request"}
            or not re.fullmatch(r"[a-f0-9]{32}",nonce or "") or request['nonce']!=nonce
            or type(request['uid']) is not int or not 0<request['uid']<2**63
            or type(request['admin']) is not int or not 0<request['admin']<2**63
            or type(request['expires']) is not int or not now<=request['expires']<=now+1800
            or not isinstance(request['expected_request'],str)
            or (request['expected_request'] and not re.fullmatch(r"[a-f0-9]{32}",request['expected_request']))):
        raise ValueError("invalid operational request")
    root=Path(root)
    config=root/'etc/ipazake/bot.json'
    if config.stat().st_mode&0o077:raise ValueError("private configuration required")
    owner=int(json.loads(config.read_text())['TELEGRAM_OWNER_ID'])
    if owner!=request['admin']:raise ValueError("administrator mismatch")
    source=(root/'opt/ipazake/current/SOURCE_COMMIT').read_text().strip()
    if source!=SOURCE:raise ValueError("unverified runtime source")
    health=json.loads((root/'var/lib/ipazake/health.json').read_text())
    state=health.get('state')
    if state not in {'ready','starting','stopped','github_unavailable','telegram_unavailable','failed'}:state='unknown'
    scope=lambda uid:hashlib.sha256(('telegram-owner:'+str(uid)).encode()).hexdigest()
    path=root/'var/lib/ipazake/state.sqlite3'
    db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10)
    try:
        row=db.execute('SELECT enabled,daily_limit FROM tenant_access WHERE namespace=? AND uid=?',(scope(owner),request['uid'])).fetchone()
        admin=request['uid']==owner
        own=scope(request['uid'])
        item=db.execute('SELECT state FROM tasks WHERE scope=? AND rid=?',(own,request['expected_request'])).fetchone() if request['expected_request'] else None
        task_state=item[0] if item and item[0] in STATES else None
        admin_item=db.execute('SELECT 1 FROM tasks WHERE scope=? AND rid=?',(scope(owner),request['expected_request'])).fetchone() if request['expected_request'] else None
        card=db.execute('SELECT value FROM metadata WHERE scope=? AND name=?',(own,'progress:'+request['expected_request'])).fetchone() if request['expected_request'] else None
        progress=json.loads(card[0]) if card else {}
        phase=progress.get('stage') if isinstance(progress,dict) else None
        if phase not in {'done','uploading','retrieving','delivery_verifying','failed','unknown','cancelled'}:phase='processing' if phase else None

        return {'schema':'ipa-private-access-inspection-v1','status':'inspected',
                'runtime_source':source,'service_state':state,'service_task_active':health.get('task_active') is True,
                'target_is_administrator':admin,'target_authorized':admin or bool(row and row[0]==1),
                'target_daily_limit':row[1] if row and not admin else None,
                'expected_request_owned':item is not None,'expected_request_state':task_state,
                'separate_from_administrator':not admin and item is not None and admin_item is None,
                'expected_progress_stage':phase,
                'expected_progress_finished':isinstance(progress.get('finished'),(int,float)) and not isinstance(progress.get('finished'),bool),
                'expected_progress_message_saved':type(progress.get('message_id')) is int and progress['message_id']>0}
    finally:db.close()

def main():
    try:
        path=Path(sys.argv[1])
        if path.stat().st_size>2048 or path.stat().st_mode&0o077:raise ValueError()
        value=inspect('/',json.loads(path.read_text()),sys.argv[2])
        print(json.dumps(value));return 0
    except Exception:
        print('{"schema":"ipa-private-access-inspection-v1","status":"inspection_unavailable"}')
        return 2
if __name__=='__main__':raise SystemExit(main())
