import test from "node:test";
import assert from "node:assert/strict";
import {handle,SQL,target} from "./worker.mjs";
const now=1795510000;
const secret="S".repeat(48);
const owner=12345;
function fakeDb(){
  const calls=[];
  return {calls,prepare(sql){calls.push(sql);return {bind(...args){
    calls.push(args);
    return {run:async()=>({success:true,meta:{changes:1}}),all:async()=>({success:true,results:[]}),first:async()=>null};
  }};}};
}
function req(text="123456",opts={}){
  const update={update_id:111,message:{date:now,chat:{id:owner,type:"private"},from:{id:owner,is_bot:false},text}};
  return new Request("https://pilot.example.invalid/telegram",{method:"POST",headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":secret},body:JSON.stringify(update),...opts});
}
const env=db=>({PILOT_ENABLED:"1",PILOT_OWNER_ID:String(owner),TELEGRAM_WEBHOOK_SECRET:secret,DB:db});
test("strict App Store routing and no TestFlight",()=>{
  assert.deepEqual(target("123456"),{app:"123456",region:"default"});
  assert.deepEqual(target("https://apps.apple.com/cn/app/a/id123456"),{app:"123456",region:"cn"});
  for(const bad of ["https://testflight.apple.com/join/ABC123","https://apps.apple.com.evil.invalid/id123456","https://u@apps.apple.com/id123456","https://apps.apple.com/id123456#x","http://apps.apple.com/id123456"])assert.equal(target(bad),null);
});
test("disabled, invalid secret and other users never touch D1",async()=>{
  const db=fakeDb();
  assert.equal((await handle(req(),{...env(db),PILOT_ENABLED:"0"},now)).status,503);
  assert.equal((await handle(req("123456",{headers:{"content-type":"application/json"}}),env(db),now)).status,401);
  const update={update_id:1,message:{date:now,chat:{id:88,type:"private"},from:{id:88,is_bot:false},text:"123456"}};
  assert.equal((await handle(req("123456",{body:JSON.stringify(update)}),env(db),now)).status,200);
  assert.equal(db.calls.length,0);
});
test("owner registration is explicitly waiting; no dispatch",async()=>{
  const db=fakeDb();
  const res=await handle(req("https://apps.apple.com/cn/app/a/id123456"),env(db),now);
  assert.equal(res.status,200);
  const reply=await res.json();
  assert.equal(reply.method,"sendMessage");
  assert.match(reply.text,/尚未开始/);
  assert.equal(db.calls[0],SQL.insert);
  assert.match(db.calls[1][0],/^pilot_[a-f0-9]{32}$/);
  assert.equal(db.calls[1][4],"cn");
});
test("duplicate, quota and database failure do not dispatch",async()=>{
  const db={prepare(sql){return {bind(){return {run:async()=>({success:true,meta:{changes:0}}),first:async()=>sql===SQL.existing?{job_id:"pilot_"+"a".repeat(32)}:null};}};}};
  assert.deepEqual(await (await handle(req(),env(db),now)).json(),{ok:true});
  const quota={prepare(){return {bind(){return {run:async()=>({success:true,meta:{changes:0}}),first:async()=>null};}};}};
  assert.match((await (await handle(req(),env(quota),now)).json()).text,/上限/);
  const fail={prepare(){throw Error("private upstream details");}};
  const result=await handle(req(),env(fail),now);
  assert.equal(result.status,503);assert.deepEqual(await result.json(),{ok:false});
});
test("cancel and status are scoped",async()=>{
  const db=fakeDb();
  const id="pilot_"+"a".repeat(32);
  assert.match((await (await handle(req("/cancel "+id),env(db),now)).json()).text,/已取消/);
  assert.deepEqual(db.calls.slice(0,2),[SQL.cancel,[String(owner),id]]);
  assert.match((await (await handle(req("/status"),env(db),now)).json()).text,/暂无/);
  assert.deepEqual(db.calls.slice(2),[SQL.recent,[String(owner)]]);
});
