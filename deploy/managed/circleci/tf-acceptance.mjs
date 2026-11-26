// Durable acceptance candidate. No HTTP route or activation is installed by this module.
const HASH=/^[a-f0-9]{64}$/,SHA=/^[a-f0-9]{40}$/,HEX=/^[a-f0-9]{32}$/;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
function require(value,code){if(!value)throw Error(code);}
export const SCHEMA=`
CREATE TABLE IF NOT EXISTS circleci_tf_handoff (
  owner_id TEXT PRIMARY KEY,
  snapshot_sha256 TEXT NOT NULL,
  session_sha256 TEXT NOT NULL,
  source_sha TEXT NOT NULL,
  stage_nonce TEXT NOT NULL,
  ready INTEGER NOT NULL DEFAULT 0 CHECK(ready IN (0,1)),
  sealed_at INTEGER
);
CREATE TABLE IF NOT EXISTS circleci_tf_acceptances (
  invite_hash TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('confirmed','intent','unknown')),
  request_id TEXT NOT NULL UNIQUE,
  run_id TEXT NOT NULL,
  source_sha TEXT NOT NULL,
  nonce TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  imported INTEGER NOT NULL CHECK(imported IN (0,1))
);
`;
function owner(value){require(/^[1-9][0-9]{0,15}$/.test(value||""),"tf_owner");}
export async function inviteHash(invite,ownerId,pepper){
  owner(ownerId);
  require(/^[A-Za-z0-9_-]{6,80}$/.test(invite||"")&&pepper instanceof Uint8Array&&pepper.byteLength===32,"tf_hash_input");
  const key=await crypto.subtle.importKey("raw",pepper,{name:"HMAC",hash:"SHA-256"},false,["sign"]);
  const raw=await crypto.subtle.sign("HMAC",key,new TextEncoder().encode("cn-testflight\0"+ownerId+"\0"+invite));
  return Array.from(new Uint8Array(raw),v=>v.toString(16).padStart(2,"0")).join("");
}
function proof(value){
  require(value&&Object.keys(value).sort().join(",")==="session_sha256,snapshot_sha256,source_sha"&&
    HASH.test(value.snapshot_sha256||"")&&HASH.test(value.session_sha256||"")&&SHA.test(value.source_sha||""),"tf_handoff_proof");
}
export async function stageHandoff(db,ownerId,evidence,rows){
  owner(ownerId);proof(evidence);
  require(Array.isArray(rows)&&rows.length<=20,"tf_import_limit");
  const nonce=crypto.randomUUID().replaceAll("-","");
  const queries=[db.prepare(`INSERT INTO circleci_tf_handoff(owner_id,snapshot_sha256,session_sha256,source_sha,stage_nonce)
    VALUES(?,?,?,?,?) ON CONFLICT(owner_id) DO NOTHING`).bind(ownerId,evidence.snapshot_sha256,evidence.session_sha256,evidence.source_sha,nonce)];
  const seen=new Set();
  for(const r of rows){
    require(r&&HASH.test(r.invite_hash||"")&&!seen.has(r.invite_hash)&&["confirmed","intent","unknown"].includes(r.state)&&
      /^tf_[a-f0-9]{32}$/.test(r.request_id||"")&&/^[1-9][0-9]{0,19}$/.test(r.run_id||"")&&
      SHA.test(r.source_sha||"")&&HEX.test(r.nonce||"")&&Number.isSafeInteger(r.created_at)&&
      Number.isSafeInteger(r.updated_at)&&r.created_at>=0&&r.updated_at>=r.created_at,"tf_import_row");
    seen.add(r.invite_hash);
    queries.push(db.prepare(`INSERT INTO circleci_tf_acceptances
      (invite_hash,owner_id,state,request_id,run_id,source_sha,nonce,created_at,updated_at,imported)
      SELECT ?,?,?,?,?,?,?,?,?,1 WHERE EXISTS (
        SELECT 1 FROM circleci_tf_handoff WHERE owner_id=? AND snapshot_sha256=? AND session_sha256=? AND source_sha=? AND stage_nonce=? AND sealed_at IS NULL)
      ON CONFLICT(invite_hash) DO NOTHING`).bind(r.invite_hash,ownerId,r.state,r.request_id,r.run_id,r.source_sha,
        r.nonce,r.created_at,r.updated_at,ownerId,evidence.snapshot_sha256,evidence.session_sha256,evidence.source_sha,nonce));
  }
  const result=await db.batch(queries);require(result.every(r=>r.success===true),"tf_import_storage");
  const saved=await db.prepare("SELECT * FROM circleci_tf_handoff WHERE owner_id=?").bind(ownerId).first();
  require(saved&&saved.snapshot_sha256===evidence.snapshot_sha256&&saved.session_sha256===evidence.session_sha256&&
    saved.source_sha===evidence.source_sha&&saved.sealed_at===null,"tf_handoff_immutable");
  // Read back every imported outcome. Conflicts never overwrite the original truth.
  for(const r of rows){
    const current=await db.prepare("SELECT * FROM circleci_tf_acceptances WHERE invite_hash=?").bind(r.invite_hash).first();
    require(current&&current.owner_id===ownerId&&current.imported===1&&
      Object.keys(r).every(k=>current[k]===r[k]),"tf_import_conflict");
  }
  const count=await db.prepare("SELECT count(*) n FROM circleci_tf_acceptances WHERE owner_id=? AND imported=1").bind(ownerId).first();
  require(count.n===rows.length,"tf_import_count");
  if(saved.stage_nonce===nonce){
    const done=await db.prepare("UPDATE circleci_tf_handoff SET ready=1 WHERE owner_id=? AND stage_nonce=? AND sealed_at IS NULL")
      .bind(ownerId,nonce).run();require(done.success===true,"tf_import_storage");
  } else require(saved.ready===1,"tf_import_incomplete_no_retry");
  return {staged:true,rows:rows.length};
}
export async function sealHandoff(db,ownerId,evidence,now){
  owner(ownerId);proof(evidence);require(Number.isSafeInteger(now)&&now>0,"tf_handoff_time");
  // Caller must verify a stopped source or an explicit offline token/dispatch fence, and the immutable snapshot. No external route exists.
  const result=await db.prepare(`UPDATE circleci_tf_handoff SET sealed_at=?
    WHERE owner_id=? AND snapshot_sha256=? AND session_sha256=? AND source_sha=? AND ready=1 AND sealed_at IS NULL`)
    .bind(now,ownerId,evidence.snapshot_sha256,evidence.session_sha256,evidence.source_sha).run();
  require(result.success===true&&result.meta?.changes===1,"tf_handoff_seal");
}
function task(value){
  require(value&&Object.keys(value).sort().join(",")==="invite,request_id,run_id,source_commit"&&/^tf_[a-f0-9]{32}$/.test(value.request_id||"")&&UUID.test(value.run_id||"")&&
    SHA.test(value.source_commit||"")&&/^[A-Za-z0-9_-]{6,80}$/.test(value.invite||""),"tf_permit_binding");
}
export async function claimPermit(db,ownerId,hash,request,now){
  owner(ownerId);task(request);require(HASH.test(hash||"")&&Number.isSafeInteger(now)&&now>0,"tf_permit_input");
  const nonce=crypto.randomUUID().replaceAll("-","");
  const result=await db.prepare(`INSERT INTO circleci_tf_acceptances
    (invite_hash,owner_id,state,request_id,run_id,source_sha,nonce,created_at,updated_at,imported)
    SELECT ?,?,'intent',?,?,?,?,?,?,0 WHERE EXISTS(
      SELECT 1 FROM circleci_tf_handoff WHERE owner_id=? AND sealed_at IS NOT NULL)
      AND NOT EXISTS(SELECT 1 FROM circleci_tf_acceptances WHERE owner_id=? AND state IN ('intent','unknown'))
    ON CONFLICT DO NOTHING`).bind(hash,ownerId,request.request_id,request.run_id,request.source_commit,nonce,now,now,
      ownerId,ownerId).run();
  require(result.success===true&&[0,1].includes(result.meta?.changes),"tf_permit_storage");
  if(result.meta.changes!==1)return {schema:"tf-accept-permit-v1",permitted:false,outcome:"handoff_or_existing_intent"};
  return {schema:"tf-accept-permit-v1",permitted:true,...request,nonce,expires:now+300};
}
export async function finishPermit(db,ownerId,hash,request,nonce,outcome,now){
  owner(ownerId);task(request);
  require(HASH.test(hash||"")&&HEX.test(nonce||"")&&["membership_verified","outcome_unknown"].includes(outcome)&&
    Number.isSafeInteger(now)&&now>0,"tf_permit_outcome");
  const state=outcome==="membership_verified"?"confirmed":"unknown";
  const result=await db.prepare(`UPDATE circleci_tf_acceptances SET state=?,updated_at=?
    WHERE invite_hash=? AND owner_id=? AND request_id=? AND run_id=? AND source_sha=? AND nonce=?
      AND state='intent' AND imported=0 AND updated_at<=?`).bind(state,now,hash,ownerId,request.request_id,
        request.run_id,request.source_commit,nonce,now).run();
  require(result.success===true,"tf_permit_storage");
  const current=await db.prepare("SELECT * FROM circleci_tf_acceptances WHERE invite_hash=?").bind(hash).first();
  require(current&&current.owner_id===ownerId&&current.request_id===request.request_id&&current.run_id===request.run_id&&
    current.source_sha===request.source_commit&&current.nonce===nonce&&current.state===state,"tf_outcome_immutable");
  return {ok:true,outcome};
}

export async function normalizeSource(rows,ownerId,pepper,observedAt){
  owner(ownerId);
  require(Array.isArray(rows)&&rows.length<=20&&Number.isSafeInteger(observedAt)&&observedAt>0,"tf_source_snapshot");
  const ordered=[],normalized=[],seen=new Set();
  for(const r of rows){
    require(r&&Object.keys(r).sort().join(",")==="created,invite,nonce,request_id,run_id,source_commit,state"&&
      /^[A-Za-z0-9_-]{6,80}$/.test(r.invite||"")&&!seen.has(r.invite)&&
      /^[1-9][0-9]{0,19}$/.test(r.run_id||"")&&SHA.test(r.source_commit||"")&&
      Number.isSafeInteger(r.created)&&r.created>=0&&r.created<=observedAt&&
      ["membership_verified","intent","outcome_unknown"].includes(r.state),"tf_source_row");
    seen.add(r.invite);
    const canonical={invite:r.invite,request_id:r.request_id,run_id:r.run_id,source_commit:r.source_commit,
      nonce:r.nonce,created:r.created,state:r.state};
    const historical=r.request_id==="historical";
    if(historical)require(r.invite==="yoNuHexZ"&&r.run_id==="42692803345"&&
      r.source_commit==="688b5356aa33a9653517f62445856a08c72819c4"&&r.nonce===""&&
      r.created===0&&r.state==="membership_verified","tf_historical_provenance");
    else require(/^tf_[a-f0-9]{32}$/.test(r.request_id||"")&&HEX.test(r.nonce||""),"tf_source_request");
    const hashed=await inviteHash(r.invite,ownerId,pepper);
    const tag=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",
      new TextEncoder().encode("historical-import\0"+ownerId+"\0"+JSON.stringify(canonical)))),
      v=>v.toString(16).padStart(2,"0")).join("");
    normalized.push({invite_hash:hashed,state:{"membership_verified":"confirmed",intent:"intent",outcome_unknown:"unknown"}[r.state],
      request_id:historical?"tf_"+tag.slice(0,32):r.request_id,run_id:r.run_id,source_sha:r.source_commit,
      nonce:historical?tag.slice(32):r.nonce,created_at:r.created,updated_at:observedAt});
    ordered.push(canonical);
  }
  require(ordered.some(r=>r.invite==="yoNuHexZ"&&r.request_id==="historical"&&r.state==="membership_verified"),
    "tf_known_history_missing");
  ordered.sort((a,b)=>a.invite<b.invite?-1:a.invite>b.invite?1:0);
  const sourceDigest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode(JSON.stringify(ordered)))),v=>v.toString(16).padStart(2,"0")).join("");
  // Historical synthetic IDs are migration identifiers only, never authorization permits.
  return {rows:normalized,source_sha256:sourceDigest};
}
