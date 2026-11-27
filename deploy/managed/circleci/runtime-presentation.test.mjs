import test from "node:test";
import assert from "node:assert/strict";
import {HOME,MENU,formatBytes,fileCard,taskView} from "./runtime-presentation.mjs";
const now=1800000000;
function row(i,changes={}){return {job_id:"pilot_"+i.toString(16).padStart(32,"0"),profile:"cn",target:"6745890963",
 state:"completed",finished_at:now-5,file_id:"SYNTHETIC_FILE",filename:"演示应用_"+i+".ipa",
 plaintext_bytes:342632968,link_expires:now+3600,...changes};}
test("home is brief and every button payload fits Telegram's limit",()=>{
 assert.ok(HOME.includes("\n\n"));assert.ok(!HOME.includes("pilot_"));assert.ok(HOME.length<220);assert.ok(!HOME.includes("仅限本人"));assert.ok(!HOME.includes("2 GB"));
 for(const r of MENU.inline_keyboard)for(const button of r)assert.ok(Buffer.byteLength(button.callback_data)<=64);
});
test("file cards display a readable name/version and decimal file size",()=>{
 assert.equal(formatBytes(342632968),"342.6 MB");assert.equal(formatBytes(1500000000),"1.50 GB");
 assert.equal(formatBytes(undefined),"");
 const text=fileCard("演示应用_7.4.7.ipa",342632968);
 assert.ok(text.includes("演示应用\n版本 7.4.7 · 342.6 MB"));assert.ok(!text.includes("342632968"));
 assert.ok(!text.includes(".ipa"));assert.ok(!text.includes("pilot_"));
});
test("many applications render only three rows with pagination and private task buttons",()=>{
 const view=taskView(Array.from({length:100},(_,i)=>row(i+1)),"c",0,now);
 assert.equal((view.text.match(/^[1-3]\. /gm)||[]).length,3);
 assert.ok(!view.text.includes("pilot_"));assert.ok(!view.text.includes("演示应用_4"));
 const buttons=view.reply_markup.inline_keyboard.flat();
 assert.equal(buttons.filter(b=>b.callback_data.startsWith("rt:get:")).length,3);
 assert.ok(buttons.filter(b=>b.callback_data.startsWith("rt:get:")).every(b=>b.text==="演示应用"));
 assert.ok(buttons.some(b=>b.callback_data==="rt:list:c:1"));
 assert.ok(buttons.every(b=>Buffer.byteLength(b.callback_data)<=64));
 const next=taskView([row(4),row(5)],"c",1,now);
 assert.ok(next.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="rt:list:c:0"));
});
test("expired, unfinished and catalog results never masquerade as a ready file",()=>{
 for(const change of [{link_expires:now-1},{finished_at:null},{file_id:null},{catalog_job:"catalog",catalog_ready:1,file_id:null}]){
  const view=taskView([row(1,change)],"c",0,now);
  assert.equal(view.reply_markup.inline_keyboard.flat().filter(b=>b.callback_data.startsWith("rt:get:")).length,0);
 }
 const active=taskView([row(1,{state:"running",filename:null,display_filename:"曾完成应用_1.0.ipa",finished_at:null,file_id:null,plaintext_bytes:null})],"a",0,now);
 assert.ok(active.text.includes("曾完成应用"));assert.ok(active.text.includes("最新版"));
 assert.ok(!active.text.includes("1.0"));assert.ok(active.reply_markup.inline_keyboard.flat().some(b=>b.callback_data.startsWith("rt:cancel:")));
});
