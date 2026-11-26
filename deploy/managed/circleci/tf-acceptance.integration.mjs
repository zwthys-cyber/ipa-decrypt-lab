// CI only: actual workerd/D1, synthetic historical rows; no invitation POST.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {mkdtemp,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {Miniflare} from "miniflare";
import {SCHEMA,inviteHash,stageHandoff,sealHandoff,claimPermit,finishPermit} from "./tf-acceptance.mjs";
globalThis.crypto??=webcrypto;
const owner="12345",hash="a".repeat(64),other="b".repeat(64),pepper=new Uint8Array(32).fill(7);
const evidence={snapshot_sha256:"c".repeat(64),session_sha256:"d".repeat(64),source_sha:"e".repeat(40)};
const request={invite:"SYNTH123",request_id:"tf_"+"a".repeat(32),run_id:"12345678-1234-1234-1234-123456789abc",
  source_commit:"f".repeat(40)};
const history={invite_hash:hash,state:"confirmed",request_id:"tf_"+"d".repeat(32),run_id:"123456",
  source_sha:"b".repeat(40),nonce:"e".repeat(32),created_at:10,updated_at:20};
async function setup(folder){
  const mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled',{status:503})}}",
    compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,
    d1Databases:{DB:"77777777-7777-4777-8777-777777777777"},...(folder?{d1Persist:folder}:{})});
  const db=await mf.getD1Database("DB");
  const statements=SCHEMA.split(";").map(s=>s.trim()).filter(Boolean);
  await db.batch(statements.map(s=>db.prepare(s)));
  return {db,close:()=>mf.dispose()};
}
test("no permit until state handoff is explicitly sealed; one durable intent at a time",async()=>{
  const s=await setup();try{
    assert.equal((await claimPermit(s.db,owner,hash,request,100)).permitted,false);
    await stageHandoff(s.db,owner,evidence,[]);
    assert.equal((await claimPermit(s.db,owner,hash,request,100)).permitted,false);
    await sealHandoff(s.db,owner,evidence,100);
    const permit=await claimPermit(s.db,owner,hash,request,101);
    assert.equal(permit.permitted,true);assert.equal(permit.expires,401);
    assert.equal((await claimPermit(s.db,owner,hash,request,102)).permitted,false);
    assert.equal((await claimPermit(s.db,owner,other,{...request,request_id:"tf_"+"b".repeat(32)},102)).permitted,false);
    await finishPermit(s.db,owner,hash,request,permit.nonce,"membership_verified",103);
    assert.equal((await claimPermit(s.db,owner,hash,request,999999)).permitted,false);
    assert.equal((await claimPermit(s.db,owner,other,{...request,request_id:"tf_"+"b".repeat(32)},104)).permitted,true);
  }finally{await s.close();}
});
test("historical confirmed invitation can never acquire a new acceptance permit",async()=>{
  const s=await setup();try{
    await stageHandoff(s.db,owner,evidence,[history]);
    assert.deepEqual(await stageHandoff(s.db,owner,evidence,[history]),{staged:true,rows:1});
    await sealHandoff(s.db,owner,evidence,100);
    assert.equal((await claimPermit(s.db,owner,hash,request,101)).permitted,false);
    const saved=await s.db.prepare("SELECT * FROM circleci_tf_acceptances").first();
    for(const [k,v] of Object.entries(history))assert.equal(saved[k],v);
  }finally{await s.close();}
});
test("unknown acceptance survives restart and permit expiry without rearming",async()=>{
  const folder=await mkdtemp(join(tmpdir(),"tf-durable-"));let s=await setup(folder);
  try{
    await stageHandoff(s.db,owner,evidence,[]);await sealHandoff(s.db,owner,evidence,100);
    const permit=await claimPermit(s.db,owner,hash,request,101);
    await finishPermit(s.db,owner,hash,request,permit.nonce,"outcome_unknown",102);
    await s.close();s=await setup(folder);
    assert.equal((await claimPermit(s.db,owner,hash,request,99999999)).permitted,false);
    assert.equal((await claimPermit(s.db,owner,other,{...request,request_id:"tf_"+"b".repeat(32)},99999999)).permitted,false);
    assert.equal((await s.db.prepare("SELECT state FROM circleci_tf_acceptances").first()).state,"unknown");
    await assert.rejects(finishPermit(s.db,owner,hash,request,permit.nonce,"membership_verified",99999999),/immutable/);
  }finally{await s.close();await rm(folder,{recursive:true,force:true});}
});
test("imported unknown truth blocks acceptance rather than expiring historical intent",async()=>{
  const s=await setup();try{
    await stageHandoff(s.db,owner,evidence,[{...history,state:"unknown"}]);
    await sealHandoff(s.db,owner,evidence,100);
    assert.equal((await claimPermit(s.db,owner,other,request,99999999)).permitted,false);
  }finally{await s.close();}
});
test("conflicting history and handoff cannot replace original records",async()=>{
  const s=await setup();try{
    await stageHandoff(s.db,owner,evidence,[history]);
    await assert.rejects(stageHandoff(s.db,owner,evidence,[{...history,state:"unknown"}]),/conflict/);
    await assert.rejects(stageHandoff(s.db,owner,{...evidence,session_sha256:"f".repeat(64)},[history]),/immutable/);
    await assert.rejects(sealHandoff(s.db,owner,{...evidence,snapshot_sha256:"f".repeat(64)},100),/seal/);
    assert.equal((await s.db.prepare("SELECT state FROM circleci_tf_acceptances").first()).state,"confirmed");
  }finally{await s.close();}
});
test("a wrong owner, run, source or nonce cannot complete another permit",async()=>{
  const s=await setup();try{
    await stageHandoff(s.db,owner,evidence,[]);await sealHandoff(s.db,owner,evidence,100);
    const permit=await claimPermit(s.db,owner,hash,request,101);
    for(const [who,bound,nonce] of [["54321",request,permit.nonce],[owner,{...request,run_id:"23456789-1234-1234-1234-123456789abc"},permit.nonce],
      [owner,{...request,source_commit:"a".repeat(40)},permit.nonce],[owner,request,"a".repeat(32)]]){
      await assert.rejects(finishPermit(s.db,who,hash,bound,nonce,"membership_verified",102),/immutable/);
    }
    assert.equal((await s.db.prepare("SELECT state FROM circleci_tf_acceptances").first()).state,"intent");
  }finally{await s.close();}
});
test("invite lookup is owner scoped and peppered; raw invitations are not storage keys",async()=>{
  const first=await inviteHash("SYNTH123",owner,pepper);
  assert.match(first,/^[a-f0-9]{64}$/);
  assert.notEqual(first,await inviteHash("SYNTH123","54321",pepper));
  assert.notEqual(first,await inviteHash("SYNTH123",owner,new Uint8Array(32).fill(8)));
});
