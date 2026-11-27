import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {Miniflare} from "miniflare";
import {schemaStatements} from "./runtime-api.mjs";
import {stageRecovery,sealRecovery,recoveryStatus,offlineEntry,refreshRecoveryFence,quarantineUpdate,sha,SNAPSHOT} from "./runtime-recovery.mjs";
import {requireEntry} from "./runtime-tasks.mjs";
import {inviteHash,claimPermit} from "./tf-acceptance.mjs";
import {handleManagedTelegram} from "./runtime-telegram.mjs";
globalThis.crypto??=webcrypto;
const owner="12345",source="a".repeat(40),now=Math.floor(Date.now()/1000),old="123456789:"+"O".repeat(36),fresh="123456789:"+"N".repeat(36);
const names={407064604:"private-delivery.yml",411713917:"china-private-delivery.yml",412609354:"testflight-private-delivery.yml",407542960:"version-catalog.yml",412705779:"china-version-catalog.yml"};
async function setup(stamp=now){
 const mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled')}}",compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"55555555-5555-4555-8555-555555555555"}});
 const DB=await mf.getD1Database("DB");
 for(const sql of schemaStatements())await DB.prepare(sql).run();
 const env={DB,RUNTIME_OWNER_ID:owner,RUNTIME_SOURCE_SHA:source,RUNTIME_MODE:"staging",RUNTIME_EXPORT_ENABLED:"0",RUNTIME_TELEGRAM_ENABLED:"0",RUNTIME_BILLING_ENABLED:"0",
  RUNTIME_GH_TOKEN:"synthetic-github-token",RUNTIME_TF_HMAC_KEY:"c".repeat(64),TELEGRAM_BOT_TOKEN:fresh,TELEGRAM_WEBHOOK_SECRET:"S".repeat(48)};
 const controls={active:false,oldActive:false,wrongHook:false};
 const send=async(url,options)=>{
  assert.equal(options.redirect,"manual");
  if(url.endsWith("/getMe")){
   const revoked=url.includes(old)&&!controls.oldActive;
   return Response.json(revoked?{ok:false,error_code:401}:{ok:true,result:{id:123456789,is_bot:true}},{status:revoked?401:200});
  }
  if(url.endsWith("/getWebhookInfo"))return Response.json({ok:true,result:{url:controls.wrongHook?"":"https://ipazake-free-control-pilot.hahayesadd.workers.dev/telegram"}});
  if(url.endsWith("/runs?per_page=100"))return Response.json({total_count:0,workflow_runs:[]});
  const id=Number(url.split("/").at(-1));assert.ok(names[id]);
  assert.equal(options.headers.authorization,"Bearer "+env.RUNTIME_GH_TOKEN);
  return Response.json({id,path:".github/workflows/"+names[id],state:controls.active?"active":"disabled_manually"});
 };
 const scope=await sha("telegram-owner:"+owner),legacy=[];
 for(let i=0;i<29;i++){
  const state=i<7?"closed":i<27?"delivered":"pending",rid=i.toString(16).padStart(32,"0");
  const original={scope,rid,app:"123456",state,at:stamp-90,created:stamp-100};
  legacy.push({owner_id:owner,request_id:rid,profile:"default",target:"123456",state,created_at:stamp-100,source_json:JSON.stringify(original),held:Number(state==="pending")});
 }
 const records={legacy_tasks:legacy,updates:[{scope,uid:123,at:now-100,done:0}],metadata:[{scope,name:"offset",value:"999999"}],
  private_returns:[{request_id:"synthetic",state:"confirmed"}],acceptance_rows:[]};
 const raw=JSON.stringify(records);
 const packet={schema:"circleci-offline-stage-v1",source_run:45866115288,snapshot_sha256:SNAPSHOT,records_json:raw,
  records_sha256:await sha(raw),captured_at:stamp-100,old_token:old,tf_history_verified:true};
 return {env,packet,controls,send,close:()=>mf.dispose()};
}
test("offline stage retains every record, holds pending and blocks entry until a real scheduled check",{timeout:60000},async()=>{
 const s=await setup();try{
  await stageRecovery(s.env,s.packet,now,s.send);await stageRecovery(s.env,s.packet,now,s.send);
  let status=await recoveryStatus(s.env);assert.equal(status.legacy_rows,29);assert.equal(status.held_rows,2);
  assert.equal(status.update_rows,1);assert.equal(status.metadata_rows,1);assert.equal(status.source_disabled_verified,false);
  await assert.rejects(offlineEntry(s.env,now),/handoff_required/);
  await sealRecovery(s.env,{records_sha256:s.packet.records_sha256,old_token:old},now,s.send);
  await sealRecovery(s.env,{records_sha256:s.packet.records_sha256,old_token:old},now+1,s.send);
  s.env.RUNTIME_MODE="production";s.env.RUNTIME_EXPORT_ENABLED="1";s.env.RUNTIME_TELEGRAM_ENABLED="1";
  await assert.rejects(requireEntry(s.env),/handoff_required/);
  await refreshRecoveryFence(s.env,now+20,s.send);
  const entry=await offlineEntry(s.env,now+20);
  assert.equal(entry.telegram_update_floor,0);assert.equal(entry.offline,true);assert.equal(entry.held_rows,2);
  assert.notEqual(entry.telegram_update_floor,999999);assert.equal(entry.activated_at,now+15);
  status=await recoveryStatus(s.env);assert.equal(status.tf_sealed,true);assert.equal(status.fence_live,true);
  const rows=await s.env.DB.prepare("SELECT state,created_at,run_id FROM circleci_tf_acceptances").all();
  assert.equal(rows.results.length,1);assert.equal(rows.results[0].state,"confirmed");assert.equal(rows.results[0].created_at,0);assert.equal(rows.results[0].run_id,"42692803345");
  const pepper=Uint8Array.from("c".repeat(64).match(/../g),x=>parseInt(x,16));
  const hash=await inviteHash("yoNuHexZ",owner,pepper);
  const permit=await claimPermit(s.env.DB,owner,hash,{invite:"yoNuHexZ",request_id:"tf_"+"d".repeat(32),run_id:"12345678-1234-1234-1234-123456789abc",source_commit:source},now+20);
  assert.equal(permit.permitted,false);
 }finally{await s.close();}
});
test("changed records, active old workflow or valid old token never authorize a recovery",{timeout:60000},async()=>{
 const s=await setup();try{
  for(const flag of ["active","oldActive"]){
   s.controls[flag]=true;await assert.rejects(stageRecovery(s.env,s.packet,now,s.send));s.controls[flag]=false;
  }
  assert.equal((await s.env.DB.prepare("SELECT count(*) n FROM runtime_legacy_tasks").first()).n,0);
  await stageRecovery(s.env,s.packet,now,s.send);
  await assert.rejects(stageRecovery(s.env,{...s.packet,records_sha256:"b".repeat(64)},now,s.send));
  await s.env.DB.prepare("UPDATE runtime_legacy_tasks SET target='tampered' WHERE request_id=?").bind("0".repeat(32)).run();
  await assert.rejects(sealRecovery(s.env,{records_sha256:s.packet.records_sha256,old_token:old},now,s.send),/rows_changed/);
 }finally{await s.close();}
});
test("lost dispatch fencing, wrong webhook, stale cron or billing flag closes the new entry",{timeout:60000},async()=>{
 const s=await setup();try{
  await stageRecovery(s.env,s.packet,now,s.send);
  await sealRecovery(s.env,{records_sha256:s.packet.records_sha256,old_token:old},now,s.send);
  s.env.RUNTIME_MODE="production";s.env.RUNTIME_EXPORT_ENABLED="1";s.env.RUNTIME_TELEGRAM_ENABLED="1";
  await refreshRecoveryFence(s.env,now+20,s.send);await offlineEntry(s.env,now+20);
  await assert.rejects(offlineEntry(s.env,now+201),/handoff_required/);
  for(const flag of ["active","wrongHook"]){
   s.controls[flag]=true;await refreshRecoveryFence(s.env,now+21,s.send);
   await assert.rejects(offlineEntry(s.env,now+21),/handoff_required/);
   s.controls[flag]=false;
  }
  await refreshRecoveryFence(s.env,now+22,s.send);
  s.env.RUNTIME_SOURCE_SHA="b".repeat(40);
  await assert.rejects(offlineEntry(s.env,now+22),/handoff_required/);
  await refreshRecoveryFence(s.env,now+23,s.send);
  await offlineEntry(s.env,now+23);
  assert.equal((await recoveryStatus(s.env)).cron_source_sha,s.env.RUNTIME_SOURCE_SHA);
  s.env.RUNTIME_BILLING_ENABLED="1";await assert.rejects(offlineEntry(s.env,now+23));
 }finally{await s.close();}
});
test("pre-cutover private updates are quarantined immutably and cannot start an export",{timeout:60000},async()=>{
 const s=await setup(now-200);try{
  await stageRecovery(s.env,s.packet,now-200,s.send);
  await sealRecovery(s.env,{records_sha256:s.packet.records_sha256,old_token:old},now-200,s.send);
  s.env.RUNTIME_MODE="production";s.env.RUNTIME_EXPORT_ENABLED="1";s.env.RUNTIME_TELEGRAM_ENABLED="1";
  await refreshRecoveryFence(s.env,now,s.send);
  let calls=0,typing=0;
  const action=async(url)=>{assert.ok(url.endsWith("/sendChatAction"));typing++;return Response.json({ok:true,result:true});};
  const update={update_id:7,message:{date:now-190,chat:{id:Number(owner),type:"private"},from:{id:Number(owner),is_bot:false},text:"123456"}};
  const request=value=>new Request("https://ipazake-free-control-pilot.hahayesadd.workers.dev/telegram",{method:"POST",
   headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":s.env.TELEGRAM_WEBHOOK_SECRET},body:JSON.stringify(value)});
  for(let i=0;i<2;i++)assert.equal((await handleManagedTelegram(request(update),s.env,async()=>{calls++;throw Error("must_not_dispatch");},now,action)).status,200);
  assert.equal(calls,0);assert.equal((await s.env.DB.prepare("SELECT count(*) n FROM runtime_recovery_quarantine").first()).n,1);
  await assert.rejects(quarantineUpdate(s.env,{...update,message:{...update.message,text:"changed"}},now),/update_conflict/);
  const reply=await handleManagedTelegram(request({...update,update_id:8,message:{...update.message,date:now,text:"/help"}}),s.env,async()=>{calls++;},now,action);
  assert.equal(reply.status,200);assert.equal(calls,0);assert.equal(typing,1);
 }finally{await s.close();}
});
