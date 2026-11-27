import {showTyping} from "./runtime-chat-action.mjs";
import {HOME,HELP,MENU,taskView,fileCard} from "./runtime-presentation.mjs";
import {quarantineUpdate} from "./runtime-recovery.mjs";
// Owner-private managed entry; it remains closed until the final handoff is sealed.
import {requireEntry} from "./runtime-tasks.mjs";
const ID=/^pilot_[a-f0-9]{32}$/;
function response(status,value={ok:true}){return Response.json(value,{status,headers:{"cache-control":"no-store"}});}
function say(owner,text,extra={}){return response(200,{method:"sendMessage",chat_id:Number(owner),text,...extra});}
async function sameSecret(a,b){
 const digest=async x=>new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(x)));
 const [left,right]=await Promise.all([digest(a),digest(b)]);let diff=0;
 for(let i=0;i<left.length;i++)diff|=left[i]^right[i];return diff===0;
}
async function payload(request){
 if(!request.body)throw Error("body");const reader=request.body.getReader(),parts=[];let n=0;
 try{for(;;){const {done,value}=await reader.read();if(done)break;n+=value.byteLength;if(n>16384)throw Error("body");parts.push(value);}}
 finally{try{await reader.cancel();}catch{}reader.releaseLock();}
 const raw=new Uint8Array(n);let offset=0;for(const part of parts){raw.set(part,offset);offset+=part.byteLength;}
 return JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(raw));
}
export function parseTask(text){
 if(typeof text!=="string"||text.length>1024)return null;
 let value=text.trim(),version="";
 if(value.startsWith("/version ")){
  const parts=value.slice(9).trim().split(/\s+/);if(parts.length!==2)return null;
  [value,version]=parts;
 }
 if(/\s/.test(value))return null;
 if(/^[1-9][0-9]{4,19}$/.test(value))return {profile:"default",target:value,version};
 try{
  const url=new URL(value);if(url.username||url.password||url.port||url.hash)return null;
  if(url.hostname==="testflight.apple.com"&&["https:","itms-beta:"].includes(url.protocol)){
   const found=/^\/join\/([A-Za-z0-9_-]{6,80})\/?$/.exec(url.pathname);
   return found&&!url.search&&!version?{profile:"tf",target:found[1],version:""}:null;
  }
  if(url.protocol!=="https:"||url.hostname!=="apps.apple.com")return null;
  const found=/\/id([1-9][0-9]{4,19})\/?$/.exec(url.pathname);
  return found?{profile:url.pathname.split("/")[1]?.toLowerCase()==="cn"?"cn":"default",target:found[1],version}:null;
 }catch{return null;}
}
export async function handleManagedTelegram(request,env,invoke,now=Math.floor(Date.now()/1000),send=fetch){
 if(new URL(request.url).pathname!=="/telegram"||request.method!=="POST"||new URL(request.url).search)return response(404,{ok:false});
 if(env.RUNTIME_TELEGRAM_ENABLED!=="1")return response(503,{ok:false});
 let handoff;try{handoff=await requireEntry(env);}catch{return response(503,{ok:false});}
 const secret=env.TELEGRAM_WEBHOOK_SECRET||"",supplied=request.headers.get("x-telegram-bot-api-secret-token")||"";
 if(!/^[A-Za-z0-9_-]{43,128}$/.test(secret)||!await sameSecret(secret,supplied))return response(401,{ok:false});
 if(!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("content-type")||""))return response(400,{ok:false});
 let update;try{update=await payload(request);}catch{return response(400,{ok:false});}
 const owner=env.RUNTIME_OWNER_ID;
 if(!Number.isSafeInteger(update?.update_id)||update.update_id<handoff.telegram_update_floor)return response(200);
 if(handoff.offline){
  const oldMessage=update.message||update.callback_query?.message,actor=update.message?.from||update.callback_query?.from;
  if(actor?.is_bot===false&&String(actor.id)===owner&&oldMessage?.chat?.type==="private"&&String(oldMessage.chat.id)===owner&&
   (!Number.isSafeInteger(oldMessage.date)||oldMessage.date<handoff.activated_at)){
   try{await quarantineUpdate(env,update,now);return response(200);}catch{return response(503,{ok:false});}
  }
 }
 async function requestTag(profile,suffix=""){
  const raw=await crypto.subtle.digest("SHA-256",new TextEncoder().encode("telegram-managed\0"+owner+"\0"+update.update_id+suffix));
  return ({default:"",cn:"cn_",tf:"tf_"}[profile])+Array.from(new Uint8Array(raw),x=>x.toString(16).padStart(2,"0")).join("").slice(0,32);
 }
 const callback=update.callback_query;let callbackCommand=null;
 if(callback){
  const m=callback.message,actor=callback.from;
  const navigation=typeof callback.data==="string"&&/^rt:(home|help|status|list:([ach]):([0-9]{1,4})|get:([a-f0-9]{32})|cancel:([a-f0-9]{32}))$/.exec(callback.data);
  const match=typeof callback.data==="string"&&/^cv:([a-f0-9]{32}):([vpnr])(?::([1-9][0-9]{5,19}))?$/.exec(callback.data);
  if(actor?.is_bot!==false||!Number.isSafeInteger(actor?.id)||String(actor.id)!==owner||
   m?.chat?.type!=="private"||m.chat.id!==actor.id||m?.from?.is_bot!==true||
   String(m.from.id)!==(env.TELEGRAM_BOT_TOKEN||"").split(":")[0]||
   !Number.isSafeInteger(m.message_id)||m.message_id<=0||!Number.isSafeInteger(m.date)||m.date>now+60||m.date<now-21600||
   typeof callback.id!=="string"||!callback.id.length||callback.id.length>128||(!match&&!navigation)||
   (match&&((match[2]==="v")!==!!match[3])))return response(200);
  if(navigation){
   callbackCommand=navigation[2]?"/tasks "+navigation[2]+" "+navigation[3]:navigation[4]?"/get pilot_"+navigation[4]:
    navigation[5]?"/cancel pilot_"+navigation[5]:navigation[1]==="home"?"/start":"/"+navigation[1];
  }else{
  try{
   // Region is read from the acknowledged menu, never from callback text.
   const view=await env.DB.prepare("SELECT j.profile FROM runtime_catalog_views v JOIN runtime_jobs j ON j.job_id=v.job_id WHERE v.view_id=? AND v.owner_id=?").bind(match[1],owner).first();
   if(!view)return response(200);
   const value=await invoke("catalog-action",{request_id:await requestTag(view.profile,":catalog-action"),view_id:match[1],
    message_id:m.message_id,action:match[2],version_id:match[3]||""});
   return response(200,{method:"answerCallbackQuery",callback_query_id:callback.id,
    text:value.selected?"已选择版本，开始处理。":value.menu_notified?"已打开版本列表。":"已提交版本查询，可用 /status 查看。"});
  }catch(error){
   if(["runtime_catalog_view_expired","runtime_catalog_already_selected","runtime_catalog_selection","runtime_catalog_page_limit"].includes(error?.message))
    return response(200,{method:"answerCallbackQuery",callback_query_id:callback.id,text:"列表已使用或已过期，请重新发送 /versions 链接。"});
   if(["runtime_catalog_rate_limit","runtime_daily_or_queue_limit"].includes(error?.message))
    return response(200,{method:"answerCallbackQuery",callback_query_id:callback.id,text:"已达到查询频率或任务上限，请稍后重试。"});
   return response(503,{ok:false});
  }
 }
 }
 const m=callbackCommand?callback.message:update?.message;
 if(!callbackCommand&&(m?.chat?.type!=="private"||
  m?.from?.is_bot!==false||!Number.isSafeInteger(m?.from?.id)||m.from.id<=0||m.chat.id!==m.from.id||
  String(m.from.id)!==owner||!Number.isSafeInteger(m.date)||m.date<now-86400||m.date>now+60||
  typeof m.text!=="string"||m.text.length>1024))return response(200);
 const text=callbackCommand||m.text.trim();
 if(!callbackCommand)await showTyping(env,send);
 const respond=async(text,extra={})=>{
  if(!callbackCommand)return say(owner,text,{reply_markup:MENU,link_preview_options:{is_disabled:true},...extra});
  // Acknowledge the spinner separately; editing an existing message does not resend a file.
  try{await send("https://api.telegram.org/bot"+env.TELEGRAM_BOT_TOKEN+"/answerCallbackQuery",{
   method:"POST",redirect:"manual",signal:AbortSignal.timeout(2000),headers:{"content-type":"application/json"},
   body:JSON.stringify({callback_query_id:callback.id})});}catch{}
  return response(200,{method:"editMessageText",chat_id:Number(owner),message_id:m.message_id,text,reply_markup:MENU,link_preview_options:{is_disabled:true},...extra});
 };
 try{
  if(text==="/start")return respond(HOME);
  if(text==="/help")return respond(HELP);
  if(text==="/status"||text==="/history"||/^\/tasks [ach] [0-9]{1,4}$/.test(text)){
   let group=text==="/history"?"h":text.startsWith("/tasks ")?text.split(" ")[1]:"a";
   const page=text.startsWith("/tasks ")?Number(text.split(" ")[2]):0;
   const filters={a:"j.state NOT IN ('closed','cancelled','completed') AND NOT (j.state='link_ready' AND j.finished_at IS NOT NULL)",
    c:"(j.state='completed' OR (j.state='link_ready' AND j.finished_at IS NOT NULL))",
    h:"j.state='cancelled'"};
   const read=async group=>(await env.DB.prepare("SELECT j.job_id,j.state,j.profile,j.target,j.version,j.filename,j.plaintext_bytes,j.link_expires,j.finished_at,j.file_id,"+
    "COALESCE(j.filename,(SELECT prior.filename FROM runtime_jobs prior WHERE prior.owner_id=j.owner_id AND prior.profile=j.profile AND prior.target=j.target AND prior.filename IS NOT NULL ORDER BY prior.created_at DESC LIMIT 1)) display_filename,"+
    "s.job_id catalog_job,s.result_json IS NOT NULL catalog_ready FROM runtime_jobs j LEFT JOIN runtime_catalog_specs s ON s.job_id=j.job_id WHERE j.owner_id=? AND j.kind='export' AND "+filters[group]+
    " ORDER BY j.created_at DESC,j.job_id DESC LIMIT 4 OFFSET ?").bind(owner,page*3).all()).results||[];
   let rows=await read(group);
   if(text==="/status"&&!rows.length){group="c";rows=await read(group);}
   const view=taskView(rows,group,page,now);return respond(view.text,{reply_markup:view.reply_markup});
  }
  if(text.startsWith("/get ")||text.startsWith("/cancel ")){
   const get=text.startsWith("/get "),id=text.slice(get?5:8).trim();
   if(!ID.test(id))return respond("任务编号无效。");
   const value=await invoke(get?"owner-get":"owner-cancel",{job_id:id});
   if(!get)return respond(value.state==="cancelled"?"已取消。":value.state==="completed"?"文件已完成核验，无法取消已完成任务。":"已记录取消请求，确认工作机结束前不会释放任务容量。");
   return respond(fileCard(value.filename,value.bytes),
    {reply_markup:{inline_keyboard:[[{text:"打开文件",url:value.url}],[{text:"我的文件",callback_data:"rt:list:c:0"},{text:"首页",callback_data:"rt:home"}]]},link_preview_options:{is_disabled:true}});
  }
  if(text.startsWith("/versions ")){
   const parsed=parseTask(text.slice(10).trim());
   if(!parsed||parsed.profile==="tf"||parsed.version)return respond("请发送 /versions App Store链接 或 /versions AppID。");
   const value=await invoke("catalog-open",{profile:parsed.profile,target:parsed.target,request_id:await requestTag(parsed.profile,":catalog")});
   return respond(value.menu_notified?"已打开版本列表。":"已提交版本查询\n\n查询完成后会发送版本按钮。");
  }
  const parsed=parseTask(text);if(!parsed)return respond(HELP);
  const raw=await crypto.subtle.digest("SHA-256",new TextEncoder().encode("telegram-managed\0"+owner+"\0"+update.update_id));
  const tag=Array.from(new Uint8Array(raw),x=>x.toString(16).padStart(2,"0")).join("").slice(0,32);
  const request_id=({default:"",cn:"cn_",tf:"tf_"}[parsed.profile])+tag;
  const value=await invoke("admit-export",{...parsed,request_id});
  return respond("已加入处理队列\n\n"+(parsed.profile==="cn"?"国区":parsed.profile==="tf"?"TestFlight":"App Store")+" · "+(parsed.profile==="tf"?"测试应用":"App "+parsed.target)+"\n完成后会通知你。",
   {reply_markup:{inline_keyboard:[[{text:"查看进度",callback_data:"rt:status"},{text:"取消任务",callback_data:"rt:cancel:"+value.job_id.slice(6)}]]}});
 }catch(error){
  if(["runtime_entry_disabled","runtime_handoff_required","runtime_tf_handoff_required"].includes(error?.message))
   return respond("迁移交接尚未完成，当前没有提交新的下载任务。");
  if(error?.message==="runtime_catalog_rate_limit")return respond("已达到目录查询频率或每日上限，请稍后重试。");
  if(error?.message==="runtime_daily_or_queue_limit")return respond("已达到每日或等待任务上限。");
  if(error?.message==="runtime_link_unavailable")return respond("文件尚未完成核验，或领取期限已过。");
  // A webhook retry reuses the same request ID; never invent a replacement task.
  return response(503,{ok:false});
 }
}
