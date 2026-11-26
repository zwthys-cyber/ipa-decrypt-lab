// Offline handoff is distinct from a stopped-source seal. It never claims the VPS was stopped.
import {need} from "./runtime-auth.mjs";
import {normalizeSource,stageHandoff,sealHandoff} from "./tf-acceptance.mjs";
export const RECOVERY_SCHEMA=[
 "CREATE TABLE IF NOT EXISTS runtime_offline_handoff(owner_id TEXT PRIMARY KEY,snapshot_sha256 TEXT NOT NULL,records_sha256 TEXT NOT NULL,token_sha256 TEXT NOT NULL,stage_source TEXT NOT NULL,captured_at INTEGER NOT NULL,created_at INTEGER NOT NULL,sealed_at INTEGER,activated_at INTEGER,fence_checked_at INTEGER,last_cron_tick_at INTEGER,fence_live INTEGER NOT NULL DEFAULT 0,legacy_rows INTEGER NOT NULL,held_rows INTEGER NOT NULL)",
 "CREATE TABLE IF NOT EXISTS runtime_offline_records(owner_id TEXT PRIMARY KEY,records_json TEXT NOT NULL)",
 "CREATE TABLE IF NOT EXISTS runtime_recovery_quarantine(owner_id TEXT NOT NULL,update_id INTEGER NOT NULL,source_json TEXT NOT NULL,created_at INTEGER NOT NULL,PRIMARY KEY(owner_id,update_id))"
].join(";")+";";
export const SNAPSHOT="28654b814e6f38c7dddd0fdb79d5d2202aa8915c23db840c9792e6c2ed4b16dd";
export const SESSION="8349899c8806e2481edfc6f8f532d6aaa855f32c241b86951a03ea62df799765";
const ORIGIN="https://ipazake-free-control-pilot.hahayesadd.workers.dev";
const workflows=[[407064604,"private-delivery.yml"],[411713917,"china-private-delivery.yml"],[412609354,"testflight-private-delivery.yml"],[407542960,"version-catalog.yml"],[412705779,"china-version-catalog.yml"]];
const historical={invite:"yoNuHexZ",request_id:"historical",run_id:"42692803345",source_commit:"688b5356aa33a9653517f62445856a08c72819c4",nonce:"",created:0,state:"membership_verified"};
export const sha=async s=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s))),b=>b.toString(16).padStart(2,"0")).join("");
const fields=(v,n)=>need(v&&Object.keys(v).sort().join(",")===n.split(",").sort().join(","),"runtime_recovery_fields");
async function get(send,url,token=null){
 const r=await send(url,{redirect:"manual",signal:AbortSignal.timeout(15000),headers:{accept:"application/json","user-agent":"ipa-offline-handoff/0.2",...(token?{authorization:"Bearer "+token}:{})}});
 const raw=await r.text();need(raw.length<=2097152,"runtime_recovery_provider_limit");
 return {status:r.status,value:JSON.parse(raw)};
}
export async function checkLegacy(env,send){
 need(typeof env.RUNTIME_GH_TOKEN==="string"&&env.RUNTIME_GH_TOKEN.length>=16,"runtime_recovery_github");
 for(const [id,path] of workflows){
  const base="https://api.github.com/repos/zwthys-cyber/ipa-decrypt-lab/actions/workflows/"+id;
  const a=await get(send,base,env.RUNTIME_GH_TOKEN);
  need(a.status===200&&a.value.id===id&&a.value.path===".github/workflows/"+path&&a.value.state==="disabled_manually","runtime_legacy_not_fenced");
  const b=await get(send,base+"/runs?per_page=100",env.RUNTIME_GH_TOKEN),v=b.value;
  need(b.status===200&&Number.isSafeInteger(v.total_count)&&Array.isArray(v.workflow_runs)&&
   v.total_count===v.workflow_runs.length&&v.total_count<=100&&v.workflow_runs.every(r=>r.status==="completed"),"runtime_legacy_not_fenced");
 }
}
async function checkTokens(env,old,send){
 const current=env.TELEGRAM_BOT_TOKEN||"",pattern=/^[0-9]{5,20}:[A-Za-z0-9_-]{30,90}$/;
 need(pattern.test(current)&&pattern.test(old||"")&&current!==old&&current.split(":")[0]===old.split(":")[0],"runtime_recovery_token");
 const fresh=await get(send,"https://api.telegram.org/bot"+current+"/getMe");
 need(fresh.status===200&&fresh.value.ok===true&&fresh.value.result?.is_bot===true&&
  String(fresh.value.result.id)===current.split(":")[0],"runtime_recovery_token");
 const stale=await get(send,"https://api.telegram.org/bot"+old+"/getMe");
 need([401,404].includes(stale.status)&&stale.value.ok===false&&stale.value.error_code===stale.status,"runtime_old_token_active");
}
function closed(env){need(env.RUNTIME_MODE==="staging"&&env.RUNTIME_EXPORT_ENABLED==="0"&&env.RUNTIME_TELEGRAM_ENABLED==="0"&&env.RUNTIME_BILLING_ENABLED==="0","runtime_recovery_entry_not_closed");}
async function readRecords(env){
 const v=await env.DB.prepare("SELECT records_json FROM runtime_offline_records WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 need(v,"runtime_recovery_missing");return {raw:v.records_json,value:JSON.parse(v.records_json)};
}
async function verifyImported(env,row){
 const records=await readRecords(env);
 need(await sha(records.raw)===row.records_sha256,"runtime_recovery_records_changed");
 const actual=(await env.DB.prepare("SELECT * FROM runtime_legacy_tasks").all()).results||[];
 need(actual.length===row.legacy_rows&&actual.reduce((n,r)=>n+r.held,0)===row.held_rows,"runtime_recovery_rows_changed");
 const indexed=new Map(actual.map(r=>[r.owner_id+":"+r.request_id,r]));
 for(const expected of records.value.legacy_tasks){
  const current=indexed.get(expected.owner_id+":"+expected.request_id);
  need(current&&Object.keys(expected).every(k=>current[k]===expected[k]),"runtime_recovery_rows_changed");
 }
 return records.value;
}
export async function stageRecovery(env,packet,now,send){
 closed(env);fields(packet,"schema,source_run,snapshot_sha256,records_json,records_sha256,captured_at,old_token,tf_history_verified");
 need(packet.schema==="circleci-offline-stage-v1"&&packet.source_run===45866115288&&packet.snapshot_sha256===SNAPSHOT&&
  /^[a-f0-9]{64}$/.test(packet.records_sha256||"")&&typeof packet.records_json==="string"&&packet.records_json.length<=1048576&&
  await sha(packet.records_json)===packet.records_sha256&&Number.isSafeInteger(packet.captured_at)&&packet.captured_at>0&&packet.captured_at<=now&&
  packet.tf_history_verified===true,"runtime_recovery_packet");
 await checkTokens(env,packet.old_token,send);await checkLegacy(env,send);
 need(/^[a-f0-9]{64}$/.test(env.RUNTIME_TF_HMAC_KEY||""),"runtime_recovery_hmac");
 const records=JSON.parse(packet.records_json);fields(records,"legacy_tasks,updates,metadata,private_returns,acceptance_rows");
 need(Array.isArray(records.legacy_tasks)&&records.legacy_tasks.length===29&&
  ["updates","metadata","private_returns","acceptance_rows"].every(k=>Array.isArray(records[k])&&records[k].length<=5000)&&
  records.acceptance_rows.length===0,"runtime_recovery_inventory");
 const scope=await sha("telegram-owner:"+env.RUNTIME_OWNER_ID),seen=new Set();let held=0;
 for(const r of records.legacy_tasks){
  fields(r,"owner_id,request_id,profile,target,state,created_at,source_json,held");
  need(typeof r.source_json==="string"&&r.source_json.length<=16384,"runtime_recovery_row");
  const original=JSON.parse(r.source_json);fields(original,"scope,rid,app,state,at,created");
  need(/^[a-f0-9]{64}$/.test(original.scope||"")&&r.owner_id===(original.scope===scope?env.RUNTIME_OWNER_ID:"legacy:"+original.scope)&&
   /^(?:cn_|tf_)?[a-f0-9]{32}$/.test(r.request_id||"")&&r.request_id===original.rid&&r.target===original.app&&typeof r.target==="string"&&
   r.target.length<=1024&&["pending","sending","delivered","closed","cancelled"].includes(r.state)&&r.state===original.state&&
   Number.isSafeInteger(r.created_at)&&r.created_at===original.created&&r.created_at>=0&&
   Number.isSafeInteger(original.at)&&original.at>=r.created_at&&original.at<=now&&
   r.profile===(r.request_id.startsWith("tf_")?"tf":r.request_id.startsWith("cn_")?"cn":"default")&&
   r.held===Number(["pending","sending"].includes(r.state))&&!seen.has(r.owner_id+":"+r.request_id),"runtime_recovery_row");
  held+=r.held;seen.add(r.owner_id+":"+r.request_id);
 }
 need(held===2,"runtime_recovery_inventory");
 for(const u of records.updates){fields(u,"scope,uid,at,done");need(/^[a-f0-9]{64}$/.test(u.scope||"")&&Number.isSafeInteger(u.uid)&&u.uid>=0&&[0,1].includes(u.done),"runtime_recovery_updates");}
 for(const m of records.metadata){fields(m,"scope,name,value");need(/^[a-f0-9]{64}$/.test(m.scope||"")&&typeof m.name==="string"&&typeof m.value==="string","runtime_recovery_metadata");}
 need(records.private_returns.every(r=>["intent","confirmed"].includes(r.state)),"runtime_recovery_returns");
 const token=await sha(env.TELEGRAM_BOT_TOKEN);
 const queries=[
  env.DB.prepare("INSERT INTO runtime_offline_handoff(owner_id,snapshot_sha256,records_sha256,token_sha256,stage_source,captured_at,created_at,legacy_rows,held_rows) VALUES(?,?,?,?,?,?,?,29,2) ON CONFLICT DO NOTHING")
   .bind(env.RUNTIME_OWNER_ID,SNAPSHOT,packet.records_sha256,token,env.RUNTIME_SOURCE_SHA,packet.captured_at,now),
  env.DB.prepare("INSERT INTO runtime_offline_records(owner_id,records_json) SELECT ?,? WHERE EXISTS(SELECT 1 FROM runtime_offline_handoff WHERE owner_id=? AND records_sha256=? AND token_sha256=?) ON CONFLICT DO NOTHING")
   .bind(env.RUNTIME_OWNER_ID,packet.records_json,env.RUNTIME_OWNER_ID,packet.records_sha256,token)];
 for(const r of records.legacy_tasks)queries.push(env.DB.prepare("INSERT INTO runtime_legacy_tasks(owner_id,request_id,profile,target,state,created_at,source_json,held) SELECT ?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM runtime_offline_handoff WHERE owner_id=? AND records_sha256=? AND token_sha256=?) ON CONFLICT DO NOTHING")
  .bind(r.owner_id,r.request_id,r.profile,r.target,r.state,r.created_at,r.source_json,r.held,env.RUNTIME_OWNER_ID,packet.records_sha256,token));
 const writes=await env.DB.batch(queries);need(writes.every(x=>x.success===true),"runtime_recovery_storage");
 const saved=await env.DB.prepare("SELECT * FROM runtime_offline_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 need(saved?.snapshot_sha256===SNAPSHOT&&saved.records_sha256===packet.records_sha256&&saved.token_sha256===token,"runtime_recovery_immutable");
 await verifyImported(env,saved);
 const pepper=Uint8Array.from(env.RUNTIME_TF_HMAC_KEY.match(/../g),x=>parseInt(x,16));
 const tf=await normalizeSource([historical],env.RUNTIME_OWNER_ID,pepper,saved.created_at);
 const evidence={snapshot_sha256:SNAPSHOT,session_sha256:SESSION,source_sha:saved.stage_source};
 const existing=await env.DB.prepare("SELECT * FROM circleci_tf_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 if(existing?.sealed_at)need(existing.snapshot_sha256===SNAPSHOT&&existing.session_sha256===SESSION&&existing.source_sha===saved.stage_source,"runtime_recovery_tf");
 else await stageHandoff(env.DB,env.RUNTIME_OWNER_ID,evidence,tf.rows);
 return {ok:true,staged:true,legacy_rows:29,held_rows:2};
}
export async function sealRecovery(env,packet,now,send){
 closed(env);fields(packet,"records_sha256,old_token");
 const row=await env.DB.prepare("SELECT * FROM runtime_offline_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 need(row&&now>=row.created_at&&row.records_sha256===packet.records_sha256&&row.token_sha256===await sha(env.TELEGRAM_BOT_TOKEN),"runtime_recovery_missing");
 await verifyImported(env,row);await checkTokens(env,packet.old_token,send);await checkLegacy(env,send);
 const tf=await env.DB.prepare("SELECT * FROM circleci_tf_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 need(tf?.ready===1&&tf.snapshot_sha256===SNAPSHOT&&tf.session_sha256===SESSION&&tf.source_sha===row.stage_source,"runtime_recovery_tf");
 if(!tf.sealed_at)await sealHandoff(env.DB,env.RUNTIME_OWNER_ID,{snapshot_sha256:SNAPSHOT,session_sha256:SESSION,source_sha:row.stage_source},now);
 const written=await env.DB.prepare("UPDATE runtime_offline_handoff SET sealed_at=COALESCE(sealed_at,?),activated_at=COALESCE(activated_at,?),fence_checked_at=? WHERE owner_id=?")
  .bind(now,now+15,now,env.RUNTIME_OWNER_ID).run();need(written.success===true,"runtime_recovery_storage");
 return {ok:true,sealed:true};
}
export async function refreshRecoveryFence(env,now,send){
 const row=await env.DB.prepare("SELECT * FROM runtime_offline_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 if(!row?.sealed_at)return;
 let live=0;
 try{
  need(row.token_sha256===await sha(env.TELEGRAM_BOT_TOKEN)&&env.RUNTIME_BILLING_ENABLED==="0","runtime_recovery_token");
  await verifyImported(env,row);await checkLegacy(env,send);
  const hook=await get(send,"https://api.telegram.org/bot"+env.TELEGRAM_BOT_TOKEN+"/getWebhookInfo");
  need(hook.status===200&&hook.value.ok===true&&hook.value.result?.url===ORIGIN+"/telegram","runtime_recovery_webhook");
  live=1;
 }catch{}
 const result=await env.DB.prepare("UPDATE runtime_offline_handoff SET fence_live=?,fence_checked_at=?,last_cron_tick_at=? WHERE owner_id=?")
  .bind(live,now,now,env.RUNTIME_OWNER_ID).run();need(result.success===true,"runtime_recovery_storage");
}
export async function offlineEntry(env,now=Math.floor(Date.now()/1000)){
 const row=await env.DB.prepare("SELECT * FROM runtime_offline_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 need(row&&row.sealed_at&&row.snapshot_sha256===SNAPSHOT&&row.token_sha256===await sha(env.TELEGRAM_BOT_TOKEN)&&
  env.RUNTIME_BILLING_ENABLED==="0"&&row.activated_at<=now&&row.fence_live===1&&
  row.last_cron_tick_at>=row.sealed_at&&row.fence_checked_at>=now-180,"runtime_handoff_required");
 const count=await env.DB.prepare("SELECT count(*) n,COALESCE(sum(held),0) held FROM runtime_legacy_tasks").first();
 need(count.n===row.legacy_rows&&count.held===row.held_rows,"runtime_legacy_import_required");
 return {offline:true,snapshot_sha256:SNAPSHOT,session_sha256:SESSION,legacy_rows:row.legacy_rows,held_rows:row.held_rows,
  telegram_update_floor:0,activated_at:row.activated_at,sealed_at:row.sealed_at};
}
export async function recoveryStatus(env){
 const row=await env.DB.prepare("SELECT * FROM runtime_offline_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 if(!row)return {ok:true,staged:false};
 const records=await verifyImported(env,row);
 const tf=await env.DB.prepare("SELECT ready,sealed_at FROM circleci_tf_handoff WHERE owner_id=?").bind(env.RUNTIME_OWNER_ID).first();
 const delivery=await env.DB.prepare("SELECT j.state,j.finished_at,j.file_id,n.state notice FROM runtime_jobs j LEFT JOIN runtime_notifications n ON n.job_id=j.job_id WHERE j.job_id='pilot_267d28bb7688af8bbc132595f7009a07'").first();
 return {ok:true,staged:true,sealed:!!row.sealed_at,records_readback_verified:true,legacy_rows:row.legacy_rows,held_rows:row.held_rows,
  update_rows:records.updates.length,metadata_rows:records.metadata.length,private_return_rows:records.private_returns.length,
  tf_sealed:tf?.ready===1&&!!tf.sealed_at,activated_at:row.activated_at,last_cron_tick_at:row.last_cron_tick_at,
  fence_live:row.fence_live===1,token_bound:row.token_sha256===await sha(env.TELEGRAM_BOT_TOKEN),
  known_delivery_preserved:delivery?.state==="completed"&&!!delivery.finished_at&&!!delivery.file_id&&delivery.notice==="sent",
  source_disabled_verified:false,recovery_gap_held:true,automatic_replay:false};
}
export async function quarantineUpdate(env,update,now){
 const encoded=JSON.stringify(update);
 const result=await env.DB.prepare("INSERT INTO runtime_recovery_quarantine(owner_id,update_id,source_json,created_at) VALUES(?,?,?,?) ON CONFLICT DO NOTHING")
  .bind(env.RUNTIME_OWNER_ID,update.update_id,encoded,now).run();need(result.success===true,"runtime_recovery_quarantine");
 const row=await env.DB.prepare("SELECT source_json FROM runtime_recovery_quarantine WHERE owner_id=? AND update_id=?").bind(env.RUNTIME_OWNER_ID,update.update_id).first();
 need(row?.source_json===encoded,"runtime_recovery_update_conflict");
}
