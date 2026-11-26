// Owner-private managed entry; it remains closed until the final handoff is sealed.
import {requireEntry} from "./runtime-tasks.mjs";
const ID=/^pilot_[a-f0-9]{32}$/;
function response(status,value={ok:true}){return Response.json(value,{status,headers:{"cache-control":"no-store"}});}
function say(owner,text,extra={}){return response(200,{method:"sendMessage",chat_id:Number(owner),text,...extra});}
const HELP="发送 App Store／TestFlight 链接开始处理；/version 链接 版本号 可指定历史版本；/status 查看任务；/get 任务编号 领取私有文件；/cancel 任务编号 取消。";
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
export async function handleManagedTelegram(request,env,invoke,now=Math.floor(Date.now()/1000)){
 if(new URL(request.url).pathname!=="/telegram"||request.method!=="POST"||new URL(request.url).search)return response(404,{ok:false});
 if(env.RUNTIME_TELEGRAM_ENABLED!=="1")return response(503,{ok:false});
 let handoff;try{handoff=await requireEntry(env);}catch{return response(503,{ok:false});}
 const secret=env.TELEGRAM_WEBHOOK_SECRET||"",supplied=request.headers.get("x-telegram-bot-api-secret-token")||"";
 if(!/^[A-Za-z0-9_-]{43,128}$/.test(secret)||!await sameSecret(secret,supplied))return response(401,{ok:false});
 if(!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("content-type")||""))return response(400,{ok:false});
 let update;try{update=await payload(request);}catch{return response(400,{ok:false});}
 const m=update?.message,owner=env.RUNTIME_OWNER_ID;
 if(!Number.isSafeInteger(update?.update_id)||update.update_id<handoff.telegram_update_floor||m?.chat?.type!=="private"||
  m?.from?.is_bot!==false||!Number.isSafeInteger(m?.from?.id)||m.from.id<=0||m.chat.id!==m.from.id||
  String(m.from.id)!==owner||!Number.isSafeInteger(m.date)||m.date<now-86400||m.date>now+60||
  typeof m.text!=="string"||m.text.length>1024)return response(200);
 const text=m.text.trim();
 try{
  if(["/start","/help"].includes(text))return say(owner,HELP);
  if(text==="/status"){
   const rows=await env.DB.prepare("SELECT job_id FROM runtime_jobs WHERE owner_id=? AND kind='export' ORDER BY created_at DESC,job_id DESC LIMIT 5").bind(owner).all();
   const labels={waiting:"等待处理",dispatch_intent:"正在提交",dispatch_unknown:"提交结果待核对",submitted:"等待工作机",
    running:"处理中",uploading:"上传私有文件",link_ready:"等待最终确认",completed:"已核验，可用 /get 领取",
    closed:"任务已结束",cancelled:"已取消",cancel_pending:"取消结果待核对",failed_pending:"等待工作机结束确认"};
   const lines=[];
   for(const row of rows.results||[]){
    const value=await invoke("status",{job_id:row.job_id});
    lines.push(row.job_id+" · "+(labels[value.state]||"状态待核对"));
   }
   return say(owner,lines.join("\n")||"暂无新任务。");
  }
  if(text.startsWith("/get ")||text.startsWith("/cancel ")){
   const get=text.startsWith("/get "),id=text.slice(get?5:8).trim();
   if(!ID.test(id))return say(owner,"任务编号无效。");
   const value=await invoke(get?"owner-get":"owner-cancel",{job_id:id});
   if(!get)return say(owner,value.state==="cancelled"?"已取消。":"已记录取消请求，确认工作机结束前不会释放任务容量。");
   return say(owner,"私有文件已核验\n文件："+value.filename+"\n大小："+value.bytes+" 字节\nSHA-256："+value.sha256+
    "\n请登录自己的 Google 账号访问。领取期限不等于网盘文件权限到期。",
    {reply_markup:{inline_keyboard:[[{text:"打开私有文件",url:value.url}]]},link_preview_options:{is_disabled:true}});
  }
  const parsed=parseTask(text);if(!parsed)return say(owner,HELP);
  const raw=await crypto.subtle.digest("SHA-256",new TextEncoder().encode("telegram-managed\0"+owner+"\0"+update.update_id));
  const tag=Array.from(new Uint8Array(raw),x=>x.toString(16).padStart(2,"0")).join("").slice(0,32);
  const request_id=({default:"",cn:"cn_",tf:"tf_"}[parsed.profile])+tag;
  const value=await invoke("admit-export",{...parsed,request_id});
  return say(owner,"已提交："+value.job_id+"\n可用 /status 查看状态；完成后用 /get "+value.job_id+" 领取私有文件。");
 }catch(error){
  if(["runtime_entry_disabled","runtime_handoff_required","runtime_tf_handoff_required"].includes(error?.message))
   return say(owner,"迁移交接尚未完成，当前没有提交新的下载任务。");
  if(error?.message==="runtime_daily_or_queue_limit")return say(owner,"已达到每日或等待任务上限。");
  if(error?.message==="runtime_link_unavailable")return say(owner,"文件尚未完成核验，或领取期限已过。");
  // A webhook retry reuses the same request ID; never invent a replacement task.
  return response(503,{ok:false});
 }
}
