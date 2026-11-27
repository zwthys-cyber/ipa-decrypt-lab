// CI only: real workerd/D1 with synthetic age-shaped opaque bytes; real age is tested separately.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {Miniflare} from "miniflare";
import {LEASE_SCHEMA,requestLease,pendingLease,publishLease,readLease,closeLease} from "./credential-broker.mjs";
globalThis.crypto??=webcrypto;
const now=1000;
const task={job_id:"pilot_"+"a".repeat(32),kind:"synthetic_noop",dispatch_state:"submitted",
  run_id:"12345678-1234-1234-1234-123456789abc",worker_job_id:"23456789-1234-1234-1234-123456789abc",
  source_sha:"b".repeat(40),finished_at:null};
const request={recipient:"age1"+"q".repeat(58),nonce:"c".repeat(32),expires_at:now+240};
const cipher=Buffer.from("age-encryption.org/v1\nsynthetic-opaque-ciphertext").toString("base64");
async function setup(){
  const mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled',{status:503})}}",
    compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"66666666-6666-4666-8666-666666666666"}});
  const db=await mf.getD1Database("DB");
  await db.prepare("CREATE TABLE circleci_claims(job_id TEXT PRIMARY KEY)").run();
  await db.prepare("INSERT INTO circleci_claims VALUES(?)").bind(task.job_id).run();
  await db.prepare(LEASE_SCHEMA).run();
  return {db,close:()=>mf.dispose()};
}
test("opaque lease is bound, immutable, idempotent and erased on terminal completion",async()=>{
  const s=await setup();try{
    assert.deepEqual(await pendingLease(s.db,task,now),{ok:true,pending:true});
    const {context}=await requestLease(s.db,task,request,now);
    assert.equal(context.profile,"synthetic");
    assert.deepEqual(await requestLease(s.db,task,request,now),{ok:true,context});
    const published=await publishLease(s.db,task,{context,ciphertext:cipher},now);
    assert.deepEqual(await publishLease(s.db,task,{context,ciphertext:cipher},now),published);
    assert.equal((await readLease(s.db,task,now)).ciphertext,cipher);
    await closeLease(s.db,task.job_id,now+1);
    const record=await s.db.prepare("SELECT * FROM circleci_credential_leases").first();
    assert.equal(record.ciphertext,null);assert.equal(record.consumed_at,now+1);
    assert.equal(record.cipher_sha256,published.cipher_sha256);
    await assert.rejects(readLease(s.db,task,now+2),/expired/);
    await assert.rejects(requestLease(s.db,task,request,now+2),/immutable/);
  }finally{await s.close();}
});
test("recipient and nonce cannot rotate after committing a lease request",async()=>{
  const s=await setup();try{
    await requestLease(s.db,task,request,now);
    for(const key of ["recipient","nonce"]){
      const value=key==="recipient"?"age1"+"p".repeat(58):"d".repeat(32);
      await assert.rejects(requestLease(s.db,task,{...request,[key]:value},now),/immutable/);
    }
  }finally{await s.close();}
});
test("publisher cannot change source, run, worker, profile or recipient",async()=>{
  const s=await setup();try{
    const {context}=await requestLease(s.db,task,request,now);
    for(const key of ["job_id","source_sha","run_id","worker_job_id","recipient","profile","nonce","expires_at"]){
      await assert.rejects(publishLease(s.db,task,{context:{...context,[key]:"other"},ciphertext:cipher},now),/binding/);
    }
    await assert.rejects(publishLease(s.db,task,{context,ciphertext:Buffer.from("plaintext").toString("base64")},now),/format/);
  }finally{await s.close();}
});
test("a published ciphertext cannot be overwritten or silently replaced",async()=>{
  const s=await setup();try{
    const {context}=await requestLease(s.db,task,request,now);
    await publishLease(s.db,task,{context,ciphertext:cipher},now);
    const changed=Buffer.from("age-encryption.org/v1\nother-ciphertext").toString("base64");
    await assert.rejects(publishLease(s.db,task,{context,ciphertext:changed},now),/immutable/);
    assert.equal((await readLease(s.db,task,now)).ciphertext,cipher);
  }finally{await s.close();}
});
test("expired material is refused and ciphertext erased without rearming the request",async()=>{
  const s=await setup();try{
    const {context}=await requestLease(s.db,task,request,now);
    await publishLease(s.db,task,{context,ciphertext:cipher},now);
    await assert.rejects(readLease(s.db,task,request.expires_at),/expired/);
    const record=await s.db.prepare("SELECT * FROM circleci_credential_leases").first();
    assert.equal(record.ciphertext,null);assert.equal(record.context_json,JSON.stringify(context));
    await assert.rejects(requestLease(s.db,task,{...request,expires_at:now+500},now+250),/immutable/);
  }finally{await s.close();}
});
test("unclaimed, finished and real Apple tasks cannot request leases",async()=>{
  const s=await setup();try{
    for(const changes of [{kind:"default"},{kind:"cn"},{kind:"tf"},{worker_job_id:null},{finished_at:now},{dispatch_state:"unknown"}])
      await assert.rejects(requestLease(s.db,{...task,...changes},request,now),/closed/);
    await assert.rejects(requestLease(s.db,task,{...request,expires_at:now+301},now),/invalid/);
  }finally{await s.close();}
});
