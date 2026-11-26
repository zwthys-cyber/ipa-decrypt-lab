import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {Miniflare} from "miniflare";
import {CATALOG_SCHEMA} from "./runtime-catalog.mjs";
import {RUNTIME_SCHEMA} from "./runtime-schema.mjs";
import {TASK_SCHEMA,admitExport} from "./runtime-tasks.mjs";
import {CANARY_SCHEMA,installCanary,canaryWindow,revokeCanary} from "./runtime-canary.mjs";
globalThis.crypto??=webcrypto;
const owner="12345",source="a".repeat(40),now=Math.floor(Date.now()/1000);
const hash=async s=>Buffer.from(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s))).toString("hex");
async function setup(){
 const mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled')}}",
  compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"66666666-6666-4666-8666-666666666666"}});
 const DB=await mf.getD1Database("DB");
 for(const sql of (RUNTIME_SCHEMA+TASK_SCHEMA+CANARY_SCHEMA+CATALOG_SCHEMA).split(";").map(s=>s.trim()).filter(Boolean))await DB.prepare(sql).run();
 return {env:{DB,RUNTIME_MODE:"staging",RUNTIME_EXPORT_ENABLED:"1",RUNTIME_OWNER_ID:owner,RUNTIME_SOURCE_SHA:source},close:()=>mf.dispose()};
}
async function packet(){
 const scope=await hash("telegram-owner:"+owner),request_id="d".repeat(32);
 const original={scope,rid:"e".repeat(32),app:"123456",state:"pending",at:now,created:now};
 const legacy=[{owner_id:owner,request_id:original.rid,profile:"default",target:original.app,state:original.state,
  created_at:now,source_json:JSON.stringify(original),held:1}];
 return {nonce:"c".repeat(32),snapshot_sha256:"b".repeat(64),
  session_sha256:"8349899c8806e2481edfc6f8f532d6aaa855f32c241b86951a03ea62df799765",
  paused_at:now-5,expires_at:now+600,request_id,target:"6739782103",telegram_update_floor:100,
  rows_sha256:await hash(JSON.stringify(legacy)),legacy};
}
test("a real canary window preserves held source rows and admits only the one bound request",async()=>{
 const s=await setup();try{
  const p=await packet();const imported=await installCanary(s.env,p,now);
  assert.equal(imported.held_rows,1);assert.equal((await canaryWindow(s.env,now)).lease_deadline,p.expires_at);
  s.env.RUNTIME_MODE="production";
  const request={profile:"default",request_id:p.request_id,target:p.target,version:""};
  const row=await admitExport(s.env,request,now);assert.equal(row.deadline,p.expires_at);
  assert.equal(row.kind,"export");assert.equal(row.state,"waiting");
  assert.equal((await s.env.DB.prepare("SELECT count(*) n FROM runtime_jobs").first()).n,1);
  assert.equal((await s.env.DB.prepare("SELECT held FROM runtime_canary_legacy").first()).held,1);
  for(const changed of [{target:"123456"},{request_id:"f".repeat(32)},{version:"1.2"}])
   await assert.rejects(admitExport(s.env,{...request,...changed},now),/canary_request_binding/);
  await revokeCanary(s.env,p.nonce,now+1);
  await assert.rejects(admitExport(s.env,request,now+2),/canary_closed/);
 }finally{await s.close();}
});
test("expiry, immutable binding, owner scope and source digest fail before real task admission",async()=>{
 const s=await setup();try{
  const p=await packet();
  await assert.rejects(installCanary(s.env,{...p,paused_at:now-121},now),/proof/);
  await assert.rejects(installCanary(s.env,{...p,expires_at:now+901},now),/proof/);
  await assert.rejects(installCanary(s.env,{...p,rows_sha256:"0".repeat(64)},now),/digest/);
  await installCanary(s.env,p,now);
  await assert.rejects(installCanary(s.env,{...p,target:"123456"},now),/immutable/);
  await assert.rejects(canaryWindow(s.env,now+901),/closed/);
  await s.env.DB.prepare("UPDATE runtime_canary_legacy SET state='delivered'").run();
  await assert.rejects(canaryWindow(s.env,now),/import_binding/);
  assert.equal((await s.env.DB.prepare("SELECT count(*) n FROM runtime_jobs").first()).n,0);
 }finally{await s.close();}
});
