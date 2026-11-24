import test from "node:test";
import assert from "node:assert/strict";
import {handle} from "./worker.mjs";
import {verifyDrive,metadata,LINK_SQL,WINDOW,MAX} from "./private-link.mjs";
const now=1795510000, owner=12345, token="T".repeat(48),issuer="I".repeat(48);
const id="pilot_"+"a".repeat(32),record={file_id:"syntheticFileID123",filename:"Example.zip",bytes:10000000000,sha256:"a".repeat(64)};
const env={PILOT_ENABLED:"1",PILOT_OWNER_ID:String(owner),TELEGRAM_WEBHOOK_SECRET:token,PILOT_LINK_ENABLED:"1",PILOT_LINK_ISSUER_TOKEN:issuer,
  PILOT_DRIVE_ACCESS_TOKEN:"synthetic-access-token-1234567890",PILOT_DRIVE_RECIPIENT_EMAIL:"reader@example.invalid"};
const file={id:record.file_id,name:record.filename,size:String(record.bytes),sha256Checksum:record.sha256,trashed:false,ownedByMe:true,mimeType:"application/zip"};
const permissions=[{type:"user",role:"owner",emailAddress:"owner@example.invalid"},{type:"user",role:"reader",emailAddress:"reader@example.invalid"}];
function mockDrive(f=file,p=permissions){
  const calls=[];
  const send=async(url,init)=>{
    calls.push(url);
    assert.equal(new URL(url).origin,"https://www.googleapis.com");
    assert.equal(init.method,"GET");assert.equal(init.redirect,"manual");assert.ok(init.signal instanceof AbortSignal);
    const result=url.includes("/permissions?")?{permissions:p}:f;
    return Response.json(result);
  };
  return {calls,send};
}
function db(row={...record,expires_at:now+WINDOW}){
  const calls=[];
  return {calls,prepare(sql){calls.push(sql);return {bind(...args){calls.push(args);return {
    run:async()=>({success:true,meta:{changes:1}}),first:async()=>row
  };}};}};
}
function register(auth=issuer,value={...record,job_id:id}){
  return new Request("https://pilot.example.invalid/v1/link-register",{method:"POST",
    headers:{"content-type":"application/json",authorization:"Bearer "+auth},body:JSON.stringify(value)});
}
function get(uid=owner){
  return new Request("https://pilot.example.invalid/telegram",{method:"POST",
    headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":token},
    body:JSON.stringify({update_id:1,message:{date:now,chat:{id:uid,type:"private"},from:{id:uid,is_bot:false},text:"/get "+id}})});
}
test("reject public, mismatched and oversized files",async()=>{
  const valid=mockDrive();assert.equal(await verifyDrive(record,env,valid.send),"https://drive.google.com/file/d/"+record.file_id+"/view");
  for(const f of [{...file,sha256Checksum:"b".repeat(64)},{...file,trashed:true},{...file,ownedByMe:false}]){
    await assert.rejects(verifyDrive(record,env,mockDrive(f).send));
  }
  for(const p of [[...permissions,{type:"anyone",role:"reader"}],[permissions[0],{type:"user",role:"writer",emailAddress:env.PILOT_DRIVE_RECIPIENT_EMAIL}],[permissions[0]]]){
    await assert.rejects(verifyDrive(record,env,mockDrive(file,p).send));
  }
  const none=mockDrive();await assert.rejects(verifyDrive({...record,bytes:10000000001},env,none.send));assert.equal(none.calls.length,0);
});
test("issuer auth, exact owner binding, no arbitrary URL",async()=>{
  const d=db(),m=mockDrive();
  assert.equal((await handle(register(token),{...env,DB:d},now,m.send)).status,401);
  assert.equal((await handle(register(issuer,{...record,job_id:id,url:"https://example.invalid"}),{...env,DB:d},now,m.send)).status,409);
  assert.equal(m.calls.length,0);
  assert.equal((await handle(register(),{...env,DB:d},now,m.send)).status,201);
  assert.deepEqual(d.calls,[LINK_SQL.register,[record.file_id,record.filename,record.bytes,record.sha256,now+WINDOW,id,String(owner)]]);
  assert.equal(m.calls.length,2);
});
test("private owner gets link after repeat ACL verification; no expiry claim",async()=>{
  const d=db(),m=mockDrive();
  assert.deepEqual(await (await handle(get(999),{...env,DB:d},now,m.send)).json(),{ok:true});
  assert.equal(d.calls.length,0);
  const response=await handle(get(),{...env,DB:d},now,m.send);
  const reply=await response.json();
  assert.equal(reply.chat_id,owner);assert.equal(reply.reply_markup.inline_keyboard[0][0].url,"https://drive.google.com/file/d/"+record.file_id+"/view");
  assert.match(reply.text,/领取期限不等于网盘权限到期/);
  assert.deepEqual(d.calls,[LINK_SQL.lookup,[id,String(owner),now]]);
  assert.equal(m.calls.length,2);
});
test("disabled, expired, cancelled or revoked link is never returned",async()=>{
  const m=mockDrive(),d=db(null);
  assert.match((await (await handle(get(),{...env,DB:d,PILOT_LINK_ENABLED:"0"},now,m.send)).json()).text,/尚未配置/);
  assert.match((await (await handle(get(),{...env,DB:d},now,m.send)).json()).text,/暂无有效链接/);
  assert.equal(m.calls.length,0);
  const revoked=mockDrive(file,[permissions[0]]);
  assert.equal((await handle(get(),{...env,DB:db()},now,revoked.send)).status,503);
});

test("large metadata stays exact above 32-bit and rejects oversize or fractional bytes",()=>{
  assert.equal(MAX,10000000000);
  for(const bytes of [2000000001,4294967297,9999999999,MAX])
    assert.equal(metadata({...record,bytes}).bytes,bytes);
  for(const bytes of [0,-1,MAX+1,1.5,"10000000000",Number.MAX_SAFE_INTEGER])
    assert.throws(()=>metadata({...record,bytes}));
});

test("retirement is authenticated, exact and does not call Drive",async()=>{
  const d=db(),m=mockDrive();
  const req=(auth)=>new Request("https://pilot.example.invalid/v1/link-retire",{method:"POST",
    headers:{"content-type":"application/json",authorization:"Bearer "+auth},body:JSON.stringify({...record,job_id:id})});
  assert.equal((await handle(req(token),{...env,DB:d},now,m.send)).status,401);
  assert.equal((await handle(req(issuer),{...env,DB:d},now,m.send)).status,200);
  assert.deepEqual(d.calls,[LINK_SQL.retire,[now,id,String(owner),record.file_id,record.filename,record.bytes,record.sha256,now-86400]]);
  assert.equal(m.calls.length,0);
});
