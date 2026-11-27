import {showTyping} from "./runtime-chat-action.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import {Miniflare} from "miniflare";
import {NOTIFY_SCHEMA,notifyOwner} from "./runtime-notify.mjs";
const env={RUNTIME_TELEGRAM_ENABLED:"1",RUNTIME_OWNER_ID:"12345",TELEGRAM_BOT_TOKEN:"123456789:"+"T".repeat(36)};
const task={job_id:"pilot_"+"a".repeat(32),kind:"export",owner_id:"12345",state:"link_ready",finished_at:100,
 file_id:"SYNTHETIC_FILE_12345",filename:"Synthetic.ipa",plaintext_bytes:100};
async function setup(){
 const mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('disabled')}}",
  compatibilityDate:"2026-07-30",cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"77777777-7777-4777-8777-777777777777"}});
 const DB=await mf.getD1Database("DB");await DB.prepare(NOTIFY_SCHEMA).run();
 return {env:{...env,DB},close:()=>mf.dispose()};
}
test("a confirmed owner-private notice is sent once across repeated finish acknowledgements",async()=>{
 const s=await setup();let calls=0,actions=0;try{
  const send=async(url,options)=>{
   if(url.endsWith("/sendChatAction")){actions++;assert.deepEqual(JSON.parse(options.body),{chat_id:12345,action:"typing"});return Response.json({ok:true,result:true});}
   calls++;assert.equal(options.redirect,"manual");assert.equal(options.method,"POST");
   const body=JSON.parse(options.body);assert.equal(body.chat_id,12345);
   assert.ok(body.text.includes("文件已准备好"));assert.ok(body.text.includes("100 B"));assert.ok(!body.text.includes("pilot_"));
   assert.equal(body.reply_markup.inline_keyboard[0][0].url,"https://drive.google.com/file/d/"+task.file_id+"/view");
   return Response.json({ok:true,result:{message_id:1,chat:{id:12345,type:"private"}}});
  };
  for(let i=0;i<3;i++)assert.equal(await notifyOwner(s.env,task,100+i,send),true);
  assert.equal(calls,1);assert.equal(actions,1);
 }finally{await s.close();}
});
test("an unknown send or wrong recipient acknowledgement is retained without another POST",async()=>{
 for(const mode of ["network","wrong-owner"]){
  const s=await setup();let calls=0;try{
   const send=async(url)=>{
    if(url.endsWith("/sendChatAction"))return Response.json({ok:true,result:true});
    calls++;if(mode==="network")throw Error("synthetic-transport-unknown");
    return Response.json({ok:true,result:{message_id:1,chat:{id:99999,type:"private"}}});
   };
   for(let i=0;i<3;i++)assert.equal(await notifyOwner(s.env,task,100+i,send),false);
   assert.equal(calls,1);assert.equal((await s.env.DB.prepare("SELECT state FROM runtime_notifications").first()).state,"unknown");
  }finally{await s.close();}
 }
});
test("disabled, cancelled, unfinished and non-owner tasks cannot create a notice",async()=>{
 const s=await setup();let calls=0;try{
  const send=async()=>{calls++;throw Error("unexpected");};
  assert.equal(await notifyOwner({...s.env,RUNTIME_TELEGRAM_ENABLED:"0"},task,100,send),false);
  for(const changed of [{owner_id:"54321"},{state:"cancel_pending"},{finished_at:null},{kind:"fixture"}])
   await assert.rejects(notifyOwner(s.env,{...task,...changed},100,send));
  assert.equal(calls,0);assert.equal((await s.env.DB.prepare("SELECT count(*) n FROM runtime_notifications").first()).n,0);
 }finally{await s.close();}
});

test("a failed typing hint does not block or repeat an acknowledged file notice",async()=>{
 const s=await setup();let messages=0;try{
  const send=async(url)=>{
   if(url.endsWith("/sendChatAction"))throw Error("synthetic-hint-transport-failure");
   messages++;return Response.json({ok:true,result:{message_id:2,chat:{id:12345,type:"private"}}});
  };
  for(let i=0;i<2;i++)assert.equal(await notifyOwner(s.env,task,100+i,send),true);
  assert.equal(messages,1);
 }finally{await s.close();}
});
test("typing hints are disabled without a valid configured private owner",async()=>{
 let calls=0;const send=async()=>{calls++;throw Error("must-not-call");};
 for(const changed of [{RUNTIME_TELEGRAM_ENABLED:"0"},{RUNTIME_OWNER_ID:""},{TELEGRAM_BOT_TOKEN:""}])
  assert.equal(await showTyping({...env,...changed},send),false);
 assert.equal(calls,0);
});
