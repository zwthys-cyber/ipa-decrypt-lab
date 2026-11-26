// CI only: actual workerd routes/D1 and RSA signatures; all provider HTTP is synthetic.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {readFile,mkdtemp,mkdir,copyFile,writeFile,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {Miniflare} from "miniflare";
import {TRUST} from "./oidc.mjs";
globalThis.crypto??=webcrypto;
const origin="https://ipazake-free-control-pilot.fixture.workers.dev",secret="C".repeat(48);
const source="a".repeat(40),owner="12345",probe="1".repeat(32),job="pilot_"+probe;
const run="12345678-1234-1234-1234-123456789abc",workflow="23456789-1234-1234-1234-123456789abc";
const workerJob="34567890-1234-1234-1234-123456789abc",otherJob="45678901-1234-1234-1234-123456789abc";
const now=Math.floor(Date.now()/1000),base=new URL("../free-pilot/",import.meta.url);
const pair=await crypto.subtle.generateKey({name:"RSASSA-PKCS1-v1_5",modulusLength:2048,
  publicExponent:new Uint8Array([1,0,1]),hash:"SHA-256"},true,["sign","verify"]);
const jwk=await crypto.subtle.exportKey("jwk",pair.publicKey);jwk.kid="fixture";
const encode=x=>Buffer.from(x).toString("base64url");
async function token(id=workerJob,changes={}){
  const claim={iss:"https://oidc.circleci.com/org/"+TRUST.org,aud:TRUST.org,iat:now-30,exp:now+1800,
    sub:"org:"+TRUST.org+":project:"+TRUST.project+":user:"+TRUST.user+
      ":checkout-source:"+TRUST.source+":checkout-ref:"+TRUST.ref+
      ":config-source:"+TRUST.source+":config-ref:"+TRUST.ref};
  for(const [key,value] of Object.entries({"org-id":TRUST.org,"project-id":TRUST.project,
    "pipeline-id":TRUST.definition,"run-id":run,"job-id":id,"ssh-rerun":false,
    "checkout-source":TRUST.source,"config-source":TRUST.source,"checkout-ref":TRUST.ref,
    "config-ref":TRUST.ref,"context-ids":[]}))claim["oidc.circleci.com/"+key]=value;
  Object.assign(claim,changes);
  const input=encode(JSON.stringify({alg:"RS256",kid:"fixture",typ:"JWT"}))+"."+encode(JSON.stringify(claim));
  return input+"."+encode(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",pair.privateKey,new TextEncoder().encode(input)));
}
async function setup(){
  const folder=await mkdtemp(join(tmpdir(),"circle-control-"));await mkdir(join(folder,"free-pilot"));await mkdir(join(folder,"circleci"));
  await Promise.all(["worker.mjs","private-link.mjs","drive-auth.mjs"].map(name=>copyFile(new URL(name,base),join(folder,"free-pilot",name))));
  await Promise.all(["control.mjs","control-schema.mjs","dispatch.mjs","oidc.mjs"].map(name=>copyFile(new URL(name,import.meta.url),join(folder,"circleci",name))));
  const entry=join(folder,"entry.mjs");
  await writeFile(entry,`
    import {handle} from "./free-pilot/worker.mjs";
    const trust=${JSON.stringify(TRUST)},run=${JSON.stringify(run)},workflow=${JSON.stringify(workflow)},worker=${JSON.stringify(workerJob)};
    let posts=0;
    export default {async fetch(request,env){
      const u=new URL(request.url);
      if(u.pathname==="/fixture-count")return Response.json({posts});
      async function provider(url,init){
        if(url==="https://oidc.circleci.com/org/"+trust.org+"/.well-known/jwks-pub.json")
          return Response.json({keys:[${JSON.stringify(jwk)}]});
        if(url==="https://circleci.com/api/v3/runs"&&init.method==="POST"){
          posts++;const p=JSON.parse(init.body).data.attributes.parameters;
          if(p.control_probe_url!==${JSON.stringify(origin)}||!p.control_probe_job?.startsWith("pilot_"))throw Error("callback_missing");
          if(request.headers.get("x-fixture-ambiguous")==="1")throw Error("accepted_but_response_lost");
          return Response.json({data:{id:run}},{status:201});
        }
        if(url==="https://circleci.com/api/v3/runs/"+run){
          const ended=request.headers.get("x-fixture-terminal")==="1";
          return Response.json({data:{id:run,attributes:{phase:ended?"ended":"started",current_outcome:ended?"succeeded":null},
            references:{project:{id:trust.project},pipeline:{id:trust.definition},event:{attributes:{vcs:{
              origin_repository_url:"https://"+trust.source,target_repository_url:"https://"+trust.source,
              branch:trust.ref.slice(11),revision:request.headers.get("x-fixture-wrong-source")==="1"?"b".repeat(40):${JSON.stringify(source)}
            }}}}}});
        }
        if(url==="https://circleci.com/api/v2/pipeline/"+run+"/workflow")
          return Response.json({items:[{id:workflow,name:"synthetic-dispatch-probe",pipeline_id:run}]});
        if(url==="https://circleci.com/api/v2/workflow/"+workflow+"/job")
          return Response.json({items:[{id:worker,name:"dispatch-contract-probe",status:"running"}]});
        throw Error("unexpected_provider_request");
      }
      return handle(request,env,${now},undefined,provider);
    }};
  `);
  const mf=new Miniflare({modules:true,modulesRoot:folder,scriptPath:entry,compatibilityDate:"2026-07-30",
    cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"55555555-5555-4555-8555-555555555555"},
    bindings:{PILOT_ENABLED:"0",PILOT_LINK_ENABLED:"0",PILOT_RUNTIME_MODE:"probe",RUNTIME_OWNER_ID:owner,
      CIRCLECI_SOURCE_SHA:source,PILOT_CONTROL_ORIGIN:origin,CIRCLECI_CONTROL_TOKEN:secret,
      CIRCLECI_API_TOKEN:"synthetic-token-no-account"}});
  const db=await mf.getD1Database("DB");
  for(const name of ["0001_pilot.sql","0002_links.sql","0003_links_10gb.sql","0004_retired_links.sql"]){
    const sql=await readFile(new URL("migrations/"+name,base),"utf8");
    const rows=sql.replace(/^--.*$/gm,"").split(";").map(x=>x.trim()).filter(Boolean);
    assert.ok((await db.batch(rows.map(sql=>db.prepare(sql)))).every(x=>x.success));
  }
  const request=(path,body={},bearer=secret,extra={})=>mf.dispatchFetch(origin+path,{method:"POST",
    headers:{"content-type":"application/json",authorization:"Bearer "+bearer,...extra},body:JSON.stringify(body)});
  const close=async()=>{await mf.dispose();await rm(folder,{recursive:true,force:true});};
  return {mf,db,request,close};
}
test("real workerd: signed claim, idempotent callback and verified terminal readback",{timeout:60000},async()=>{
  const s=await setup();try{
    assert.equal((await s.request("/v1/runtime/probe-init",{},"wrong")).status,401);
    assert.equal((await s.request("/v1/runtime/probe-init")).status,200);
    assert.equal((await s.request("/v1/runtime/probe-init")).status,200);
    assert.equal((await s.request("/v1/runtime/probe-submit",{probe_id:probe})).status,201);
    assert.equal((await s.request("/v1/runtime/probe-submit",{probe_id:probe})).status,200);
    assert.equal((await (await s.mf.dispatchFetch(origin+"/fixture-count")).json()).posts,1);
    const jwt=await token(),body={job_id:job,worker_job_id:workerJob};
    let result=await s.request("/v1/runtime/claim",body,jwt);
    assert.equal(result.status,200);
    assert.deepEqual(await result.json(),{ok:true,schema:"circleci-control-task-v1",kind:"synthetic_noop",
      job_id:job,run_id:run,worker_job_id:workerJob,source_sha:source});
    assert.equal((await s.request("/v1/runtime/claim",body,jwt)).status,200);
    assert.equal((await s.request("/v1/runtime/probe-finish",body,jwt)).status,200);
    assert.equal((await s.request("/v1/runtime/probe-finish",body,jwt)).status,200);
    result=await s.request("/v1/runtime/probe-status",{job_id:job},secret,{"x-fixture-terminal":"1"});
    assert.deepEqual(await result.json(),{ok:true,job_id:job,state:"finished",claimed:true,probe_finished:true});
    assert.equal((await s.request("/v1/runtime/claim",body,jwt)).status,409);
    assert.equal((await s.db.prepare("SELECT count(*) n FROM circleci_claims").first()).n,1);
    assert.equal((await s.request("/telegram")).status,503);
  }finally{await s.close();}
});
test("real workerd: wrong JWT, source, rerun and worker cannot obtain a claim",{timeout:60000},async()=>{
  const s=await setup();try{
    await s.request("/v1/runtime/probe-init");await s.request("/v1/runtime/probe-submit",{probe_id:probe});
    const body={job_id:job,worker_job_id:workerJob},jwt=await token();
    assert.equal((await s.request("/v1/runtime/claim",body,"x".repeat(200))).status,409);
    assert.equal((await s.request("/v1/runtime/claim",body,jwt,{"x-fixture-wrong-source":"1"})).status,409);
    assert.equal((await s.request("/v1/runtime/claim",body,await token(workerJob,{"oidc.circleci.com/ssh-rerun":true}))).status,409);
    assert.equal((await s.request("/v1/runtime/claim",{job_id:job,worker_job_id:otherJob},await token(otherJob))).status,409);
    assert.equal((await s.db.prepare("SELECT count(*) n FROM circleci_claims").first()).n,0);
    assert.equal((await s.request("/v1/runtime/probe-finish",body,jwt)).status,409);
  }finally{await s.close();}
});
test("real workerd: ambiguous remote acceptance never posts again",{timeout:60000},async()=>{
  const s=await setup();try{
    await s.request("/v1/runtime/probe-init");
    assert.equal((await s.request("/v1/runtime/probe-submit",{probe_id:probe},secret,{"x-fixture-ambiguous":"1"})).status,409);
    const result=await s.request("/v1/runtime/probe-submit",{probe_id:probe});
    assert.equal((await result.json()).state,"unknown");
    assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(x=>x.json())).posts,1);
    assert.equal((await s.request("/v1/runtime/claim",{job_id:job,worker_job_id:workerJob},await token())).status,409);
  }finally{await s.close();}
});
test("real workerd: additive init preserves old jobs and refuses a legacy ID collision",{timeout:60000},async()=>{
  const s=await setup();try{
    const old="pilot_"+"f".repeat(32);
    await s.db.prepare("INSERT INTO pilot_jobs VALUES(?,?,?,?,?,?,?,?)")
      .bind(old,owner,7,"999999","cn",0,100,"waiting_for_runtime").run();
    await s.db.prepare("INSERT INTO pilot_links(job_id,owner_id,file_id,filename,bytes,sha256,expires_at) VALUES(?,?,?,?,?,?,?)")
      .bind(old,owner,"syntheticFile12345","original.txt",100,"f".repeat(64),now+1000).run();
    assert.equal((await s.request("/v1/runtime/probe-init")).status,200);
    assert.equal((await s.request("/v1/runtime/probe-submit",{probe_id:"f".repeat(32)})).status,409);
    assert.equal((await s.db.prepare("SELECT app_id FROM pilot_jobs WHERE job_id=?").bind(old).first()).app_id,"999999");
    assert.equal((await s.db.prepare("SELECT filename FROM pilot_links WHERE job_id=?").bind(old).first()).filename,"original.txt");
    assert.equal((await s.mf.dispatchFetch(origin+"/fixture-count").then(x=>x.json())).posts,0);
  }finally{await s.close();}
});
test("real workerd: cancelled jobs cannot be claimed; no production credential route exists",{timeout:60000},async()=>{
  const s=await setup();try{
    await s.request("/v1/runtime/probe-init");await s.request("/v1/runtime/probe-submit",{probe_id:probe});
    await s.db.prepare("UPDATE pilot_jobs SET state='cancelled' WHERE job_id=?").bind(job).run();
    assert.equal((await s.request("/v1/runtime/claim",{job_id:job,worker_job_id:workerJob},await token())).status,409);
    assert.equal((await s.request("/v1/runtime/credentials",{})).status,404);
    assert.equal((await s.request("/v1/runtime/probe-submit",{probe_id:probe,owner_id:"54321"})).status,409);
  }finally{await s.close();}
});
