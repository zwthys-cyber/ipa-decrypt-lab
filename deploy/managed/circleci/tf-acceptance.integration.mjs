// CI only: actual workerd/D1, synthetic historical rows; no invitation POST.
import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {mkdtemp,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {Miniflare} from "miniflare";
import {SCHEMA,inviteHash,normalizeSource,stageHandoff,sealHandoff,claimPermit,finishPermit} from "./tf-acceptance.mjs";
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

test("actual legacy historical row is converted to a confirmed tombstone without a live nonce",async()=>{
  const old={invite:"yoNuHexZ",request_id:"historical",run_id:"42692803345",
    source_commit:"688b5356aa33a9653517f62445856a08c72819c4",nonce:"",created:0,state:"membership_verified"};
  const converted=await normalizeSource([old],owner,pepper,100);
  const repeat=await normalizeSource([old],owner,pepper,100);
  assert.deepEqual(converted,repeat);assert.equal(old.nonce,"");
  assert.equal(converted.rows[0].state,"confirmed");assert.equal(converted.rows[0].run_id,old.run_id);
  const s=await setup();try{
    const bound={...evidence,snapshot_sha256:converted.source_sha256};
    await stageHandoff(s.db,owner,bound,converted.rows);await sealHandoff(s.db,owner,bound,101);
    assert.equal((await claimPermit(s.db,owner,converted.rows[0].invite_hash,request,999999)).permitted,false);
  }finally{await s.close();}
});
test("legacy unknown intents retain their exact request, nonce and source",async()=>{
  const old={invite:"SYNTH123",request_id:request.request_id,run_id:"123456",
    source_commit:"e".repeat(40),nonce:"a".repeat(32),created:10,state:"outcome_unknown"};
  const pinned={invite:"yoNuHexZ",request_id:"historical",run_id:"42692803345",
    source_commit:"688b5356aa33a9653517f62445856a08c72819c4",nonce:"",created:0,state:"membership_verified"};
  await assert.rejects(normalizeSource([old],owner,pepper,100),/history_missing/);
  const converted=await normalizeSource([old,pinned],owner,pepper,100),row=converted.rows.find(r=>r.request_id===old.request_id);
  assert.equal(row.state,"unknown");assert.equal(row.request_id,old.request_id);
  assert.equal(row.nonce,old.nonce);assert.equal(row.source_sha,old.source_commit);
});
test("historical format cannot bless a different invitation or unproven outcome",async()=>{
  const old={invite:"yoNuHexZ",request_id:"historical",run_id:"42692803345",
    source_commit:"688b5356aa33a9653517f62445856a08c72819c4",nonce:"",created:0,state:"membership_verified"};
  for(const changed of [{invite:"SYNTH123"},{state:"intent"},{run_id:"12345"},{nonce:"a".repeat(32)}])
    await assert.rejects(normalizeSource([{...old,...changed}],owner,pepper,100),/provenance/);
});
