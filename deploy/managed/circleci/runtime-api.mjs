// Staged managed-runtime API. Real exports and Telegram admission remain disabled until handoff.
import {TRUST} from "./oidc.mjs";
import {RUNTIME_SCHEMA} from "./runtime-schema.mjs";
import {UPLOAD_SCHEMA,readUploadJournal,writeUploadJournal,confirmUploadRegistration} from "./runtime-upload.mjs";
import {DRIVE_FIXTURE,FIXTURE_SCHEMA} from "./runtime-fixture.mjs";
import {uploadAccess,verifyOwnedUpload,cleanupFixture} from "./runtime-drive.mjs";
import {need,UUID,publicJSON,circleIdentity,githubIdentity} from "./runtime-auth.mjs";
import {requestRuntimeLease,pendingRuntimeLease,publishRuntimeLease,readRuntimeLease,closeRuntimeLease} from "./runtime-lease.mjs";
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
async function task(env,id){
 need(JOB.test(id||""),"runtime_job_id");
 const value=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE job_id=? AND owner_id=?")
  .bind(id,env.RUNTIME_OWNER_ID).first();
 need(value&&value.source_sha===env.RUNTIME_SOURCE_SHA,"runtime_job_binding");
 const fixture=await env.DB.prepare("SELECT * FROM runtime_drive_fixtures WHERE job_id=?").bind(id).first();
 return {...value,drive_fixture:fixture?1:0,fixture_authorized:fixture?.authorized||0,cleanup_state:fixture?.cleanup_state||null};
}
async function sendAPI(send,url,token,data){
 return send(url,{method:"POST",redirect:"manual",signal:AbortSignal.timeout(15000),
  headers:{"user-agent":"ipa-decrypt-managed-runtime/0.2",authorization:"Bearer "+token,accept:"application/json",
   "content-type":"application/json"},body:JSON.stringify(data)});
}
async function dispatchNative(env,id,now,send){
 const nonce=crypto.randomUUID().replaceAll("-","");
 const result=await env.DB.prepare(`UPDATE runtime_jobs SET state='dispatch_intent',dispatch_nonce=?
  WHERE job_id=? AND owner_id=? AND state='waiting'
   AND NOT EXISTS(SELECT 1 FROM runtime_jobs WHERE state IN ('dispatch_intent','dispatch_unknown','submitted','running','uploading','link_ready'))`)
  .bind(nonce,id,env.RUNTIME_OWNER_ID).run();
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
 if(row.kind!=="fixture"||!row.run_id||!["submitted","running","uploading","link_ready"].includes(row.state))return;
 const run=(await publicJSON(send,"https://circleci.com/api/v3/runs/"+row.run_id)).data;
 const refs=run?.references,vcs=refs?.event?.attributes?.vcs;
 need(run?.id===row.run_id&&refs?.project?.id===TRUST.project&&refs?.pipeline?.id===TRUST.definition&&
  vcs?.revision===row.source_sha&&vcs?.origin_repository_url==="https://"+TRUST.source&&
  vcs?.target_repository_url==="https://"+TRUST.source&&vcs?.branch===TRUST.ref.slice(11),"runtime_terminal_binding");
 if(run?.attributes?.phase!=="ended")return;
 if(run.attributes.current_outcome==="succeeded"&&row.finished_at!==null&&row.fixture_verified===1){
  await env.DB.prepare("UPDATE runtime_jobs SET state='completed' WHERE job_id=? AND kind='fixture' AND state IN ('running','uploading','link_ready')").bind(row.job_id).run();
 }else if(["failed","canceled","cancelled","error"].includes(run.attributes.current_outcome)){
  // Only a known, ended, credential-free validation. Original ID, nonce and history are retained.
  await env.DB.prepare("UPDATE runtime_jobs SET state='closed' WHERE job_id=? AND kind='fixture' AND state IN ('submitted','running','uploading','link_ready')")
   .bind(row.job_id).run();
  await closeRuntimeLease(env.DB,row,Math.floor(Date.now()/1000));
 }
}

export async function handleRuntimeV2(request,env,now=Math.floor(Date.now()/1000),send=(url,init)=>globalThis.fetch(url,init)){
 const url=new URL(request.url),path=url.pathname.slice(PREFIX.length);
 if(url.search||!url.pathname.startsWith(PREFIX))return reply(404);
 if(request.method!=="POST"&&!(request.method==="GET"&&path==="ready"))return reply(404);
 if(env.RUNTIME_MODE!=="staging"||env.RUNTIME_CONTROL_ORIGIN!==ORIGIN||url.origin!==ORIGIN||
  !SHA.test(env.RUNTIME_SOURCE_SHA||"")||!/^[1-9][0-9]{0,15}$/.test(env.RUNTIME_OWNER_ID||"")||!env.DB?.prepare)return reply(503);
 try{
  if(request.method==="POST")need(request.headers.get("x-ipazake-source-sha")===env.RUNTIME_SOURCE_SHA,"runtime_source_not_ready");
  if(path==="ready"){
   const exists=await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_jobs'").first();
   if(exists){
    const rows=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE kind='fixture' AND state IN ('submitted','running','uploading','link_ready')").all();
    for(const row of rows.results||[])await reconcileFixture(env,row,send);
   }
   const count=exists?await env.DB.prepare("SELECT count(*) n FROM runtime_jobs WHERE state NOT IN ('completed','cancelled','closed')").first():{n:0};
   return reply(200,{ok:true,source_sha:env.RUNTIME_SOURCE_SHA,active:count.n>0});
  }
  if(["init","admit-fixture","admit-drive-fixture","status"].includes(path)){
   await admin(request,env);
   if(path==="init"){
    await body(request,[]);
    const sql=(RUNTIME_SCHEMA+"\n"+UPLOAD_SCHEMA+"\n"+FIXTURE_SCHEMA).split(";").map(x=>x.trim()).filter(Boolean);
    const result=await env.DB.batch(sql.map(x=>env.DB.prepare(x)));
    need(result.every(x=>x.success===true),"runtime_schema");
    return reply(200,{ok:true,source_sha:env.RUNTIME_SOURCE_SHA});
   }
   if(["admit-fixture","admit-drive-fixture"].includes(path)){
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
   const value=await body(request,["job_id"]);let row=await task(env,value.job_id);
   await reconcileFixture(env,row,send);row=await task(env,row.job_id);
   const lease=await env.DB.prepare("SELECT cipher_sha256,consumed_at,ciphertext,publisher_run_id FROM runtime_credential_leases WHERE job_id=?").bind(row.job_id).first();
   return reply(200,{ok:true,job_id:row.job_id,state:row.state,run_id:row.run_id,claimed:!!row.worker_job_id,
    drive_fixture:row.drive_fixture===1,drive_uploaded:!!row.file_id,fixture_cleaned:row.cleanup_state==="confirmed",
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
  if(!["claim","lease-request","lease-read","finish","plaintext-proof","upload-access","upload-journal","upload-register","fixture-cleanup"].includes(path))return reply(404);
  const fields=path==="lease-request"?["job_id","worker_job_id","recipient","nonce","expires_at"]:
   path==="plaintext-proof"?["job_id","worker_job_id","receipt"]:
   path==="upload-journal"?["job_id","worker_job_id","action","state"]:
   path==="upload-register"?["job_id","worker_job_id","record"]:
   path==="finish"?["job_id","worker_job_id","fixture_verified"]:["job_id","worker_job_id"];
  const value=await body(request,fields,path==="upload-journal"?8192:4096),row=await task(env,value.job_id);
  const identity=await circleIdentity(request,env,row,value.worker_job_id,now,send);
  if(path==="claim"){
   need(row.kind==="fixture","runtime_production_disabled");
   const result=await env.DB.prepare(`UPDATE runtime_jobs SET state='running',worker_job_id=?,workflow_id=?
    WHERE job_id=? AND state IN ('submitted','running') AND (worker_job_id IS NULL OR worker_job_id=?)`)
    .bind(identity.job_id,identity.workflow_id,row.job_id,identity.job_id).run();
   need(result.success===true&&result.meta?.changes===1,"runtime_claim_storage");
   return reply(200,{ok:true,task:{schema:"circleci-export-request-v1",job_id:row.job_id,request_id:row.request_id,
    run_id:row.run_id,worker_job_id:identity.job_id,source_sha:row.source_sha,profile:row.profile,target:row.target,
    version:row.version,recipient:"age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d",
    deadline:row.deadline},task_kind:row.kind,drive_fixture:row.drive_fixture===1,fixture_binding:row.drive_fixture===1?DRIVE_FIXTURE:null});
  }
  need(row.worker_job_id===identity.job_id&&["running","uploading","link_ready"].includes(row.state)&&row.deadline>now,"runtime_claim_required");
  if(path==="plaintext-proof"){
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
    env.DB.prepare("UPDATE runtime_jobs SET state='link_ready',file_id=? WHERE job_id=? AND state IN ('uploading','link_ready') AND (file_id IS NULL OR file_id=?)")
     .bind(verified.file_id,row.job_id,verified.file_id),
    env.DB.prepare("UPDATE runtime_drive_fixtures SET file_id=? WHERE job_id=? AND (file_id IS NULL OR file_id=?)")
     .bind(verified.file_id,row.job_id,verified.file_id)]);
   need(result.every(x=>x.success===true),"runtime_upload_registration_storage");return reply(200,{ok:true,verified:true});
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
