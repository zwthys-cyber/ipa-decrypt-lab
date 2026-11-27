// CI only: actual workerd/D1, real RSA tokens, synthetic provider transport.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {mkdtemp,mkdir,copyFile,writeFile,rm} from "node:fs/promises";
import {join} from "node:path";
import {tmpdir} from "node:os";
import {Miniflare} from "miniflare";
import {verifyCatalog} from "./runtime-catalog.mjs";
import {parseTask} from "./runtime-telegram.mjs";
import {TRUST as C} from "./oidc.mjs";
import {GITHUB_TRUST as G} from "./github-oidc.mjs";
globalThis.crypto??=webcrypto;
const source="a".repeat(40),owner="12345",secret="A".repeat(48),origin=G.audience,probe="1".repeat(32),job="pilot_"+probe;
const run="12345678-1234-1234-1234-123456789abc",workflow="23456789-1234-1234-1234-123456789abc";
const worker="34567890-1234-1234-1234-123456789abc",publisher="987654321",now=Math.floor(Date.now()/1000);
async function pair(kid){
 const key=await crypto.subtle.generateKey({name:"RSASSA-PKCS1-v1_5",modulusLength:2048,
  publicExponent:new Uint8Array([1,0,1]),hash:"SHA-256"},true,["sign","verify"]);
 const jwk=await crypto.subtle.exportKey("jwk",key.publicKey);jwk.kid=kid;return {key,jwk,kid};
}
const circle=await pair("circle-fixture"),github=await pair("github-fixture");
async function signed(kind,changes={}){
 let claims;
 if(kind==="circle"){
  claims={iss:"https://oidc.circleci.com/org/"+C.org,aud:C.org,iat:now-10,exp:now+600,
   sub:"org:"+C.org+":project:"+C.project+":user:"+C.user+":checkout-source:"+C.source+
    ":checkout-ref:"+C.ref+":config-source:"+C.source+":config-ref:"+C.ref};
  for(const [key,value] of Object.entries({"org-id":C.org,"project-id":C.project,"pipeline-id":C.definition,
   "run-id":run,"job-id":worker,"ssh-rerun":false,"checkout-source":C.source,"config-source":C.source,
   "checkout-ref":C.ref,"config-ref":C.ref,"context-ids":[]}))claims["oidc.circleci.com/"+key]=value;
 }else claims={iss:G.issuer,aud:G.audience,iat:now-10,nbf:now-10,exp:now+290,
  sub:"repo:"+G.repository+":ref:"+G.ref,repository:G.repository,repository_id:G.repository_id,
  repository_owner_id:G.owner_id,actor_id:G.owner_id,ref:G.ref,ref_type:"branch",sha:source,
  workflow_sha:source,workflow_ref:G.repository+"/"+G.workflows.lease+"@"+G.ref,
  run_id:publisher,run_attempt:"1",runner_environment:"github-hosted",event_name:"workflow_dispatch"};
 Object.assign(claims,changes);
 const signer=kind==="circle"?circle:github;
 const enc=x=>Buffer.from(x).toString("base64url");
 const raw=enc(JSON.stringify({alg:"RS256",kid:signer.kid}))+"."+enc(JSON.stringify(claims));
 return raw+"."+enc(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",signer.key.privateKey,new TextEncoder().encode(raw)));
}
async function setup(bindings={}){
 const base=await mkdtemp(join(tmpdir(),"runtime-api-"));
 const folder=join(base,"circleci");await mkdir(folder);await mkdir(join(base,"free-pilot"));
 await copyFile(new URL("../free-pilot/drive-auth.mjs",import.meta.url),join(base,"free-pilot","drive-auth.mjs"));
 const files=["runtime-chat-action.mjs","runtime-presentation.mjs","runtime-api.mjs","runtime-recovery.mjs","runtime-catalog.mjs","runtime-canary.mjs","runtime-notify.mjs","runtime-tasks.mjs","runtime-telegram.mjs","tf-acceptance.mjs","runtime-schema.mjs","runtime-auth.mjs","runtime-lease.mjs","runtime-upload.mjs","runtime-drive.mjs","runtime-fixture.mjs",
  "oidc.mjs","github-oidc.mjs"];
 await Promise.all(files.map(name=>copyFile(new URL(name,import.meta.url),join(folder,name))));
 const entry=join(folder,"entry.mjs");
 await writeFile(entry,`
 import {handleRuntimeV2,runtimeTick} from "./runtime-api.mjs";
 import {handleManagedTelegram} from "./runtime-telegram.mjs";
 const C=${JSON.stringify(C)},G=${JSON.stringify(G)};
 const run=${JSON.stringify(run)},workflow=${JSON.stringify(workflow)},worker=${JSON.stringify(worker)};
 let menus=[];let nativePosts=0,publisherPosts=0,typingActions=0,notifications=0,deleted=false,managedJob="pilot_11111111111111111111111111111111";
 export default {async fetch(request,env){
  if(new URL(request.url).pathname==="/fixture-count")return Response.json({nativePosts,publisherPosts,typingActions});
  if(request.headers.get("x-fixture-query-budget")==="1"){
   const rawDB=env.DB,originals=new WeakMap();let calls=0;
   const use=()=>{if(++calls>8)throw Error("fixture_d1_query_budget");};
   const wrap=statement=>{
    const next={bind(...args){return wrap(statement.bind(...args));}};
    for(const method of ["first","all","run","raw"])next[method]=(...args)=>{use();return statement[method](...args);};
    originals.set(next,statement);return next;
   };
   env={...env,DB:{prepare(sql){return wrap(rawDB.prepare(sql));},batch(statements){use();return rawDB.batch(statements.map(s=>originals.get(s)||s));}}};
  }
  async function provider(url,options){
   new Request(url,options);
   if(options.redirect!=="manual")throw Error("redirect_policy");
   if(url==="https://oidc.circleci.com/org/"+C.org+"/.well-known/jwks-pub.json")
    return Response.json({keys:[${JSON.stringify(circle.jwk)}]});
   if(url===G.issuer+"/.well-known/jwks")return Response.json({keys:[${JSON.stringify(github.jwk)}]});
   if(url==="https://circleci.com/api/v2/workflow/"+workflow+"/cancel")return new Response(null,{status:202});
   if(url==="https://circleci.com/api/v3/runs"){
    nativePosts++;
    const params=JSON.parse(options.body).data.attributes.parameters;
    managedJob=params.managed_job;
    if(params.managed_runtime!==true||params.dispatch_probe!==false||params.managed_source!==${JSON.stringify(source)})
     throw Error("bad_native_parameters");
    if(request.headers.get("x-fixture-unknown")==="1")throw Error("ambiguous_network");
    const used=await env.DB.prepare("SELECT job_id FROM runtime_jobs WHERE run_id=?").bind(run).first();
    return Response.json({data:{id:!used?run:"12345678-1234-1234-1234-"+String(nativePosts).padStart(12,"0")}},{status:201});
   }
   if(url.startsWith("https://circleci.com/api/v3/runs/")){
    const currentRun=url.split("/").at(-1);
    const terminal=currentRun===run&&request.headers.get("x-fixture-terminal")==="1";
    return Response.json({data:{id:currentRun,attributes:{phase:terminal?"ended":"started",current_outcome:terminal?(request.headers.get("x-fixture-failed")==="1"?"failed":"succeeded"):null},
     references:{project:{id:C.project},pipeline:{id:C.definition},event:{attributes:{vcs:{
      origin_repository_url:"https://"+C.source,target_repository_url:"https://"+C.source,branch:C.ref.slice(11),
      revision:request.headers.get("x-fixture-wrong-source")==="1"?"b".repeat(40):${JSON.stringify(source)}
     }}}}}});
   }
   if(url==="https://circleci.com/api/v2/pipeline/"+run+"/workflow")
    return Response.json({items:[{id:workflow,name:"managed-runtime-tasks",pipeline_id:run}]});
   if(url==="https://circleci.com/api/v2/workflow/"+workflow+"/job")
    return Response.json({items:[{id:worker,name:"managed-runtime-task",status:"running"}]});
   if(url==="https://api.github.com/repos/"+G.repository+"/actions/workflows/circleci-secret-lease.yml/dispatches"){
    publisherPosts++;
    const value=JSON.parse(options.body);
    const task=await env.DB.prepare("SELECT * FROM runtime_jobs WHERE job_id=?").bind(managedJob).first();
    const catalog=await env.DB.prepare("SELECT job_id FROM runtime_catalog_specs WHERE job_id=?").bind(managedJob).first();
    if(value.inputs.profile!==(task.kind==="fixture"?"synthetic":task.profile+(catalog?"_catalog":""))||value.inputs.job_id!==managedJob)throw Error("wrong_publisher_profile");
    return new Response(null,{status:204});
   }
   if(url==="https://api.github.com/repos/"+G.repository+"/actions/runs/"+${JSON.stringify(publisher)})
    return Response.json({id:Number(${JSON.stringify(publisher)}),repository:{id:Number(G.repository_id)},actor:{id:Number(G.owner_id)},
     event:"workflow_dispatch",run_attempt:1,head_sha:${JSON.stringify(source)},head_branch:C.ref.slice(11),
     status:"in_progress",path:G.workflows.lease,display_title:"CircleCI lease "+managedJob});
   if(url.startsWith("https://api.telegram.org/bot")){
    if(url.endsWith("/answerCallbackQuery"))return Response.json({ok:true,result:true});
    if(url.endsWith("/sendChatAction")){
     const action=JSON.parse(options.body);
     if(String(action.chat_id)!==env.RUNTIME_OWNER_ID||action.action!=="typing")throw Error("wrong_typing_owner");
     typingActions++;return Response.json({ok:true,result:true});
    }
    notifications++;
    const value=JSON.parse(options.body);
    if(String(value.chat_id)!==env.RUNTIME_OWNER_ID)throw Error("wrong_notification_owner");
    if(value.text.includes("历史版本"))menus.push(value);
    if(request.headers.get("x-fixture-notify-unknown")==="1")throw Error("unknown_notification");
    return Response.json({ok:true,result:{message_id:10+menus.length,chat:{type:"private",id:Number(env.RUNTIME_OWNER_ID)}}});
   }
   if(url.startsWith("https://www.googleapis.com/drive/v3/")){
    if(options.method==="DELETE"){deleted=true;return new Response(null,{status:204});}
    if(url.includes("about?"))return Response.json({storageQuota:{limit:String(15*1024**3),usage:"0"},user:{emailAddress:"fixture@example.invalid"}});
    if(url.includes("/permissions?"))return Response.json({permissions:[{type:"user",role:"owner",emailAddress:"fixture@example.invalid"}]});
    if(deleted)return new Response(null,{status:404});
    return Response.json({id:"FIXTURE_FILE_12345",name:"Migration_ARM_Probe.ipa",size:"5496",
     sha256Checksum:"85025bd1cfea42339ed38b09e9580e1094b2949153c83c81e66d9b1ad9043e93",
     ownedByMe:true,trashed:false,mimeType:"application/octet-stream"});
   }
   throw Error("unexpected_provider_request");
  }
  if(new URL(request.url).pathname==="/fixture-menus")return Response.json(menus);
  if(new URL(request.url).pathname==="/fixture-tick"){await runtimeTick(env,${now},provider);return Response.json({ok:true});}
  if(new URL(request.url).pathname==="/fixture-drive")return Response.json({deleted,notifications});
  if(new URL(request.url).pathname==="/telegram")return handleManagedTelegram(request,env,async(path,value)=>{
   const result=await handleRuntimeV2(new Request(G.audience+"/v2/runtime/"+path,{method:"POST",
    headers:{"content-type":"application/json","x-ipazake-source-sha":env.RUNTIME_SOURCE_SHA,"x-ipazake-control-token":env.CIRCLECI_CONTROL_TOKEN},
    body:JSON.stringify({...value,_source:env.RUNTIME_SOURCE_SHA})}),env,${now},provider);
   const answer=await result.json();if(!answer.ok)throw Error(answer.code);return answer;
  },${now},provider);
  return handleRuntimeV2(request,env,${now},provider);
 }};
 `);
 const mf=new Miniflare({modules:true,modulesRoot:base,scriptPath:entry,compatibilityDate:"2026-07-30",
  cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"99999999-9999-4999-8999-999999999999"},
  bindings:{RUNTIME_MODE:"staging",RUNTIME_CONTROL_ORIGIN:origin,RUNTIME_SOURCE_SHA:source,RUNTIME_OWNER_ID:owner,
   CIRCLECI_CONTROL_TOKEN:secret,CIRCLECI_API_TOKEN:"synthetic-circle-token",RUNTIME_GH_TOKEN:"synthetic-github-token",PILOT_DRIVE_RECIPIENT_EMAIL:"fixture@example.invalid",PILOT_DRIVE_ACCESS_TOKEN:"T".repeat(32),...bindings}});
 const db=await mf.getD1Database("DB");
 const requestSource=bindings.RUNTIME_SOURCE_SHA||source;
 const request=(path,value={},kind="admin",token=secret,extra={})=>mf.dispatchFetch(origin+"/v2/runtime/"+path,{
  method:"POST",headers:{"content-type":"application/json","x-ipazake-source-sha":requestSource,
   [kind==="circle"?"x-ipazake-job-token":kind==="github"?"x-ipazake-github-token":"x-ipazake-control-token"]:token,...extra},
  body:JSON.stringify({...value,_source:requestSource})});
 const close=async()=>{await mf.dispose();await rm(base,{recursive:true,force:true});};
 return {mf,db,request,close};
}
test("real workerd managed claim, automatic publisher, immutable lease and completion",{timeout:60000},async()=>{
 const s=await setup();try{
  assert.equal((await s.request("init")).status,200);
  assert.equal((await s.request("admit-fixture",{probe_id:probe})).status,200);
  await s.request("admit-fixture",{probe_id:probe});
  const c=await signed("circle"),g=await signed("github"),identity={job_id:job,worker_job_id:worker};
  assert.equal((await s.request("claim",identity,"circle",c)).status,200);
  const value={...identity,recipient:"age1"+"q".repeat(58),nonce:"c".repeat(32),expires_at:now+300};
  const requested=await s.request("lease-request",value,"circle",c);
  assert.equal(requested.status,200);const context=(await requested.json()).context;
  assert.equal(context.profile,"synthetic");
  assert.equal((await s.request("lease-request",value,"circle",c)).status,200);
  assert.deepEqual(await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json()),{nativePosts:1,publisherPosts:1,typingActions:0});
  const publisherBinding={job_id:job,publisher_run_id:publisher};
  assert.equal((await s.request("publisher/pending",publisherBinding,"github",g)).status,200);
  const ciphertext=btoa("age-encryption.org/v1\nfixture-opaque-cipher");
  const payload={...publisherBinding,context,ciphertext};
  assert.equal((await s.request("publisher/publish",payload,"github",g)).status,200);
  assert.equal((await s.request("publisher/publish",payload,"github",g)).status,200);
  assert.equal((await s.request("publisher/publish",{...payload,context:{...context,profile:"tf"}},"github",g)).status,409);
  assert.equal((await (await s.request("lease-read",identity,"circle",c)).json()).ciphertext,ciphertext);
  assert.equal((await s.request("finish",{...identity,fixture_verified:true},"circle",c)).status,200);
  const status=await (await s.request("status",{job_id:job},"admin",secret,{"x-fixture-terminal":"1"})).json();
  assert.equal(status.state,"completed");assert.equal(status.ciphertext_cleared,true);assert.equal(status.fixture_verified,true);
 }finally{await s.close();}
});
test("real workerd rejects cross-role identities, wrong source and reruns",{timeout:60000},async()=>{
 const s=await setup();try{
  await s.request("init");await s.request("admit-fixture",{probe_id:probe});
  const identity={job_id:job,worker_job_id:worker},c=await signed("circle"),g=await signed("github");
  assert.equal((await s.request("claim",identity,"circle",g)).status,409);
  assert.equal((await s.request("claim",identity,"circle",c,{"x-fixture-wrong-source":"1"})).status,409);
  assert.equal((await s.request("claim",identity,"circle",await signed("circle",{"oidc.circleci.com/ssh-rerun":true}))).status,409);
  await s.request("claim",identity,"circle",c);
  const value={job_id:job,publisher_run_id:publisher};
  assert.equal((await s.request("publisher/pending",value,"github",c)).status,409);
  const bad=await signed("github",{workflow_ref:G.repository+"/"+G.workflows.probe+"@"+G.ref,event_name:"push"});
  assert.equal((await s.request("publisher/pending",value,"github",bad)).status,409);
  assert.equal((await s.request("claim",identity,"admin",secret)).status,409);
 }finally{await s.close();}
});
test("real workerd ambiguous native creation never launches another task",{timeout:60000},async()=>{
 const s=await setup();try{
  await s.request("init");
  const first=await s.request("admit-fixture",{probe_id:probe},"admin",secret,{"x-fixture-unknown":"1"});
  assert.equal((await first.json()).state,"dispatch_unknown");
  assert.equal((await (await s.request("admit-fixture",{probe_id:probe})).json()).state,"dispatch_unknown");
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
 }finally{await s.close();}
});

test("known failed fixtures close without rearming the original job or dispatch nonce",{timeout:60000},async()=>{
 const s=await setup();try{
  await s.request("init");await s.request("admit-fixture",{probe_id:probe});
  const before=await s.db.prepare("SELECT dispatch_nonce,run_id FROM runtime_jobs WHERE job_id=?").bind(job).first();
  const status=await s.request("status",{job_id:job},"admin",secret,{"x-fixture-terminal":"1","x-fixture-failed":"1"});
  assert.equal((await status.json()).state,"closed");
  await s.request("admit-fixture",{probe_id:probe});
  const after=await s.db.prepare("SELECT dispatch_nonce,run_id FROM runtime_jobs WHERE job_id=?").bind(job).first();
  assert.deepEqual(after,before);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
 }finally{await s.close();}
});

test("a stale deployment rejects admission before creating any native intent",{timeout:60000},async()=>{
 const s=await setup();try{
  await s.request("init");
  const result=await s.request("admit-fixture",{probe_id:probe},"admin",secret,{"x-ipazake-source-sha":"b".repeat(40)});
  assert.equal(result.status,409);assert.equal((await result.json()).code,"runtime_source_not_ready");
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs").first()).n,0);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,0);
 }finally{await s.close();}
});

test("drive fixture requires pinned proof, durable intent, owner verification and cleanup",{timeout:60000},async()=>{
 const s=await setup();try{
  await s.request("init");await s.request("admit-drive-fixture",{probe_id:probe});
  const c=await signed("circle"),identity={job_id:job,worker_job_id:worker};
  const claimed=await (await s.request("claim",identity,"circle",c)).json();
  assert.equal(claimed.drive_fixture,true);
  assert.equal((await s.request("upload-access",identity,"circle",c)).status,409);
  const b=claimed.fixture_binding;
  const receipt={schema:"circleci-private-upload-fixture-v1",job_id:job,run_id:run,worker_job_id:worker,
   source_commit:source,fixture_authorized:true,decryption_proven:false,plaintext_verified:false,
   account_data_removed:false,archive_verified:true,plaintext_sha256:b.sha256,plaintext_bytes:b.bytes,filename:b.filename};
  assert.equal((await s.request("plaintext-proof",{...identity,receipt:{...receipt,decryption_proven:true}},"circle",c)).status,409);
  assert.equal((await s.request("plaintext-proof",{...identity,receipt},"circle",c)).status,200);
  assert.equal((await s.request("upload-access",identity,"circle",c)).status,200);
  const record={filename:b.filename,bytes:b.bytes,sha256:b.sha256},file_id="FIXTURE_FILE_12345";
  assert.equal((await s.request("upload-register",{...identity,record:{...record,file_id}},"circle",c)).status,409);
  const state={job_id:job,owner:"fixture@example.invalid",record};
  for(const item of [{stage:"start_intent"},{stage:"uploading",session:"https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=SYNTHETIC_12345678"},
   {stage:"uploaded",file_id},{stage:"registration_intent",file_id,registration_origin:origin}]){
   const r=await s.request("upload-journal",{...identity,action:"put",state:{...state,...item}},"circle",c);
   assert.equal(r.status,200,await r.text());
  }
  for(let n=0;n<2;n++)assert.equal((await s.request("upload-register",{...identity,record:{...record,file_id}},"circle",c)).status,200);
  assert.equal((await s.request("finish",{...identity,fixture_verified:true},"circle",c)).status,409);
  for(let n=0;n<2;n++)assert.equal((await (await s.request("fixture-cleanup",identity,"circle",c)).json()).cleaned,true);
  const status=await (await s.request("status",{job_id:job})).json();
  assert.equal(status.drive_uploaded,true);assert.equal(status.fixture_cleaned,true);
 }finally{await s.close();}
});
test("ordinary credential fixtures cannot acquire upload access",{timeout:60000},async()=>{
 const s=await setup();try{
  await s.request("init");await s.request("admit-fixture",{probe_id:probe});
  const c=await signed("circle"),identity={job_id:job,worker_job_id:worker};
  await s.request("claim",identity,"circle",c);
  assert.equal((await s.request("upload-access",identity,"circle",c)).status,409);
  assert.equal((await s.request("fixture-cleanup",identity,"circle",c)).status,409);
  assert.equal((await s.request("admit-drive-fixture",{probe_id:probe})).status,409);
 }finally{await s.close();}
});

async function production(){
 const s=await setup({RUNTIME_MODE:"production",RUNTIME_EXPORT_ENABLED:"1",RUNTIME_TELEGRAM_ENABLED:"1",TELEGRAM_WEBHOOK_SECRET:"S".repeat(48),TELEGRAM_BOT_TOKEN:"123456789:"+"T".repeat(36)});
 assert.equal((await s.request("init")).status,200);return s;
}
async function handoff(s){
 await s.db.prepare("INSERT INTO runtime_entry_handoff VALUES(?,?,?,?,?,?,?,?,?)").bind(owner,"b".repeat(64),"c".repeat(64),now-20,now-30,now-10,0,0,100).run();
}
const realRequest={request_id:"d".repeat(32),profile:"default",target:"123456",version:""};
function exportProof(id){
 return {schema:"circleci-private-delivery-v1",status:"encrypted_artifact_ready",provider:"circleci",
  job_id:id,request_id:realRequest.request_id,run_id:run,worker_job_id:worker,source_commit:source,account_profile:"default",
  app_id:"123456",requested_version:"",resolved_version:"",external_version_id:"",
  plaintext_verified:true,runtime_verified:false,account_data_removed:true,plaintext_published:false,
  encrypted_images:1,decrypted_pages:1,plaintext_bytes:5496,
  plaintext_sha256:"85025bd1cfea42339ed38b09e9580e1094b2949153c83c81e66d9b1ad9043e93",
  ciphertext_bytes:6000,ciphertext_sha256:"e".repeat(64),
  recipient:"age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d",filename:"Migration_ARM_Probe.ipa"};
}
test("production admission requires sealed state and preserves one logical dispatch",{timeout:60000},async()=>{
 const s=await production();try{
  const blocked=await s.request("admit-export",realRequest);assert.equal(blocked.status,409);
  assert.equal((await blocked.json()).code,"runtime_handoff_required");
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs").first()).n,0);
  await handoff(s);
  const admitted=await (await s.request("admit-export",realRequest)).json();assert.equal(admitted.ok,true);
  assert.equal(admitted.state,"submitted");
  for(let i=0;i<3;i++)assert.equal((await (await s.request("admit-export",realRequest)).json()).job_id,admitted.job_id);
  assert.equal((await s.request("admit-export",{...realRequest,target:"654321"})).status,409);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
  assert.equal((await s.request("admit-fixture",{probe_id:probe})).status,409);
  assert.equal((await s.request("admit-export",{...realRequest,profile:"cn"})).status,409);
  assert.equal((await s.request("admit-export",{request_id:"tf_"+"e".repeat(32),profile:"tf",target:"yoNuHexZ",version:""})).status,409);
 }finally{await s.close();}
});
test("production lifecycle binds profile lease, immutable proof, registered file and private retrieval",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);const id=(await (await s.request("admit-export",realRequest)).json()).job_id;
  const identity={job_id:id,worker_job_id:worker},c=await signed("circle"),g=await signed("github");
  const claim=await (await s.request("claim",identity,"circle",c)).json();assert.equal(claim.task_kind,"export");
  assert.equal(claim.task.profile,"default");assert.equal(claim.task.request_id,realRequest.request_id);
  const requested=await (await s.request("lease-request",{...identity,recipient:"age1"+"q".repeat(58),nonce:"c".repeat(32),expires_at:now+300},"circle",c)).json();
  assert.equal(requested.context.profile,"default");
  const pub={job_id:id,publisher_run_id:publisher};
  await s.request("publisher/pending",pub,"github",g);
  const packet={...pub,context:requested.context,ciphertext:btoa("age-encryption.org/v1\nsynthetic-test-only")};
  assert.equal((await s.request("publisher/publish",packet,"github",g)).status,200);
  assert.equal((await s.request("lease-consumed",identity,"circle",c)).status,200);
  assert.equal((await s.db.prepare("SELECT ciphertext FROM runtime_credential_leases WHERE job_id=?").bind(id).first()).ciphertext,null);
  const proof=exportProof(id);
  for(const changed of [{plaintext_verified:false},{account_profile:"cn"},{source_commit:"b".repeat(40)},{app_id:"654321"},{encrypted_images:0},{decrypted_pages:0},{account_data_removed:false},{runtime_verified:true},{requested_version:"1.2"}])
   assert.equal((await s.request("plaintext-proof",{...identity,receipt:{...proof,...changed}},"circle",c)).status,409);
  const saved=await s.request("plaintext-proof",{...identity,receipt:proof},"circle",c);assert.equal(saved.status,200,await saved.text());
  assert.equal((await s.request("plaintext-proof",{...identity,receipt:{...proof,plaintext_sha256:"f".repeat(64)}},"circle",c)).status,409);
  const record={filename:proof.filename,bytes:proof.plaintext_bytes,sha256:proof.plaintext_sha256},file_id="FIXTURE_FILE_12345";
  const state={job_id:id,owner:"fixture@example.invalid",record};
  for(const item of [{stage:"start_intent"},{stage:"uploading",session:"https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=SYNTHETIC_12345678"},
   {stage:"uploaded",file_id},{stage:"registration_intent",file_id,registration_origin:origin}]){
   const r=await s.request("upload-journal",{...identity,action:"put",state:{...state,...item}},"circle",c);assert.equal(r.status,200,await r.text());
  }
  const registered=await s.request("upload-register",{...identity,record:{...record,file_id}},"circle",c);assert.equal(registered.status,200,await registered.text());
  assert.equal((await s.request("owner-get",{job_id:id})).status,409);
  assert.equal((await s.request("export-finish",{...identity,receipt:proof},"circle",c)).status,409);
  const finished=await s.request("export-finish",{...identity,receipt:{...proof,private_delivery:{...record,file_id}}},"circle",c);assert.equal(finished.status,200);assert.equal((await finished.json()).notification_confirmed,true);
  const repeated=await s.request("export-finish",{...identity,receipt:{...proof,private_delivery:{...record,file_id}}},"circle",c);
  assert.equal(repeated.status,200);assert.equal((await s.mf.dispatchFetch(origin+"/fixture-drive").then(r=>r.json())).notifications,1);
  const completed=await (await s.request("status",{job_id:id},"admin",secret,{"x-fixture-terminal":"1"})).json();assert.equal(completed.state,"completed");
  const link=await (await s.request("owner-get",{job_id:id})).json();assert.equal(link.ok,true);
  assert.equal(link.url,"https://drive.google.com/file/d/"+file_id+"/view");
  const callback={update_id:120,callback_query:{id:"synthetic-get",from:{id:Number(owner),is_bot:false},
   message:{message_id:15,date:now,chat:{id:Number(owner),type:"private"},from:{id:123456789,is_bot:true}},data:"rt:get:"+id.slice(6)}};
  const result=await s.mf.dispatchFetch(origin+"/telegram",{method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":"S".repeat(48)},body:JSON.stringify(callback)});
  assert.equal(result.status,200,await result.clone().text());
  const card=await result.json();assert.equal(card.method,"editMessageText");
  assert.ok(card.text.includes("文件已准备好"));assert.ok(!card.text.includes(id));
  assert.equal(card.reply_markup.inline_keyboard[0][0].url,link.url);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-drive").then(r=>r.json())).notifications,1);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-drive").then(r=>r.json())).deleted,false);
 }finally{await s.close();}
});
test("cancellation stops checkpoints and waits for terminal confirmation",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);const id=(await (await s.request("admit-export",realRequest)).json()).job_id;
  const c=await signed("circle"),identity={job_id:id,worker_job_id:worker};
  await s.request("claim",identity,"circle",c);
  assert.equal((await (await s.request("checkpoint",{...identity,stage:"downloading"},"circle",c)).json()).proceed,true);
  const callback={update_id:121,callback_query:{id:"synthetic-cancel",from:{id:Number(owner),is_bot:false},
   message:{message_id:16,date:now,chat:{id:Number(owner),type:"private"},from:{id:123456789,is_bot:true}},data:"rt:cancel:"+id.slice(6)}};
  const reply=await s.mf.dispatchFetch(origin+"/telegram",{method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":"S".repeat(48)},body:JSON.stringify(callback)});
  const cancelled=await reply.json();assert.equal(cancelled.method,"editMessageText");assert.ok(cancelled.text.includes("取消"));
  assert.equal((await (await s.request("owner-cancel",{job_id:id})).json()).state,"cancel_pending");
  assert.equal((await (await s.request("checkpoint",{...identity,stage:"working"},"circle",c)).json()).proceed,false);
  assert.equal((await s.request("lease-request",{...identity,recipient:"age1"+"q".repeat(58),nonce:"c".repeat(32),expires_at:now+300},"circle",c)).status,409);
  await s.request("owner-cancel",{job_id:id});
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_cancel_intents").first()).n,1);
  const closed=await (await s.request("status",{job_id:id},"admin",secret,{"x-fixture-terminal":"1","x-fixture-failed":"1"})).json();assert.equal(closed.state,"closed");
 }finally{await s.close();}
});
test("owner webhook deduplicates links and rejects consumed or foreign updates",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);
  const message=(uid,user=Number(owner))=>({update_id:uid,message:{date:now,chat:{id:user,type:"private"},from:{id:user,is_bot:false},text:"https://apps.apple.com/de/app/id123456"}});
  const post=(body,token="S".repeat(48))=>s.mf.dispatchFetch(origin+"/telegram",{method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":token},body:JSON.stringify(body)});
  assert.equal((await post(message(101),"wrong")).status,401);
  assert.equal((await post(message(99))).status,200);assert.equal((await post(message(101,99999))).status,200);
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs").first()).n,0);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).typingActions,0);
  for(let i=0;i<3;i++)assert.equal((await post(message(101))).status,200);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).typingActions,3);
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs").first()).n,1);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
 }finally{await s.close();}
});

test("owner retrieval survives source upgrades while worker identity remains source-bound",{timeout:60000},async()=>{
 const s=await setup({RUNTIME_MODE:"production",RUNTIME_EXPORT_ENABLED:"1",RUNTIME_SOURCE_SHA:"b".repeat(40)});
 try{
  assert.equal((await s.request("init")).status,200);await handoff(s);
  const p=exportProof(job);
  await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline,plaintext_sha256,plaintext_bytes,filename,file_id,link_expires,finished_at) VALUES(?,?,?,'default','export','123456','',?,'completed',?,?,?,?,?,'FIXTURE_FILE_12345',?,?)")
   .bind(job,owner,realRequest.request_id,source,now-100,now+100,p.plaintext_sha256,p.plaintext_bytes,p.filename,now+1000,now-90).run();
  const link=await s.request("owner-get",{job_id:job});assert.equal(link.status,200,await link.text());
  const status=await (await s.request("status",{job_id:job})).json();assert.equal(status.state,"completed");
  const c=await signed("circle");
  assert.equal((await s.request("claim",{job_id:job,worker_job_id:worker},"circle",c)).status,409);
 }finally{await s.close();}
});

test("managed links retain profile/version routing and reject foreign URL targets",()=>{
 assert.deepEqual(parseTask("123456"),{profile:"default",target:"123456",version:""});
 assert.deepEqual(parseTask("/version https://apps.apple.com/cn/app/id123456 889619746"),{profile:"cn",target:"123456",version:"889619746"});
 assert.deepEqual(parseTask("itms-beta://testflight.apple.com/join/SyntheticInvite"),{profile:"tf",target:"SyntheticInvite",version:""});
 for(const text of ["http://apps.apple.com/app/id123456","https://apps.apple.com.evil/app/id123456",
  "https://user:pass@apps.apple.com/app/id123456","https://testflight.apple.com/join/SyntheticInvite?redirect=https://evil.invalid",
  "/version https://testflight.apple.com/join/SyntheticInvite 1.2"]){
  assert.equal(parseTask(text),null);
 }
});

function catalogProof(claim,before="",id="123456789",next=""){
 const t=claim.task;
 return {schema:"circleci-version-catalog-v1",job_id:t.job_id,request_id:t.request_id,run_id:t.run_id,
  worker_job_id:t.worker_job_id,source_sha:t.source_sha,account_profile:t.profile,app_id:t.target,
  before,next_before:next,total:20,rows:[{id,version:"1.2.3",date:"2026-10-01"}]};
}
async function seedCatalog(s,{tag="1",profile="cn",before="",page=0,version="323456789",next="223456789"}={}){
 const request_id=(profile==="cn"?"cn_":"")+tag.repeat(32),id="pilot_"+tag.repeat(32);
 const task={job_id:id,request_id,run_id:run,worker_job_id:worker,source_sha:source,profile,target:"123456"};
 const result=catalogProof({task},before,version,next);
 await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline,finished_at) VALUES(?,?,?,?,'export',?,'',?,'completed',?,?,?)")
  .bind(id,owner,request_id,profile,task.target,source,now-120,now+1000,now-100).run();
 await s.db.prepare("INSERT INTO runtime_catalog_specs(job_id,before_id,page_index,result_json) VALUES(?,?,?,?)").bind(id,before,page,JSON.stringify(result)).run();
 return {id,result};
}
const catalogRequest=(tag="2",profile="cn")=>({request_id:(profile==="cn"?"cn_":"")+tag.repeat(32),profile,target:"123456"});
async function viewOf(s,request_id){
 return s.db.prepare("SELECT * FROM runtime_catalog_views WHERE request_id=?").bind(request_id).first();
}
test("catalog claim leases only metadata credentials, rejects upload and completes an immutable page",{timeout:60000},async()=>{
 for(const profile of ["default","cn"]){
  const s=await production();try{
   await handoff(s);const input=catalogRequest("2",profile);
   const admitted=await (await s.request("catalog-open",input)).json();assert.equal(admitted.ok,true,JSON.stringify(admitted));
   const identity={job_id:admitted.job_id,worker_job_id:worker},c=await signed("circle"),g=await signed("github");
   const claim=await (await s.request("claim",identity,"circle",c)).json();assert.equal(claim.task_kind,"catalog");
   assert.equal(claim.catalog_before,"");
   const requested=await (await s.request("lease-request",{...identity,recipient:"age1"+"q".repeat(58),nonce:"c".repeat(32),expires_at:now+300},"circle",c)).json();
   assert.equal(requested.context.profile,profile+"_catalog");
   const pub={job_id:identity.job_id,publisher_run_id:publisher};
   await s.request("publisher/pending",pub,"github",g);
   assert.equal((await s.request("publisher/publish",{...pub,context:requested.context,ciphertext:btoa("age-encryption.org/v1\nsynthetic-test-only")},"github",g)).status,200);
   await s.request("lease-consumed",identity,"circle",c);
   for(const path of ["upload-access","fixture-cleanup","tf-permit","plaintext-proof","export-finish"]){
    const extra=path==="tf-permit"?{action:"claim",args:{}}:["plaintext-proof","export-finish"].includes(path)?{receipt:{}}:{};
    assert.equal((await s.request(path,{...identity,...extra},"circle",c)).status,409);
   }
   const receipt=catalogProof(claim,"","323456789","223456789");
   const finished=await s.request("catalog-finish",{...identity,receipt},"circle",c);assert.equal(finished.status,200,await finished.clone().text());
   assert.equal((await finished.json()).notification_confirmed,true);
   assert.equal((await s.request("catalog-finish",{...identity,receipt},"circle",c)).status,200);
   assert.equal((await s.request("catalog-finish",{...identity,receipt:{...receipt,total:21}},"circle",c)).status,409);
   const view=await viewOf(s,input.request_id);assert.equal(view.state,"sent");
   assert.equal((await s.mf.dispatchFetch(origin+"/fixture-menus").then(r=>r.json())).length,1);
   const status=await (await s.request("status",{job_id:identity.job_id},"admin",secret,{"x-fixture-terminal":"1"})).json();
   assert.equal(status.state,"completed");assert.equal(status.catalog_ready,true);assert.equal(status.export_verified,false);
   assert.equal((await s.request("owner-get",{job_id:identity.job_id})).status,409);
  }finally{await s.close();}
 }
});
test("cached pages bind Telegram owner, bot message and whole-list single selection",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);
  await seedCatalog(s);await seedCatalog(s,{tag:"4",before:"223456789",page:1,version:"123456789",next:""});
  const input=catalogRequest();assert.equal((await s.request("catalog-open",input)).status,200);
  const view=await viewOf(s,input.request_id);assert.equal(view.message_id,11);
  const action=(tag,letter,version_id="",v=view)=>({request_id:"cn_"+tag.repeat(32),view_id:v.view_id,message_id:v.message_id,action:letter,version_id});
  assert.equal((await s.request("catalog-action",{...action("3","n"),message_id:999})).status,409);
  assert.equal((await s.request("catalog-action",action("3","n"))).status,200);
  const second=await viewOf(s,"cn_"+"3".repeat(32));assert.equal(second.family_id,view.family_id);
  assert.equal((await s.request("catalog-action",action("5","p","",second))).status,200);
  const previous=await viewOf(s,"cn_"+"5".repeat(32));assert.equal(previous.family_id,view.family_id);
  const callback=(uid,user=Number(owner),bot=123456789,message=view.message_id,version="323456789")=>({update_id:uid,callback_query:{id:"synthetic-callback",from:{id:user,is_bot:false},
   message:{message_id:message,date:now,chat:{id:user,type:"private"},from:{id:bot,is_bot:true}},
   data:"cv:"+view.view_id+":v:"+version}});
  const post=value=>s.mf.dispatchFetch(origin+"/telegram",{method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":"S".repeat(48)},body:JSON.stringify(value)});
  for(const bad of [callback(99),callback(101,99999),callback(101,Number(owner),99999),callback(101,Number(owner),123456789,999)]){
   await post(bad);
  }
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs WHERE NOT EXISTS(SELECT 1 FROM runtime_catalog_specs s WHERE s.job_id=runtime_jobs.job_id)").first()).n,0);
  assert.equal((await post(callback(102))).status,200);
  assert.equal((await post(callback(102))).status,200);
  assert.equal((await s.request("catalog-action",action("6","v","123456789",second))).status,409);
  assert.equal((await s.request("catalog-action",action("7","n","",previous))).status,409);
  const exports=await s.db.prepare("SELECT * FROM runtime_jobs WHERE NOT EXISTS(SELECT 1 FROM runtime_catalog_specs s WHERE s.job_id=runtime_jobs.job_id)").all();
  assert.equal(exports.results.length,1);assert.equal(exports.results[0].profile,"cn");assert.equal(exports.results[0].version,"323456789");
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
 }finally{await s.close();}
});
test("explicit refresh queues one metadata job while cached reopening performs no Apple dispatch",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);await seedCatalog(s);
  const input=catalogRequest();await s.request("catalog-open",input);
  await s.request("catalog-open",input);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,0);
  const view=await viewOf(s,input.request_id),refresh={request_id:"cn_"+"3".repeat(32),view_id:view.view_id,message_id:view.message_id,action:"r",version_id:""};
  const result=await (await s.request("catalog-action",refresh)).json();assert.equal(result.ok,true,JSON.stringify(result));
  await s.request("catalog-action",refresh);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
  const spec=await s.db.prepare("SELECT before_id,page_index FROM runtime_catalog_specs WHERE job_id=?").bind(result.job_id).first();
  assert.deepEqual(spec,{before_id:"",page_index:0});
  const denied=await (await s.request("catalog-action",{...refresh,request_id:"cn_"+"4".repeat(32)})).json();
  assert.equal(denied.code,"runtime_catalog_rate_limit");
 }finally{await s.close();}
});
test("uncertain catalog notification is never repeated; a new owner command may reopen cache",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);await seedCatalog(s);
  const request=catalogRequest();
  const first=await (await s.request("catalog-open",request,"admin",secret,{"x-fixture-notify-unknown":"1"})).json();
  assert.equal(first.menu_notified,false);assert.equal((await viewOf(s,request.request_id)).state,"unknown");
  assert.equal((await (await s.request("catalog-open",request)).json()).menu_notified,false);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-menus").then(r=>r.json())).length,1);
  assert.equal((await (await s.request("catalog-open",catalogRequest("3"))).json()).menu_notified,true);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,0);
 }finally{await s.close();}
});
test("owner catalog requests bypass daily totals while staging still rejects them",{timeout:60000},async()=>{
 const disabled=await setup();try{
  await disabled.request("init");assert.equal((await disabled.request("catalog-open",catalogRequest())).status,409);
 }finally{await disabled.close();}
 const s=await production();try{
  await handoff(s);
  for(let i=0;i<20;i++){
   const id="pilot_"+i.toString(16).padStart(32,"0"),rid=i.toString(16).padStart(32,"0");
   await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline) VALUES(?,?,?,'cn','export','123456','',?,'closed',?,?)").bind(id,owner,"cn_"+rid,source,Math.floor(now/86400)*86400,now+1000).run();
   await s.db.prepare("INSERT INTO runtime_catalog_specs(job_id,before_id,page_index) VALUES(?,'',0)").bind(id).run();
  }
  const catalog=await s.request("catalog-open",catalogRequest("f","default"));assert.equal(catalog.status,200,await catalog.clone().text());
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_catalog_specs").first()).n,21);
  assert.equal((await s.request("admit-export",realRequest)).status,200);
 }finally{await s.close();}
});
test("catalog proof rejects imprecise numeric IDs, backward cursors and invalid dates",()=>{
 const task={kind:"catalog",job_id:job,request_id:"d".repeat(32),run_id:run,worker_job_id:worker,source_sha:source,profile:"default",target:"123456",catalog:{before_id:"99999999999999999999"}};
 const value=catalogProof({task},"99999999999999999999","99999999999999999998","99999999999999999997");
 assert.doesNotThrow(()=>verifyCatalog(task,value));
 for(const change of [{next_before:value.before},{rows:[...value.rows,...value.rows]},{rows:[{...value.rows[0],date:"2026-02-30"}]},{app_id:"654321"},{rows:[{...value.rows[0],id:123456789}]}]){
  assert.throws(()=>verifyCatalog(task,{...value,...change}),/runtime_catalog/);
 }
});

test("the scheduled reconciler releases a known ended catalog and dispatches its queued export once",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);const seeded=await seedCatalog(s,{profile:"default"});
  await s.db.prepare("UPDATE runtime_jobs SET state='link_ready',run_id=?,worker_job_id=?,workflow_id=? WHERE job_id=?").bind(run,worker,workflow,seeded.id).run();
  const admitted=await (await s.request("admit-export",realRequest)).json();assert.equal(admitted.state,"waiting");
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,0);
  for(let i=0;i<2;i++){
   const result=await s.mf.dispatchFetch(origin+"/fixture-tick",{headers:{"x-fixture-terminal":"1"}});
   assert.equal(result.status,200,await result.text());
  }
  const old=await s.db.prepare("SELECT state FROM runtime_jobs WHERE job_id=?").bind(seeded.id).first();
  const next=await s.db.prepare("SELECT state,run_id FROM runtime_jobs WHERE job_id=?").bind(admitted.job_id).first();
  assert.equal(old.state,"completed");assert.equal(next.state,"submitted");assert.notEqual(next.run_id,run);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
 }finally{await s.close();}
});

test("task pages stay bounded, owner-private and below eight D1 calls without provider queries",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);
  for(let i=0;i<6;i++){
   const id="pilot_"+(100+i).toString(16).padStart(32,"0");
   await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline,finished_at,file_id,filename,plaintext_bytes,link_expires) VALUES(?,?,?,'default','export','123456','',?,'completed',?,?,?,'SYNTHETIC_FILE',?,342632968,?)")
    .bind(id,i===5?"99999":owner,(100+i).toString(16).padStart(32,"0"),source,now-i,now+1000,now-10,"Synthetic "+i+"_1.0.ipa",now+3600).run();
  }
  await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline) VALUES(?,?,?,'default','export','999999','',?,'closed',?,?)")
   .bind("pilot_"+"f".repeat(32),owner,"f".repeat(32),source,now,now+1000).run();
  const post=body=>s.mf.dispatchFetch(origin+"/telegram",{method:"POST",
   headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":"S".repeat(48),"x-fixture-query-budget":"1"},
   body:JSON.stringify(body)});
  const message=text=>({update_id:101,message:{date:now,chat:{id:Number(owner),type:"private"},from:{id:Number(owner),is_bot:false},text}});
  const result=await post(message("/status"));assert.equal(result.status,200,await result.clone().text());
  const answer=await result.json();assert.ok(answer.text.startsWith("已完成"));
  assert.equal((answer.text.match(/^[1-3]\. /gm)||[]).length,3);
  assert.ok(answer.text.includes("Synthetic 0"));assert.ok(!answer.text.includes("Synthetic 3"));
  assert.ok(!answer.text.includes("Synthetic 5"));assert.ok(!answer.text.includes("pilot_"));
  assert.ok(!answer.text.includes("999999"));
  assert.ok(answer.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="rt:list:c:1"));
  const callback=(data,user=Number(owner),bot=123456789)=>({update_id:102,callback_query:{id:"synthetic-navigation",from:{id:user,is_bot:false},
   message:{message_id:12,date:now,chat:{id:user,type:"private"},from:{id:bot,is_bot:true}},data}});
  const second=await post(callback("rt:list:c:1"));assert.equal(second.status,200);
  const page=await second.json();assert.equal(page.method,"editMessageText");assert.equal(page.message_id,12);
  assert.ok(page.text.includes("Synthetic 3"));assert.ok(page.text.includes("Synthetic 4"));assert.ok(!page.text.includes("Synthetic 5"));
  assert.equal((page.text.match(/^[1-3]\. /gm)||[]).length,2);
  const history=await (await post(callback("rt:list:h:0"))).json();assert.ok(!history.text.includes("999999"));assert.ok(history.text.includes("暂无任务"));
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs WHERE owner_id=? AND state='closed'").bind(owner).first()).n,1);
  for(const bad of [callback("rt:list:c:0",99999),callback("rt:list:c:0",Number(owner),99999),callback("rt:list:c:-1"),callback("rt:list:c:99999")]){
   const reply=await (await post(bad)).json();assert.equal(reply.method,undefined);
  }
  const home=await (await post(message("/start"))).json();assert.ok(home.text.includes("\n\n"));assert.ok(home.reply_markup.inline_keyboard.length);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,0);
 }finally{await s.close();}
});

test("the configured owner can submit after daily success and failure totals are exhausted",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);
  for(let i=0;i<24;i++){
   const tag=(300+i).toString(16).padStart(32,"0");
   await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline) VALUES(?,?,?,'default','export','123456','',?,?,?,?)")
    .bind("pilot_"+tag,owner,tag,source,i%2?"closed":"completed",Math.floor(now/86400)*86400,now+1000).run();
  }
  const response=await s.request("admit-export",realRequest);assert.equal(response.status,200,await response.clone().text());
  const row=await s.db.prepare("SELECT state FROM runtime_jobs WHERE owner_id=? AND request_id=?").bind(owner,realRequest.request_id).first();
  assert.equal(row.state,"submitted");
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs WHERE owner_id=?").bind(owner).first()).n,25);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,1);
 }finally{await s.close();}
});
test("owner daily exemption never bypasses the thirty-job waiting queue",{timeout:60000},async()=>{
 const s=await production();try{
  await handoff(s);
  for(let i=0;i<30;i++){
   const tag=(400+i).toString(16).padStart(32,"0");
   await s.db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline) VALUES(?,?,?,'default','export','123456','',?,'waiting',?,?)")
    .bind("pilot_"+tag,owner,tag,source,now-120,now+1000).run();
  }
  const response=await s.request("admit-export",realRequest);assert.equal(response.status,409);
  assert.equal((await response.json()).code,"runtime_queue_limit");
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs WHERE owner_id=?").bind(owner).first()).n,30);
  assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json())).nativePosts,0);
  const catalog=await s.request("catalog-open",catalogRequest("f","default"));assert.equal(catalog.status,409);
  assert.equal((await catalog.json()).code,"runtime_queue_limit");
  assert.equal((await s.db.prepare("SELECT count(*) n FROM runtime_jobs WHERE owner_id=?").bind(owner).first()).n,30);
 }finally{await s.close();}
});
