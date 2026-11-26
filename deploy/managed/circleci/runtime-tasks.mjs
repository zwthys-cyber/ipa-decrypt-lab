// Real-task admission and immutable verification. Source handoff is a separate, explicit operation.
import {canaryWindow} from "./runtime-canary.mjs";
import {need} from "./runtime-auth.mjs";
const HEX=/^[a-f0-9]{64}$/,SHA=/^[a-f0-9]{40}$/;
export const TASK_SCHEMA=`
CREATE TABLE IF NOT EXISTS runtime_entry_handoff(
 owner_id TEXT PRIMARY KEY,snapshot_sha256 TEXT NOT NULL,session_sha256 TEXT NOT NULL,
 old_service_stopped_at INTEGER NOT NULL,billing_verified_at INTEGER NOT NULL,sealed_at INTEGER NOT NULL,
 legacy_rows INTEGER NOT NULL,held_rows INTEGER NOT NULL,telegram_update_floor INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS runtime_legacy_tasks(
 owner_id TEXT NOT NULL,request_id TEXT NOT NULL,profile TEXT NOT NULL,target TEXT NOT NULL,state TEXT NOT NULL,
 created_at INTEGER NOT NULL,source_json TEXT NOT NULL,held INTEGER NOT NULL CHECK(held IN (0,1)),
 PRIMARY KEY(owner_id,request_id)
);
CREATE TABLE IF NOT EXISTS runtime_export_proofs(job_id TEXT PRIMARY KEY,receipt_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_task_progress(job_id TEXT PRIMARY KEY,stage TEXT NOT NULL,updated_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS runtime_cancel_intents(job_id TEXT PRIMARY KEY,created_at INTEGER NOT NULL,outcome TEXT NOT NULL);
`;
export const ACTIVE=["dispatch_intent","dispatch_unknown","submitted","running","uploading","link_ready","cancel_intent","cancel_pending","failed_pending"];
export function version(value){
 need(typeof value==="string"&&value.length<=32&&(!value||/^[1-9][0-9]{5,19}$/.test(value)||/^[0-9]{1,5}(?:\.[0-9]{1,5}){0,4}$/.test(value)),"runtime_version");
 return value;
}
export async function requireEntry(env){
 need(env.RUNTIME_MODE==="production"&&env.RUNTIME_EXPORT_ENABLED==="1","runtime_entry_disabled");
 need(Number.isSafeInteger(Number(env.RUNTIME_OWNER_ID))&&Number(env.RUNTIME_OWNER_ID)>0,"runtime_owner_configuration");
 const window=await canaryWindow(env,Math.floor(Date.now()/1000));if(window)return window;
 const row=await env.DB.prepare("SELECT * FROM runtime_entry_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 need(row&&HEX.test(row.snapshot_sha256||"")&&HEX.test(row.session_sha256||"")&&
  row.old_service_stopped_at>0&&row.billing_verified_at>0&&row.sealed_at>=row.old_service_stopped_at&&
  row.sealed_at>=row.billing_verified_at&&Number.isSafeInteger(row.legacy_rows)&&row.legacy_rows>=0&&
  Number.isSafeInteger(row.held_rows)&&row.held_rows>=0&&Number.isSafeInteger(row.telegram_update_floor)&&row.telegram_update_floor>=0,"runtime_handoff_required");
 const counts=await env.DB.prepare("SELECT count(*) total,COALESCE(sum(held),0) held FROM runtime_legacy_tasks").first();
 need(counts.total===row.legacy_rows&&counts.held===row.held_rows,"runtime_legacy_import_required");
 return row;
}
export function exportRequest(value){
 need(value&&Object.keys(value).sort().join(",")==="profile,request_id,target,version"&&["default","cn","tf"].includes(value.profile),"runtime_export_request");
 const prefix={default:"",cn:"cn_",tf:"tf_"}[value.profile];
 need(new RegExp("^"+prefix+"[a-f0-9]{32}$").test(value.request_id||""),"runtime_export_namespace");
 need(typeof value.target==="string"&&(value.profile==="tf"?/^[A-Za-z0-9_-]{6,80}$/:/^[1-9][0-9]{4,19}$/).test(value.target),"runtime_export_target");
 version(value.version);need(value.profile!=="tf"||value.version==="","runtime_tf_version");
 return value;
}
const canonical=value=>JSON.stringify(Object.fromEntries(Object.keys(value).sort().map(k=>[k,value[k]])));
export async function admitExport(env,value,now){
 const entry=await requireEntry(env);exportRequest(value);
 if(entry.canary)need(value.profile==="default"&&value.request_id===entry.request_id&&value.target===entry.target&&value.version==="","runtime_canary_request_binding");
 if(value.profile==="tf"){
  const handoff=await env.DB.prepare("SELECT ready,sealed_at,snapshot_sha256,session_sha256 FROM circleci_tf_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
  need(handoff?.ready===1&&handoff.sealed_at>0&&handoff.snapshot_sha256===entry.snapshot_sha256&&handoff.session_sha256===entry.session_sha256&&/^[a-f0-9]{64}$/.test(env.RUNTIME_TF_HMAC_KEY||""),"runtime_tf_handoff_required");
 }
 const limit=env.RUNTIME_DAILY_LIMIT===undefined?3:Number(env.RUNTIME_DAILY_LIMIT);
 need(Number.isSafeInteger(limit)&&limit>=1&&limit<=20,"runtime_quota_configuration");
 const legacy=await env.DB.prepare("SELECT request_id FROM runtime_legacy_tasks WHERE request_id=? AND owner_id=?").bind(value.request_id,env.RUNTIME_OWNER_ID).first();
 need(!legacy,"runtime_historical_request_held");
 const start=Math.floor(now/86400)*86400;
 const savedQuota=entry.canary?await env.DB.prepare("SELECT count(*) n FROM runtime_canary_legacy WHERE source_sha=? AND owner_id=? AND created_at>=? AND created_at<?").bind(env.RUNTIME_SOURCE_SHA,env.RUNTIME_OWNER_ID,start,start+86400).first():{n:0};
 const raw=await crypto.subtle.digest("SHA-256",new TextEncoder().encode("managed-export\0"+env.RUNTIME_OWNER_ID+"\0"+value.request_id));
 const id="pilot_"+Array.from(new Uint8Array(raw),x=>x.toString(16).padStart(2,"0")).join("").slice(0,32);
 const result=await env.DB.prepare(`INSERT INTO runtime_jobs
  (job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline)
  SELECT ?,?,?,?,'export',?,?,?,'waiting',?,?
  WHERE ((SELECT count(*) FROM runtime_jobs WHERE owner_id=? AND kind='export' AND NOT EXISTS(SELECT 1 FROM runtime_catalog_specs s WHERE s.job_id=runtime_jobs.job_id) AND created_at>=? AND created_at<?)
   +(SELECT count(*) FROM runtime_legacy_tasks WHERE owner_id=? AND created_at>=? AND created_at<?)+?)<?
   AND (SELECT count(*) FROM runtime_jobs WHERE owner_id=? AND kind='export' AND state='waiting')<30
  ON CONFLICT DO NOTHING`).bind(id,env.RUNTIME_OWNER_ID,value.request_id,value.profile,value.target,value.version,
   env.RUNTIME_SOURCE_SHA,now,Math.min(now+3600,entry.lease_deadline||now+3600),env.RUNTIME_OWNER_ID,start,start+86400,env.RUNTIME_OWNER_ID,start,start+86400,savedQuota.n,limit,env.RUNTIME_OWNER_ID).run();
 need(result.success===true,"runtime_admission_storage");
 const row=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE request_id=? AND owner_id=?").bind(value.request_id,env.RUNTIME_OWNER_ID).first();
 need(row,"runtime_daily_or_queue_limit");
 need(row.job_id===id&&row.kind==="export"&&(row.source_sha===env.RUNTIME_SOURCE_SHA||["completed","closed","cancelled"].includes(row.state))&&
  ["profile","target","version"].every(key=>row[key]===value[key]),"runtime_request_immutable");
 return row;
}
export function verifyReceipt(task,value){
 need(value&&typeof value==="object"&&!Array.isArray(value)&&value.schema==="circleci-private-delivery-v1"&&
  value.status==="encrypted_artifact_ready"&&value.provider==="circleci"&&value.job_id===task.job_id&&
  value.request_id===task.request_id&&value.run_id===task.run_id&&value.worker_job_id===task.worker_job_id&&
  value.source_commit===task.source_sha&&value.account_profile===task.profile&&value.requested_version===task.version&&
  value.plaintext_verified===true&&value.account_data_removed===true&&value.plaintext_published===false&&
  value.runtime_verified===false&&value.recipient==="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"&&
  Number.isSafeInteger(value.encrypted_images)&&value.encrypted_images>0&&
  Number.isSafeInteger(value.decrypted_pages)&&value.decrypted_pages>0&&
  Number.isSafeInteger(value.plaintext_bytes)&&value.plaintext_bytes>0&&value.plaintext_bytes<=2000000000&&
  Number.isSafeInteger(value.ciphertext_bytes)&&value.ciphertext_bytes>value.plaintext_bytes&&
  value.ciphertext_bytes<=2002097152&&HEX.test(value.plaintext_sha256||"")&&HEX.test(value.ciphertext_sha256||"")&&
  typeof value.filename==="string"&&value.filename.length<=160&&!value.filename.startsWith(".")&&
  /^[\p{L}\p{N} ._()\-]+\.ipa$/iu.test(value.filename),"runtime_export_proof");
 const fields=["schema","status","provider","job_id","request_id","run_id","worker_job_id","source_commit","account_profile",
  "app_id","requested_version","resolved_version","external_version_id","plaintext_verified","runtime_verified",
  "account_data_removed","plaintext_published","encrypted_images","decrypted_pages","plaintext_bytes","plaintext_sha256",
  "ciphertext_bytes","ciphertext_sha256","recipient","filename"];
 if(task.profile==="tf"){
  fields.push("target_type","testflight_invite");
  need(value.target_type==="testflight"&&value.testflight_invite===task.target&&
   /^[1-9][0-9]{4,19}$/.test(value.app_id||"")&&value.filename.includes("_Beta_"),"runtime_tf_proof");
 }else need(value.app_id===task.target,"runtime_app_proof");
 need(Object.keys(value).sort().join(",")===fields.sort().join(","),"runtime_proof_fields");
 version(value.resolved_version);version(value.external_version_id);
 if(task.version){
  const external=/^[1-9][0-9]{5,19}$/.test(task.version);
  need(/^[1-9][0-9]{5,19}$/.test(value.external_version_id)&&value.resolved_version&&
   !/^[1-9][0-9]{5,19}$/.test(value.resolved_version)&&
   (external?value.external_version_id===task.version:value.resolved_version===task.version),"runtime_version_proof");
 }
 return canonical(value);
}
export async function saveExportProof(db,task,value){
 const encoded=verifyReceipt(task,value);
 need(["running","uploading"].includes(task.state),"runtime_proof_state");
 const queries=[
  db.prepare("INSERT INTO runtime_export_proofs(job_id,receipt_json) VALUES(?,?) ON CONFLICT DO NOTHING").bind(task.job_id,encoded),
  db.prepare(`UPDATE runtime_jobs SET state='uploading',plaintext_sha256=?,plaintext_bytes=?,filename=?
   WHERE job_id=? AND worker_job_id=? AND state IN ('running','uploading')
    AND EXISTS(SELECT 1 FROM runtime_export_proofs WHERE job_id=? AND receipt_json=?)
    AND (plaintext_sha256 IS NULL OR (plaintext_sha256=? AND plaintext_bytes=? AND filename=?))`)
   .bind(value.plaintext_sha256,value.plaintext_bytes,value.filename,task.job_id,task.worker_job_id,task.job_id,encoded,
    value.plaintext_sha256,value.plaintext_bytes,value.filename)];
 const result=await db.batch(queries);
 need(result.every(x=>x.success===true)&&result[1].meta?.changes===1,"runtime_proof_immutable");
}
export async function verifyFinishedExport(db,task,value){
 need(value&&value.private_delivery,"runtime_delivery_required");
 const base={...value};delete base.private_delivery;delete base.acceptance_attempted;
 const encoded=verifyReceipt(task,base),record=value.private_delivery;
 const saved=await db.prepare("SELECT receipt_json FROM runtime_export_proofs WHERE job_id=?").bind(task.job_id).first();
 const upload=await db.prepare("SELECT stage,state_json FROM runtime_uploads WHERE job_id=?").bind(task.job_id).first();
 need(saved?.receipt_json===encoded&&upload?.stage==="registered"&&task.state==="link_ready"&&
  record&&Object.keys(record).sort().join(",")==="bytes,file_id,filename,sha256"&&record.file_id===task.file_id&&
  record.filename===task.filename&&record.bytes===task.plaintext_bytes&&record.sha256===task.plaintext_sha256&&
  JSON.parse(upload.state_json).file_id===record.file_id,"runtime_delivery_required");
 if(task.profile==="tf")need(typeof value.acceptance_attempted==="boolean","runtime_tf_finish");
}
