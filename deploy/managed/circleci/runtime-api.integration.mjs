// CI only: actual workerd/D1, real RSA tokens, synthetic provider transport.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {mkdtemp,mkdir,copyFile,writeFile,rm} from "node:fs/promises";
import {join} from "node:path";
import {tmpdir} from "node:os";
import {Miniflare} from "miniflare";
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
async function setup(){
 const folder=await mkdtemp(join(tmpdir(),"runtime-api-"));
 const files=["runtime-api.mjs","runtime-schema.mjs","runtime-auth.mjs","runtime-lease.mjs","runtime-upload.mjs",
  "oidc.mjs","github-oidc.mjs"];
 await Promise.all(files.map(name=>copyFile(new URL(name,import.meta.url),join(folder,name))));
 const entry=join(folder,"entry.mjs");
 await writeFile(entry,`
 import {handleRuntimeV2} from "./runtime-api.mjs";
 const C=${JSON.stringify(C)},G=${JSON.stringify(G)};
 const run=${JSON.stringify(run)},workflow=${JSON.stringify(workflow)},worker=${JSON.stringify(worker)};
 let nativePosts=0,publisherPosts=0;
 export default {async fetch(request,env){
  if(new URL(request.url).pathname==="/fixture-count")return Response.json({nativePosts,publisherPosts});
  async function provider(url,options){
   new Request(url,options);
   if(options.redirect!=="manual")throw Error("redirect_policy");
   if(url==="https://oidc.circleci.com/org/"+C.org+"/.well-known/jwks-pub.json")
    return Response.json({keys:[${JSON.stringify(circle.jwk)}]});
   if(url===G.issuer+"/.well-known/jwks")return Response.json({keys:[${JSON.stringify(github.jwk)}]});
   if(url==="https://circleci.com/api/v3/runs"){
    nativePosts++;
    const params=JSON.parse(options.body).data.attributes.parameters;
    if(params.managed_runtime!==true||params.dispatch_probe!==false||params.managed_source!==${JSON.stringify(source)})
     throw Error("bad_native_parameters");
    if(request.headers.get("x-fixture-unknown")==="1")throw Error("ambiguous_network");
    return Response.json({data:{id:run}},{status:201});
   }
   if(url==="https://circleci.com/api/v3/runs/"+run){
    const terminal=request.headers.get("x-fixture-terminal")==="1";
    return Response.json({data:{id:run,attributes:{phase:terminal?"ended":"started",current_outcome:terminal?"succeeded":null},
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
    if(value.inputs.profile!=="synthetic"||value.inputs.job_id!==${JSON.stringify(job)})throw Error("wrong_publisher_profile");
    return new Response(null,{status:204});
   }
   if(url==="https://api.github.com/repos/"+G.repository+"/actions/runs/"+${JSON.stringify(publisher)})
    return Response.json({id:Number(${JSON.stringify(publisher)}),repository:{id:Number(G.repository_id)},actor:{id:Number(G.owner_id)},
     event:"workflow_dispatch",run_attempt:1,head_sha:${JSON.stringify(source)},head_branch:C.ref.slice(11),
     status:"in_progress",path:G.workflows.lease,display_title:"CircleCI lease "+${JSON.stringify(job)}});
   throw Error("unexpected_provider_request");
  }
  return handleRuntimeV2(request,env,${now},provider);
 }};
 `);
 const mf=new Miniflare({modules:true,modulesRoot:folder,scriptPath:entry,compatibilityDate:"2026-07-30",
  cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"99999999-9999-4999-8999-999999999999"},
  bindings:{RUNTIME_MODE:"staging",RUNTIME_CONTROL_ORIGIN:origin,RUNTIME_SOURCE_SHA:source,RUNTIME_OWNER_ID:owner,
   CIRCLECI_CONTROL_TOKEN:secret,CIRCLECI_API_TOKEN:"synthetic-circle-token",RUNTIME_GH_TOKEN:"synthetic-github-token"}});
 const db=await mf.getD1Database("DB");
 const request=(path,value={},kind="admin",token=secret,extra={})=>mf.dispatchFetch(origin+"/v2/runtime/"+path,{
  method:"POST",headers:{"content-type":"application/json",
   [kind==="circle"?"x-ipazake-job-token":kind==="github"?"x-ipazake-github-token":"x-ipazake-control-token"]:token,...extra},
  body:JSON.stringify(value)});
 const close=async()=>{await mf.dispose();await rm(folder,{recursive:true,force:true});};
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
  assert.deepEqual(await s.mf.dispatchFetch(origin+"/fixture-count").then(r=>r.json()),{nativePosts:1,publisherPosts:1});
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
