import test from "node:test";
import assert from "node:assert/strict";
import {Miniflare} from "miniflare";
import {UPLOAD_SCHEMA,readUploadJournal,writeUploadJournal,confirmUploadRegistration} from "./runtime-upload.mjs";
const task={job_id:"pilot_"+"a".repeat(32),owner_id:"12345",
  worker_job_id:"12345678-1234-1234-1234-123456789abc",source_sha:"b".repeat(40),kind:"export",state:"running",
  plaintext_sha256:"c".repeat(64),plaintext_bytes:8192,filename:"Synthetic_Beta_1.0.ipa",
  recipient_email:"fixture@example.invalid",control_origin:"https://ipazake-free-control-pilot.fixture.workers.dev"};
const initial={job_id:task.job_id,record:{filename:task.filename,bytes:8192,sha256:task.plaintext_sha256},
  owner:task.recipient_email,stage:"start_intent"};
const session="https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=SYNTHETIC_12345678";
async function setup(){
  const mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled')}}",
    compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"88888888-8888-4888-8888-888888888888"}});
  const db=await mf.getD1Database("DB");await db.prepare(UPLOAD_SCHEMA).run();
  return {db,close:()=>mf.dispose()};
}
test("intent precedes upload and lost acknowledgement replays only the same journal write",async()=>{
  const s=await setup();try{
    assert.equal(await readUploadJournal(s.db,task),null);
    for(let i=0;i<3;i++)assert.deepEqual(await writeUploadJournal(s.db,task,initial,100+i),{ok:true,revision:1});
    assert.deepEqual(await readUploadJournal(s.db,task),initial);
    assert.deepEqual(await writeUploadJournal(s.db,task,{...initial,stage:"uploading",session},103),{ok:true,revision:2});
    assert.equal((await readUploadJournal(s.db,task)).session,session);
  }finally{await s.close();}
});
test("unknown creation intent cannot be reset or jump to an uploaded file",async()=>{
  const s=await setup();try{
    await assert.rejects(writeUploadJournal(s.db,task,{...initial,stage:"uploading",session},100),/intent_required/);
    await writeUploadJournal(s.db,task,initial,100);
    await assert.rejects(writeUploadJournal(s.db,task,{...initial,stage:"uploaded",file_id:"SYNTHETIC_123"},999999),/transition/);
    assert.equal((await readUploadJournal(s.db,task)).stage,"start_intent");
  }finally{await s.close();}
});
test("plaintext hash, size, filename and owner are immutable",async()=>{
  const s=await setup();try{
    await writeUploadJournal(s.db,task,initial,100);
    for(const change of [{record:{...initial.record,sha256:"d".repeat(64)}},
      {record:{...initial.record,bytes:8193}},{record:{...initial.record,filename:"Other.ipa"}},
      {owner:"other@example.invalid"}]){
      await assert.rejects(writeUploadJournal(s.db,task,{...initial,...change},101));
    }
    assert.deepEqual(await readUploadJournal(s.db,task),initial);
  }finally{await s.close();}
});
test("other owners, workers and source revisions cannot read or mutate this upload",async()=>{
  const s=await setup();try{
    await writeUploadJournal(s.db,task,initial,100);
    for(const change of [{owner_id:"54321"},{worker_job_id:"23456789-1234-1234-1234-123456789abc"},{source_sha:"d".repeat(40)}]){
      await assert.rejects(readUploadJournal(s.db,{...task,...change}),/owner/);
      await assert.rejects(writeUploadJournal(s.db,{...task,...change},initial,101),/owner/);
    }
  }finally{await s.close();}
});
test("redirects and arbitrary upload sessions are refused",async()=>{
  const s=await setup();try{
    await writeUploadJournal(s.db,task,initial,100);
    for(const url of [session.replace("www.googleapis.com","evil.invalid"),session.replace("https:","http:"),
      session+"&redirect=https://evil.invalid",session+"&upload_id=OTHER_123456"]){
      await assert.rejects(writeUploadJournal(s.db,task,{...initial,stage:"uploading",session:url},101));
    }
  }finally{await s.close();}
});
test("only independently verified server registration can commit completion",async()=>{
  const s=await setup();try{
    await writeUploadJournal(s.db,task,initial,100);
    await writeUploadJournal(s.db,task,{...initial,stage:"uploading",session},101);
    const uploaded={...initial,stage:"uploaded",file_id:"SYNTHETIC_123456"};
    await writeUploadJournal(s.db,task,uploaded,102);
    const registering={...uploaded,stage:"registration_intent",registration_origin:task.control_origin};
    await writeUploadJournal(s.db,task,registering,103);
    await assert.rejects(writeUploadJournal(s.db,task,{...registering,stage:"registered"},104),/transition/);
    await assert.rejects(confirmUploadRegistration(s.db,task,"OTHER_FILE_123",104),/binding/);
    await confirmUploadRegistration(s.db,task,uploaded.file_id,104);
    assert.equal((await readUploadJournal(s.db,task)).stage,"registered");
    assert.equal((await writeUploadJournal(s.db,task,{...registering,stage:"registered"},105)).revision,5);
  }finally{await s.close();}
});
test("cancellation closes further journal access without deleting preserved intent",async()=>{
  const s=await setup();try{
    await writeUploadJournal(s.db,task,initial,100);
    await assert.rejects(readUploadJournal(s.db,{...task,state:"cancelled"}),/context/);
    assert.equal((await s.db.prepare("SELECT stage FROM runtime_uploads").first()).stage,"start_intent");
  }finally{await s.close();}
});
