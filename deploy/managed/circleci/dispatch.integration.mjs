// CI only: actual local workerd/D1, synthetic CircleCI transport, no account credentials.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {readFile,mkdtemp,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {Miniflare} from "miniflare";
import {dispatchSynthetic,finishSynthetic,DISPATCH_SQL} from "./dispatch.mjs";
import {TRUST} from "./oidc.mjs";
globalThis.crypto??=webcrypto;
const owner="12345",jobs=["1","2","3"].map(x=>"pilot_"+x.repeat(32));
const source="a".repeat(40),run="12345678-1234-1234-1234-123456789abc";
const config={enabled:"synthetic-only",owner,job:jobs[0],source,now:1000,token:"synthetic-token-no-real-account"};
const sql=(await Promise.all([
  "../free-pilot/migrations/0001_pilot.sql","../free-pilot/migrations/0002_links.sql",
  "./migrations/0001_dispatch.sql"
].map(path=>readFile(new URL(path,import.meta.url),"utf8")))).join("\n");
function make(folder){
  return new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled',{status:503});}}",
    compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,
    d1Databases:{DB:"44444444-4444-4444-8444-444444444444"},...(folder?{d1Persist:folder}:{})});
}
async function setup(mf){
  const db=await mf.getD1Database("DB");
  const statements=sql.replace(/^--.*$/gm,"").split(";").map(x=>x.trim()).filter(Boolean);
  assert.ok((await db.batch(statements.map(x=>db.prepare(x)))).every(x=>x.success));
  for(let n=0;n<jobs.length;n++)await db.prepare("INSERT INTO pilot_jobs VALUES(?,?,?,?,?,?,?,?)")
    .bind(jobs[n],owner,n,"123456","default",0,1000,"waiting_for_runtime").run();
  return db;
}
function acknowledgement(url,options){
  assert.equal(url,"https://circleci.com/api/v3/runs");
  assert.equal(options.method,"POST");assert.equal(options.redirect,"error");
  const value=JSON.parse(options.body);
  assert.equal(value.data.references.pipeline.id,TRUST.definition);
  assert.equal(value.data.attributes.config.branch,TRUST.ref.slice(11));
  assert.deepEqual(value.data.attributes.checkout,value.data.attributes.config);
  const p=value.data.attributes.parameters;
  assert.equal(p.dispatch_probe,true);assert.equal(p.build_native_runtime,false);
  assert.equal(p.probe_source,source);assert.match(p.probe_id,/^[a-f0-9]{32}$/);
  assert.equal(Object.keys(p).length,4);
  return Response.json({data:{id:run}},{status:201});
}
async function row(db,job=jobs[0]){
  return db.prepare("SELECT * FROM circleci_dispatches WHERE job_id=?").bind(job).first();
}
function loseAcknowledgement(db,at){
  return {prepare(query){
    const original=db.prepare(query);
    return {bind(...args){
      const bound=original.bind(...args);
      return {first:()=>bound.first(),async run(){
        const result=await bound.run();
        if(query===at)throw Error("synthetic_committed_ack_lost");
        return result;
      }};
    }};
  }};
}
test("concurrent dispatch claims produce exactly one POST",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);let calls=0;
    const send=async(...args)=>{calls++;return acknowledgement(...args);};
    const results=await Promise.all([dispatchSynthetic(db,config,send),
      dispatchSynthetic(db,{...config,job:jobs[1]},send),dispatchSynthetic(db,config,send)]);
    assert.equal(calls,1);assert.equal(results.filter(x=>x.state==="submitted").length,1);
    assert.equal((await db.prepare("SELECT count(*) n FROM circleci_dispatches").first()).n,1);
  }finally{await mf.dispose();}
});
test("uncertain network outcome survives restart and never expires into retry",{timeout:60000},async()=>{
  const folder=await mkdtemp(join(tmpdir(),"circle-dispatch-"));let mf=make(folder);
  try{
    let db=await setup(mf),calls=0;
    const send=async()=>{calls++;throw Error("synthetic_timeout_after_remote_accept");};
    assert.equal((await dispatchSynthetic(db,config,send)).state,"unknown");
    assert.equal((await row(db)).state,"unknown");
    await mf.dispose();mf=make(folder);db=await mf.getD1Database("DB");
    assert.equal((await dispatchSynthetic(db,{...config,now:31537000},send)).state,"blocked");
    assert.equal((await dispatchSynthetic(db,{...config,job:jobs[1],now:31537000},send)).state,"blocked");
    assert.equal(calls,1);
  }finally{await mf.dispose();await rm(folder,{recursive:true,force:true});}
});
test("lost intent acknowledgement sends nothing and preserves the blocking intent",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);let calls=0;const send=async()=>{calls++;return acknowledgement();};
    const result=await dispatchSynthetic(loseAcknowledgement(db,DISPATCH_SQL.claim),config,send);
    assert.equal(result.state,"storage_unavailable");assert.equal(calls,0);
    assert.equal((await row(db)).state,"intent");
    assert.equal((await dispatchSynthetic(db,config,send)).state,"blocked");assert.equal(calls,0);
  }finally{await mf.dispose();}
});
test("lost dispatch acknowledgement cannot submit again",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);let calls=0;
    const send=async(...args)=>{calls++;return acknowledgement(...args);};
    assert.equal((await dispatchSynthetic(loseAcknowledgement(db,DISPATCH_SQL.submitted),config,send)).state,"unknown");
    assert.equal((await dispatchSynthetic(db,config,send)).state,"blocked");
    assert.equal(calls,1);assert.equal((await row(db)).run_id,run);
  }finally{await mf.dispose();}
});
test("wrong owner, cancelled job, delivered link and disabled config dispatch nothing",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);let calls=0;const send=async()=>{calls++;throw Error("forbidden");};
    assert.equal((await dispatchSynthetic(db,{...config,owner:"54321"},send)).state,"blocked");
    await db.prepare("UPDATE pilot_jobs SET state='cancelled' WHERE job_id=?").bind(jobs[0]).run();
    assert.equal((await dispatchSynthetic(db,config,send)).state,"blocked");
    await db.prepare("INSERT INTO pilot_links VALUES(?,?,?,?,?,?,?)")
      .bind(jobs[1],owner,"syntheticFile12345","fixture.txt",1,"a".repeat(64),2000).run();
    assert.equal((await dispatchSynthetic(db,{...config,job:jobs[1]},send)).state,"blocked");
    assert.equal((await dispatchSynthetic(db,{...config,enabled:"1"},send)).state,"disabled");
    assert.equal(calls,0);
  }finally{await mf.dispose();}
});
test("wrong readback never releases capacity; verified success permits the next job",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);assert.equal((await dispatchSynthetic(db,config,acknowledgement)).state,"submitted");
    const value={data:{id:run,attributes:{phase:"ended",current_outcome:"succeeded"},
      references:{project:{id:TRUST.project},pipeline:{id:TRUST.definition},event:{attributes:{vcs:{
        origin_repository_url:"https://"+TRUST.source,target_repository_url:"https://"+TRUST.source,
        branch:TRUST.ref.slice(11),revision:"b".repeat(40)}}}}}};
    const send=async(url,options)=>{
      assert.equal(url,"https://circleci.com/api/v3/runs/"+run);
      assert.equal(options.method,"GET");return Response.json(value);
    };
    await assert.rejects(finishSynthetic(db,{...config,now:1010},send),/identity/);
    assert.equal((await row(db)).state,"submitted");
    value.data.references.event.attributes.vcs.revision=source;
    assert.equal((await finishSynthetic(db,{...config,now:1010},send)).state,"finished");
    const next=async(url,options)=>Response.json({data:{id:"23456789-1234-1234-1234-123456789abc"}},{status:201});
    assert.equal((await dispatchSynthetic(db,{...config,job:jobs[1],now:1020},next)).state,"submitted");
    assert.equal((await dispatchSynthetic(db,{...config,now:1030},next)).state,"blocked");
  }finally{await mf.dispose();}
});
test("malformed or rejected trigger outcome remains blocked without automatic POST retry",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);let calls=0;
    const send=async()=>{calls++;return Response.json({data:{id:"invalid"}},{status:201});};
    assert.equal((await dispatchSynthetic(db,config,send)).state,"unknown");
    assert.equal((await dispatchSynthetic(db,config,send)).state,"blocked");assert.equal(calls,1);
    await assert.rejects(db.prepare("UPDATE circleci_dispatches SET state='retry'").run());
  }finally{await mf.dispose();}
});

test("trigger timeout records unknown and does not dispatch a second request",{timeout:60000},async()=>{
  const mf=make();try{
    const db=await setup(mf);let calls=0;
    const send=async(url,options)=>{
      calls++;
      assert.ok(options.signal instanceof AbortSignal);
      return new Promise((resolve,reject)=>options.signal.addEventListener("abort",
        ()=>reject(options.signal.reason),{once:true}));
    };
    assert.equal((await dispatchSynthetic(db,config,send)).state,"unknown");
    assert.equal((await row(db)).state,"unknown");
    assert.equal((await dispatchSynthetic(db,config,send)).state,"blocked");
    assert.equal(calls,1);
  }finally{await mf.dispose();}
});
