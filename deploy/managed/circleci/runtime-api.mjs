// Staged managed-runtime API. Real exports and Telegram admission remain disabled until handoff.
import {CATALOG_SCHEMA,catalogTask,openCatalog,catalogAction,saveCatalog,completeCatalogNotices} from "./runtime-catalog.mjs";
import {CANARY_SCHEMA,installCanary,revokeCanary} from "./runtime-canary.mjs";
import {NOTIFY_SCHEMA,notifyOwner} from "./runtime-notify.mjs";
import {TASK_SCHEMA,requireEntry,admitExport,saveExportProof,verifyFinishedExport} from "./runtime-tasks.mjs";
import {SCHEMA as TF_SCHEMA,claimPermit,finishPermit,inviteHash} from "./tf-acceptance.mjs";
import {TRUST} from "./oidc.mjs";
import {RUNTIME_SCHEMA} from "./runtime-schema.mjs";
import {UPLOAD_SCHEMA,readUploadJournal,writeUploadJournal,confirmUploadRegistration} from "./runtime-upload.mjs";
import {DRIVE_FIXTURE,FIXTURE_SCHEMA} from "./runtime-fixture.mjs";
import {uploadAccess,verifyOwnedUpload,cleanupFixture} from "./runtime-drive.mjs";
import {need,UUID,publicJSON,circleIdentity,githubIdentity} from "./runtime-auth.mjs";
import {requestRuntimeLease,pendingRuntimeLease,publishRuntimeLease,readRuntimeLease,closeRuntimeLease} from "./runtime-lease.mjs";
export const schemaStatements=()=>[RUNTIME_SCHEMA,UPLOAD_SCHEMA,FIXTURE_SCHEMA,TASK_SCHEMA,TF_SCHEMA,NOTIFY_SCHEMA,CANARY_SCHEMA,CATALOG_SCHEMA].flatMap(sql=>sql.split(";")).map(sql=>sql.trim()).filter(Boolean);
const PREFIX="/v2/runtime/";
const JOB=/^pilot_[a-f0-9]{32}$/,SHA=/^[a-f0-9]{40}$/;
const ORIGIN="https://ipazake-free-control-pilot.hahayesadd.workers.dev";
function reply(status,value={ok:false}){return Response.json(value,{status,headers:{"cache-control":"no-store"}});}
async function body(request,fields,limit=4096){
 need(request.headers.get("content-type")==="application/json"&&request.body,"runtime_body");
 const reader=request.body.getReader();let size=0;const chunks=[];
 try{for(;;){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;
   need(size<=limit,"runtime_body_limit");chunks.push(part.value);}}
 finally{try{await reader.cancel();}catch{}reader.releaseLock();}
 const raw=new Uint8Array(size);let at=0;for(const part of chunks){raw.set(part,at);at+=part.byteLength;}
 const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(raw));
 need(value&&typeof value==="object"&&!Array.isArray(value)&&
  Object.keys(value).sort().join(",")===["_source",...fields].sort().join(","),"runtime_fields");need(value._source===request.headers.get("x-ipazake-source-sha"),"runtime_source_not_ready");return value;
}
async function admin(request,env){
 const supplied=request.headers.get("x-ipazake-control-token")||"";
 need(/^[A-Za-z0-9_-]{43,128}$/.test(env.CIRCLECI_CONTROL_TOKEN||"")&&
  ![env.CIRCLECI_API_TOKEN,env.RUNTIME_GH_TOKEN].includes(env.CIRCLECI_CONTROL_TOKEN),"runtime_admin_configuration");
 const digest=async value=>new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(value)));
 const [a,b]=await Promise.all([digest(supplied),digest(env.CIRCLECI_CONTROL_TOKEN)]);
 let difference=0;for(let i=0;i<a.length;i++)difference|=a[i]^b[i];
 need(difference===0,"runtime_admin_authentication");
}
async function task(env,id,currentSource=true){
 need(JOB.test(id||""),"runtime_job_id");
 const value=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE job_id=? AND owner_id=?")
  .bind(id,env.RUNTIME_OWNER_ID).first();
 need(value&&(!currentSource||value.source_sha===env.RUNTIME_SOURCE_SHA),"runtime_job_binding");
 const fixture=await env.DB.prepare("SELECT * FROM runtime_drive_fixtures WHERE job_id=?").bind(id).first();
 return {...await catalogTask(env.DB,value),drive_fixture:fixture?1:0,fixture_authorized:fixture?.authorized||0,cleanup_state:fixture?.cleanup_state||null};
}
async function sendAPI(send,url,token,data){
 return send(url,{method:"POST",redirect:"manual",signal:AbortSignal.timeout(15000),
  headers:{"user-agent":"ipa-decrypt-managed-runtime/0.2",authorization:"Bearer "+token,accept:"application/json",
   "content-type":"application/json"},body:JSON.stringify(data)});
}
export async function dispatchNative(env,id,now,send){
 const nonce=crypto.randomUUID().replaceAll("-","");
 const result=await env.DB.prepare(`UPDATE runtime_jobs SET state='dispatch_intent',dispatch_nonce=?
  WHERE job_id=? AND owner_id=? AND state='waiting'
   AND deadline>? AND source_sha=?
   AND NOT EXISTS(SELECT 1 FROM runtime_jobs WHERE state IN ('dispatch_intent','dispatch_unknown','submitted','running','uploading','link_ready','cancel_intent','cancel_pending','failed_pending'))`)
  .bind(nonce,id,env.RUNTIME_OWNER_ID,now,env.RUNTIME_SOURCE_SHA).run();
 need(result.success===true,"runtime_dispatch_storage");
 if(result.meta?.changes!==1)return;
 try{
  const response=await sendAPI(send,"https://circleci.com/api/v3/runs",env.CIRCLECI_API_TOKEN,
   {data:{attributes:{config:{branch:TRUST.ref.slice(11)},checkout:{branch:TRUST.ref.slice(11)},
    parameters:{managed_runtime:true,managed_job:id,managed_source:env.RUNTIME_SOURCE_SHA,managed_origin:ORIGIN,
     dispatch_probe:false,build_native_runtime:false,runtime_consumer:false,validate_arm64_archive:false}},
    references:{pipeline:{id:TRUST.definition}}}});
  need(response.status===201,"runtime_dispatch_unknown");
  const raw=await response.text();need(raw.length<=65536,"runtime_dispatch_response");
  const run=JSON.parse(raw)?.data?.id;need(UUID.test(run||""),"runtime_dispatch_unknown");
  const stored=await env.DB.prepare(`UPDATE runtime_jobs SET state='submitted',run_id=?
   WHERE job_id=? AND dispatch_nonce=? AND state='dispatch_intent'`).bind(run,id,nonce).run();
  need(stored.success===true&&stored.meta?.changes===1,"runtime_dispatch_unknown");
 }catch{
  await env.DB.prepare("UPDATE runtime_jobs SET state='dispatch_unknown' WHERE job_id=? AND dispatch_nonce=? AND state='dispatch_intent'")
   .bind(id,nonce).run();
 }
}
async function promoteNext(env,now,send){
 await requireEntry(env);
 const finished=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE owner_id=? AND finished_at IS NOT NULL AND state IN ('running','uploading','link_ready')").bind(env.RUNTIME_OWNER_ID).all();
 for(const row of finished.results||[])await reconcileFixture(env,row,send);
 await env.DB.prepare("UPDATE runtime_jobs SET state='closed' WHERE owner_id=? AND kind='export' AND state='waiting' AND deadline<=?").bind(env.RUNTIME_OWNER_ID,now).run();
 const next=await env.DB.prepare("SELECT job_id FROM runtime_jobs WHERE owner_id=? AND source_sha=? AND kind='export' AND state='waiting' AND deadline>? ORDER BY created_at,job_id LIMIT 1")
  .bind(env.RUNTIME_OWNER_ID,env.RUNTIME_SOURCE_SHA,now).first();
 if(next)await dispatchNative(env,next.job_id,now,send);
}
async function dispatchPublisher(env,row,context,now,send){
 need(typeof env.RUNTIME_GH_TOKEN==="string"&&env.RUNTIME_GH_TOKEN.length>=16,"runtime_publisher_configuration");
 const saved=await env.DB.prepare(`INSERT INTO runtime_publisher_dispatches(job_id,state,created_at)
  VALUES(?,'intent',?) ON CONFLICT(job_id) DO NOTHING`).bind(row.job_id,now).run();
 need(saved.success===true,"runtime_publisher_storage");if(saved.meta?.changes!==1)return;
 let state="unknown";
 try{
  const response=await sendAPI(send,
   "https://api.github.com/repos/zwthys-cyber/ipa-decrypt-lab/actions/workflows/circleci-secret-lease.yml/dispatches",
   env.RUNTIME_GH_TOKEN,{ref:TRUST.ref.slice(11),inputs:{job_id:row.job_id,profile:context.profile,source:row.source_sha}});
  if(response.status===204)state="submitted";
  if(response.body)await response.body.cancel();
 }catch{}
 await env.DB.prepare("UPDATE runtime_publisher_dispatches SET state=? WHERE job_id=? AND state='intent'")
  .bind(state,row.job_id).run();
}

async function reconcileFixture(env,row,send){
 row=await catalogTask(env.DB,row);
 if(!row.run_id||!["submitted","running","uploading","link_ready","cancel_intent","cancel_pending","failed_pending"].includes(row.state))return;
 const run=(await publicJSON(send,"https://circleci.com/api/v3/runs/"+row.run_id)).data;
 const refs=run?.references,vcs=refs?.event?.attributes?.vcs;
 need(run?.id===row.run_id&&refs?.project?.id===TRUST.project&&refs?.pipeline?.id===TRUST.definition&&
  vcs?.revision===row.source_sha&&vcs?.origin_repository_url==="https://"+TRUST.source&&
  vcs?.target_repository_url==="https://"+TRUST.source&&vcs?.branch===TRUST.ref.slice(11),"runtime_terminal_binding");
 if(run?.attributes?.phase!=="ended")return;
 if(run.attributes.current_outcome==="succeeded"&&row.finished_at!==null&&
  (row.kind==="fixture"?row.fixture_verified===1:row.kind==="catalog"?!!row.catalog.result_json:!!row.file_id)){
  await env.DB.prepare("UPDATE runtime_jobs SET state='completed' WHERE job_id=? AND state IN ('running','uploading','link_ready')").bind(row.job_id).run();
 }else if(["failed","canceled","cancelled","error"].includes(run.attributes.current_outcome)||row.state==="failed_pending"||["cancel_intent","cancel_pending"].includes(row.state)){
  // Only a known, ended, credential-free validation. Original ID, nonce and history are retained.
  await env.DB.prepare("UPDATE runtime_jobs SET state='closed' WHERE job_id=? AND state IN ('submitted','running','uploading','link_ready','cancel_intent','cancel_pending','failed_pending')")
   .bind(row.job_id).run();
  await closeRuntimeLease(env.DB,row,Math.floor(Date.now()/1000));
 }
}

export async function handleRuntimeV2(request,env,now=Math.floor(Date.now()/1000),send=(url,init)=>globalThis.fetch(url,init)){
 const url=new URL(request.url),path=url.pathname.slice(PREFIX.length);
 if(url.search||!url.pathname.startsWith(PREFIX))return reply(404);
 if(request.method!=="POST"&&!(request.method==="GET"&&path==="ready"))return reply(404);
 if(!["staging","production"].includes(env.RUNTIME_MODE)||env.RUNTIME_CONTROL_ORIGIN!==ORIGIN||url.origin!==ORIGIN||
  !SHA.test(env.RUNTIME_SOURCE_SHA||"")||!/^[1-9][0-9]{0,15}$/.test(env.RUNTIME_OWNER_ID||"")||!env.DB?.prepare)return reply(503);
 try{
  if(request.method==="POST")need(request.headers.get("x-ipazake-source-sha")===env.RUNTIME_SOURCE_SHA,"runtime_source_not_ready");
  if(path==="ready"){
   const exists=await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_jobs'").first();
   if(exists){
    const rows=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE state IN ('submitted','running','uploading','link_ready','cancel_intent','cancel_pending','failed_pending')").all();
    for(const row of rows.results||[])await reconcileFixture(env,row,send);
   }
   const count=exists?await env.DB.prepare("SELECT count(*) n FROM runtime_jobs WHERE state NOT IN ('completed','cancelled','closed')").first():{n:0};
   return reply(200,{ok:true,source_sha:env.RUNTIME_SOURCE_SHA,active:count.n>0});
  }
  if(["init","admit-fixture","admit-drive-fixture","admit-export","catalog-open","catalog-action","status","owner-cancel","owner-get","canary/install","canary/revoke"].includes(path)){
   await admin(request,env);
   if(path==="init"){
    await body(request,[]);
    const sql=schemaStatements();
    const result=await env.DB.batch(sql.map(x=>env.DB.prepare(x)));
    need(result.every(x=>x.success===true),"runtime_schema");
    return reply(200,{ok:true,source_sha:env.RUNTIME_SOURCE_SHA});
   }
   if(path==="canary/install"){const value=await body(request,["packet"],262144);return reply(200,await installCanary(env,value.packet,now));}
   if(path==="canary/revoke"){const value=await body(request,["nonce"]);return reply(200,await revokeCanary(env,value.nonce,now));}
   if(["admit-fixture","admit-drive-fixture"].includes(path)){
    need(env.RUNTIME_MODE==="staging","runtime_fixture_only");
    const value=await body(request,["probe_id"]);need(/^[a-f0-9]{32}$/.test(value.probe_id||""),"runtime_fixture_id");
    const id="pilot_"+value.probe_id;
    const inserted=await env.DB.prepare(`INSERT INTO runtime_jobs
      (job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline)
      VALUES(?,?,?,'default','fixture','123456','',?,'waiting',?,?) ON CONFLICT DO NOTHING`)
      .bind(id,env.RUNTIME_OWNER_ID,value.probe_id,env.RUNTIME_SOURCE_SHA,now,now+3600).run();
    need(inserted.success===true,"runtime_admission_storage");await task(env,id);
    if(path==="admit-drive-fixture"){
     const marked=await env.DB.prepare("INSERT INTO runtime_drive_fixtures(job_id) SELECT job_id FROM runtime_jobs WHERE job_id=? AND state=\'waiting\' ON CONFLICT DO NOTHING").bind(id).run();
     need(marked.success===true,"runtime_fixture_storage");
     need((await task(env,id)).drive_fixture===1,"runtime_fixture_admission_binding");
    }else need((await task(env,id)).drive_fixture===0,"runtime_fixture_admission_binding");
    await dispatchNative(env,id,now,send);
    const row=await task(env,id);return reply(200,{ok:true,job_id:id,state:row.state,run_id:row.run_id});
   }
   if(path==="catalog-open"||path==="catalog-action"){
    const value=await body(request,path==="catalog-open"?["request_id","profile","target"]:["request_id","view_id","message_id","action","version_id"]);
    delete value._source;
    const result=path==="catalog-open"?await openCatalog(env,value,now,send):await catalogAction(env,value,now,send);
    await promoteNext(env,now,send);return reply(200,result);
   }
   if(path==="admit-export"){
    const value=await body(request,["request_id","profile","target","version"]);delete value._source;
    const row=await admitExport(env,value,now);
    await promoteNext(env,now,send);
    const current=await task(env,row.job_id,false);
    return reply(200,{ok:true,job_id:row.job_id,state:current.state,run_id:current.run_id});
   }
   const value=await body(request,["job_id"]);let row=await task(env,value.job_id,false);
   await reconcileFixture(env,row,send);row=await task(env,row.job_id,false);
   if(path==="status"&&["export","catalog"].includes(row.kind))await promoteNext(env,now,send);
   if(path==="owner-cancel"){
    need(["export","catalog"].includes(row.kind),"runtime_cancel_export_only");
    if(["completed","closed","cancelled"].includes(row.state))return reply(200,{ok:true,state:row.state});
    if(row.finished_at!==null&&(row.file_id||row.catalog?.result_json))return reply(200,{ok:true,state:"completed"});
    if(row.state==="waiting"){
     const stopped=await env.DB.prepare("UPDATE runtime_jobs SET state='cancelled' WHERE job_id=? AND state='waiting'").bind(row.job_id).run();
     need(stopped.success===true,"runtime_cancel_storage");
     if(stopped.meta?.changes===1)return reply(200,{ok:true,state:"cancelled"});
     row=await task(env,row.job_id,false);
    }
    const cancelled=await env.DB.prepare("UPDATE runtime_jobs SET state='cancel_pending' WHERE job_id=? AND finished_at IS NULL AND state NOT IN ('completed','closed','cancelled')")
     .bind(row.job_id).run();
    need(cancelled.success===true,"runtime_cancel_storage");
    if(cancelled.meta?.changes!==1)return reply(200,{ok:true,state:(await task(env,row.job_id,false)).finished_at!==null?"completed":"closed"});
    const intent=await env.DB.prepare("INSERT INTO runtime_cancel_intents(job_id,created_at,outcome) VALUES(?,?,'intent') ON CONFLICT DO NOTHING").bind(row.job_id,now).run();
    need(intent.success===true,"runtime_cancel_storage");
    await closeRuntimeLease(env.DB,row,now);
    if(intent.meta?.changes===1&&row.workflow_id){
     let outcome="unknown";
     try{
      const response=await send("https://circleci.com/api/v2/workflow/"+row.workflow_id+"/cancel",{
       method:"POST",redirect:"manual",signal:AbortSignal.timeout(10000),headers:{"Circle-Token":env.CIRCLECI_API_TOKEN,accept:"application/json"}});
      if(response.status===202)outcome="submitted";
      if(response.body)await response.body.cancel();
     }catch{}
     await env.DB.prepare("UPDATE runtime_cancel_intents SET outcome=? WHERE job_id=? AND outcome='intent'").bind(outcome,row.job_id).run();
    }
    return reply(200,{ok:true,state:"cancel_pending"});
   }
   if(path==="owner-get"){
    await requireEntry(env);need(row.kind==="export"&&(row.state==="completed"||(row.state==="link_ready"&&row.finished_at!==null))&&row.file_id&&row.link_expires>now,"runtime_link_unavailable");
    const record={file_id:row.file_id,filename:row.filename,bytes:row.plaintext_bytes,sha256:row.plaintext_sha256};
    await verifyOwnedUpload({...row,recipient_email:env.PILOT_DRIVE_RECIPIENT_EMAIL,control_origin:ORIGIN},record,env,send);
    return reply(200,{ok:true,...record,url:"https://drive.google.com/file/d/"+encodeURIComponent(row.file_id)+"/view",expires_at:row.link_expires});
   }
   const proof=await env.DB.prepare("SELECT receipt_json FROM runtime_export_proofs WHERE job_id=?").bind(row.job_id).first();
   const exportProof=proof?JSON.parse(proof.receipt_json):null;
   const notice=await env.DB.prepare("SELECT state FROM runtime_notifications WHERE job_id=?").bind(row.job_id).first();
   const lease=await env.DB.prepare("SELECT cipher_sha256,consumed_at,ciphertext,publisher_run_id FROM runtime_credential_leases WHERE job_id=?").bind(row.job_id).first();
   return reply(200,{ok:true,job_id:row.job_id,state:row.state,run_id:row.run_id,claimed:!!row.worker_job_id,
    drive_fixture:row.drive_fixture===1,drive_uploaded:!!row.file_id,fixture_cleaned:row.cleanup_state==="confirmed",
    link_expires:row.link_expires,profile:row.profile,task_kind:row.kind,catalog_ready:!!row.catalog?.result_json,export_verified:exportProof?.plaintext_verified===true,
    encrypted_images:exportProof?.encrypted_images||0,decrypted_pages:exportProof?.decrypted_pages||0,plaintext_bytes:row.plaintext_bytes,
    notification_confirmed:notice?.state==="sent",
    finished:row.finished_at!==null,fixture_verified:row.fixture_verified===1,
    publisher_run_id:lease?.publisher_run_id||null,cipher_sha256:lease?.cipher_sha256||null,ciphertext_cleared:!!lease&&lease.ciphertext===null&&lease.consumed_at!==null});
  }
  if(["publisher/pending","publisher/publish"].includes(path)){
   const publish=path.endsWith("publish");
   const value=await body(request,publish?["job_id","publisher_run_id","context","ciphertext"]:["job_id","publisher_run_id"],
    publish?360000:4096);
   const row=await task(env,value.job_id);
   await githubIdentity(request,env,row,value.publisher_run_id,now,send);
   if(publish)return reply(200,{ok:true,cipher_sha256:await publishRuntimeLease(env.DB,row,value.publisher_run_id,value,now)});
   return reply(200,{ok:true,...await pendingRuntimeLease(env.DB,row,value.publisher_run_id,now)});
  }
  if(!["claim","lease-request","lease-read","finish","plaintext-proof","upload-access","upload-journal","upload-register","fixture-cleanup","checkpoint","lease-consumed","export-finish","worker-failed","tf-permit","catalog-finish"].includes(path))return reply(404);
  const fields=path==="lease-request"?["job_id","worker_job_id","recipient","nonce","expires_at"]:
   path==="plaintext-proof"?["job_id","worker_job_id","receipt"]:
   path==="upload-journal"?["job_id","worker_job_id","action","state"]:
   path==="upload-register"?["job_id","worker_job_id","record"]:
   path==="checkpoint"?["job_id","worker_job_id","stage"]:
   ["export-finish","catalog-finish"].includes(path)?["job_id","worker_job_id","receipt"]:
   path==="tf-permit"?["job_id","worker_job_id","action","args"]:
   path==="finish"?["job_id","worker_job_id","fixture_verified"]:["job_id","worker_job_id"];
  const value=await body(request,fields,path==="upload-journal"?8192:4096),row=await task(env,value.job_id);
  const identity=await circleIdentity(request,env,row,value.worker_job_id,now,send);
  if(path==="claim"){
   if(["export","catalog"].includes(row.kind))await requireEntry(env);else need(env.RUNTIME_MODE==="staging","runtime_fixture_only");
   const result=await env.DB.prepare(`UPDATE runtime_jobs SET state='running',worker_job_id=?,workflow_id=?
    WHERE job_id=? AND state IN ('submitted','running') AND (worker_job_id IS NULL OR worker_job_id=?)`)
    .bind(identity.job_id,identity.workflow_id,row.job_id,identity.job_id).run();
   need(result.success===true&&result.meta?.changes===1,"runtime_claim_storage");
   return reply(200,{ok:true,task:{schema:"circleci-export-request-v1",job_id:row.job_id,request_id:row.request_id,
    run_id:row.run_id,worker_job_id:identity.job_id,source_sha:row.source_sha,profile:row.profile,target:row.target,
    version:row.version,recipient:"age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d",
    deadline:row.deadline},task_kind:row.kind,catalog_before:row.catalog?.before_id||"",drive_fixture:row.drive_fixture===1,fixture_binding:row.drive_fixture===1?DRIVE_FIXTURE:null});
  }
  need(row.worker_job_id===identity.job_id,"runtime_claim_required");
  if(path==="checkpoint"){
   need(typeof value.stage==="string"&&/^[a-z_]{1,40}$/.test(value.stage),"runtime_stage");
   const stages=["metadata","loading_runtime","preparing_public_resources","authenticating","auth_retry","resolving_version",
    "downloading","auditing","decrypting","verifying","encrypting","uploading_private","publishing_ciphertext","ciphertext_verified",
    "finalizing_ciphertext","artifact_ready","restoring_saved_session","checking_acceptance_permit","catalog_query","catalog_ready","working"];
   need(stages.includes(value.stage),"runtime_stage");
   const proceed=["running","uploading","link_ready"].includes(row.state)&&row.deadline>now;
   if(proceed&&value.stage!=="working")await env.DB.prepare("INSERT INTO runtime_task_progress(job_id,stage,updated_at) VALUES(?,?,?) ON CONFLICT(job_id) DO UPDATE SET stage=excluded.stage,updated_at=excluded.updated_at").bind(row.job_id,value.stage,now).run();
   return reply(200,{ok:true,proceed,deadline:row.deadline});
  }
  if(path==="worker-failed"){
   await closeRuntimeLease(env.DB,row,now);
   await env.DB.prepare("UPDATE runtime_jobs SET state='failed_pending' WHERE job_id=? AND state IN ('running','uploading','link_ready') AND finished_at IS NULL").bind(row.job_id).run();
   return reply(200,{ok:true});
  }
  need(["running","uploading","link_ready"].includes(row.state)&&row.deadline>now,"runtime_claim_required");
  if(path==="lease-consumed"){await closeRuntimeLease(env.DB,row,now);return reply(200,{ok:true});}
  if(path==="catalog-finish"){
   need(row.kind==="catalog","runtime_catalog_only");
   await saveCatalog(env,row,value.receipt,now);await closeRuntimeLease(env.DB,row,now);
   const confirmed=await completeCatalogNotices(env,row,now,send);
   return reply(200,{ok:true,notification_confirmed:confirmed});
  }
  if(row.kind==="catalog")need(["lease-request","lease-read"].includes(path),"runtime_catalog_metadata_only");
  if(path==="tf-permit"){
   await requireEntry(env);need(row.kind==="export"&&row.profile==="tf","runtime_tf_task");
   const args=value.args,request={invite:row.target,request_id:row.request_id,run_id:row.run_id,source_commit:row.source_sha};
   need(args&&Object.entries(request).every(([key,item])=>args[key]===item)&&
    ["claim","finish"].includes(value.action)&&Object.keys(args).sort().join(",")===
    [...Object.keys(request),...(value.action==="finish"?["nonce","outcome"]:[])].sort().join(","),"runtime_tf_request_binding");
   need(/^[a-f0-9]{64}$/.test(env.RUNTIME_TF_HMAC_KEY||""),"runtime_tf_handoff_required");
   const pepper=Uint8Array.from(env.RUNTIME_TF_HMAC_KEY.match(/../g),x=>parseInt(x,16));
   const hash=await inviteHash(row.target,row.owner_id,pepper);
   return reply(200,value.action==="claim"?{ok:true,...await claimPermit(env.DB,row.owner_id,hash,request,now)}:
    {ok:true,...await finishPermit(env.DB,row.owner_id,hash,request,args.nonce,args.outcome,now)});
  }
  if(path==="export-finish"){
   await requireEntry(env);need(row.kind==="export","runtime_export_only");
   await verifyFinishedExport(env.DB,row,value.receipt);
   await closeRuntimeLease(env.DB,row,now);
   const result=await env.DB.prepare("UPDATE runtime_jobs SET finished_at=COALESCE(finished_at,?) WHERE job_id=? AND state='link_ready' AND worker_job_id=?").bind(now,row.job_id,identity.job_id).run();
   need(result.success===true&&result.meta?.changes===1,"runtime_export_finish_storage");
   const completed=await task(env,row.job_id);
   let notification=false;
   try{notification=await notifyOwner(env,completed,now,send);}catch{}
   return reply(200,{ok:true,notification_confirmed:notification});
  }
  if(path==="plaintext-proof"){
   if(row.kind==="export"){
    await requireEntry(env);await saveExportProof(env.DB,row,value.receipt);return reply(200,{ok:true});
   }
   need(row.kind==="fixture"&&row.drive_fixture===1,"runtime_production_disabled");
   const proof=value.receipt,expected={schema:"circleci-private-upload-fixture-v1",job_id:row.job_id,
    run_id:row.run_id,worker_job_id:row.worker_job_id,source_commit:row.source_sha,fixture_authorized:true,
    decryption_proven:false,plaintext_verified:false,account_data_removed:false,archive_verified:true,
    plaintext_sha256:DRIVE_FIXTURE.sha256,plaintext_bytes:DRIVE_FIXTURE.bytes,filename:DRIVE_FIXTURE.filename};
   need(proof&&Object.keys(proof).sort().join(",")===Object.keys(expected).sort().join(",")&&
    Object.entries(expected).every(([k,v])=>proof[k]===v),"runtime_fixture_proof");
   need(["running","uploading"].includes(row.state),"runtime_fixture_proof_state");
   const saved=await env.DB.batch([
    env.DB.prepare("UPDATE runtime_jobs SET state='uploading',plaintext_sha256=?,plaintext_bytes=?,filename=? WHERE job_id=? AND state IN ('running','uploading')")
     .bind(DRIVE_FIXTURE.sha256,DRIVE_FIXTURE.bytes,DRIVE_FIXTURE.filename,row.job_id),
    env.DB.prepare("UPDATE runtime_drive_fixtures SET authorized=1 WHERE job_id=?").bind(row.job_id)]);
   need(saved.every(x=>x.success===true),"runtime_fixture_proof_storage");return reply(200,{ok:true});
  }
  const uploadTask={...row,recipient_email:env.PILOT_DRIVE_RECIPIENT_EMAIL,control_origin:ORIGIN};
  if(path==="upload-access")return reply(200,{ok:true,...await uploadAccess(uploadTask,env,now,send)});
  if(path==="upload-journal"){
   need(["get","put"].includes(value.action),"runtime_upload_action");
   if(value.action==="get"){need(value.state===null,"runtime_upload_fields");return reply(200,{ok:true,state:await readUploadJournal(env.DB,uploadTask)});}
   await writeUploadJournal(env.DB,uploadTask,value.state,now);return reply(200,{ok:true});
  }
  if(path==="upload-register"){
   // Journal intent and provider verification are both required, including on a repeated acknowledgement.
   const saved=await readUploadJournal(env.DB,uploadTask);
   need(saved&&["registration_intent","registered"].includes(saved.stage)&&saved.file_id===value.record?.file_id,"runtime_upload_registration_intent");
   const verified=await verifyOwnedUpload(uploadTask,value.record,env,send);
   await confirmUploadRegistration(env.DB,uploadTask,verified.file_id,now);
   const result=await env.DB.batch([
    env.DB.prepare("UPDATE runtime_jobs SET state='link_ready',file_id=?,link_expires=COALESCE(link_expires,?) WHERE job_id=? AND state IN ('uploading','link_ready') AND (file_id IS NULL OR file_id=?)")
     .bind(verified.file_id,now+86400,row.job_id,verified.file_id),
    env.DB.prepare("UPDATE runtime_drive_fixtures SET file_id=? WHERE job_id=? AND (file_id IS NULL OR file_id=?)")
     .bind(verified.file_id,row.job_id,verified.file_id)]);
   need(result.every(x=>x.success===true)&&result[0].meta?.changes===1,"runtime_upload_registration_storage");return reply(200,{ok:true,verified:true});
  }
  if(path==="fixture-cleanup")return reply(200,{ok:true,cleaned:await cleanupFixture(uploadTask,env,now,send)});
  if(path==="lease-request"){
   const context=await requestRuntimeLease(env.DB,row,value,now);await dispatchPublisher(env,row,context,now,send);
   return reply(200,{ok:true,context});
  }
  if(path==="lease-read")return reply(200,{ok:true,...await readRuntimeLease(env.DB,row,now)});
  need(row.kind==="fixture"&&value.fixture_verified===true,"runtime_finish_binding");
  need(row.drive_fixture===0||(row.fixture_authorized===1&&row.file_id&&row.cleanup_state==="confirmed"),"runtime_fixture_delivery_required");
  const lease=await env.DB.prepare("SELECT cipher_sha256 FROM runtime_credential_leases WHERE job_id=?").bind(row.job_id).first();
  need(lease?.cipher_sha256,"runtime_lease_required");await closeRuntimeLease(env.DB,row,now);
  const result=await env.DB.prepare("UPDATE runtime_jobs SET finished_at=COALESCE(finished_at,?),fixture_verified=1 WHERE job_id=? AND worker_job_id=?")
   .bind(now,row.job_id,identity.job_id).run();need(result.success===true,"runtime_finish_storage");
  return reply(200,{ok:true});
 }catch(error){
  const code=/^[a-z_]{1,60}$/.test(error?.message||"")?error.message:"runtime_unavailable";
  return reply(409,{ok:false,code});
 }
}

export async function runtimeTick(env,now=Math.floor(Date.now()/1000),send=(url,init)=>globalThis.fetch(url,init)){
 await requireEntry(env);
 const rows=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE owner_id=? AND state IN ('submitted','running','uploading','link_ready','cancel_intent','cancel_pending','failed_pending')").bind(env.RUNTIME_OWNER_ID).all();
 for(const row of rows.results||[])await reconcileFixture(env,row,send);
 await promoteNext(env,now,send);
}
