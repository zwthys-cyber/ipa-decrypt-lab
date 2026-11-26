// Free control-plane pilot: no external task dispatch, uploads or billing APIs.
import {configured as linksConfigured,registerLink,getLink,retireLink} from "./private-link.mjs";
import {googleFetch} from "./drive-auth.mjs";
import {handleRuntime} from "../circleci/control.mjs";
const SECRET=/^[A-Za-z0-9_-]{43,128}$/;
const OWNER=/^[1-9][0-9]{0,15}$/;
const APP=/^[1-9][0-9]{4,19}$/;
const JOB=/^pilot_[a-f0-9]{32}$/;
const MAX_BODY=16384;
export const SQL={
  insert:`INSERT INTO pilot_jobs(job_id,owner_id,update_id,app_id,region,day,created_at,state)
    SELECT ?,?,?,?,?,?,?,'waiting_for_runtime'
    WHERE (SELECT count(*) FROM pilot_jobs WHERE owner_id=? AND day=?)<3
      AND (SELECT count(*) FROM pilot_jobs j WHERE j.owner_id=? AND j.state='waiting_for_runtime'
        AND NOT EXISTS (SELECT 1 FROM pilot_links l WHERE l.job_id=j.job_id))<30
    ON CONFLICT(owner_id,update_id) DO NOTHING`,
  existing:"SELECT job_id FROM pilot_jobs WHERE owner_id=? AND update_id=?",
  recent:`SELECT j.job_id,j.app_id,j.region,j.state,l.expires_at,l.retired_at FROM pilot_jobs j
    LEFT JOIN pilot_links l ON l.job_id=j.job_id AND l.owner_id=j.owner_id
    WHERE j.owner_id=? ORDER BY j.created_at DESC,j.job_id DESC LIMIT 5`,
  cancel:"UPDATE pilot_jobs SET state='cancelled' WHERE owner_id=? AND job_id=? AND state='waiting_for_runtime'"
};
function response(status,value={ok:true}) {
  return new Response(JSON.stringify(value),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});
}
function say(chat,text) {
  // Telegram's webhook-response method is best effort, not a confirmed send.
  return response(200,{method:"sendMessage",chat_id:chat,text});
}
async function sameSecret(a,b) {
  const enc=new TextEncoder();
  const left=new Uint8Array(await crypto.subtle.digest("SHA-256",enc.encode(a)));
  const right=new Uint8Array(await crypto.subtle.digest("SHA-256",enc.encode(b)));
  let diff=0;
  for(let i=0;i<left.length;i++)diff|=left[i]^right[i];
  return diff===0;
}
async function body(request) {
  const length=request.headers.get("content-length");
  if(length!==null&&(!/^\d{1,5}$/.test(length)||Number(length)<1||Number(length)>MAX_BODY))throw Error("body");
  if(!request.body)throw Error("body");
  const reader=request.body.getReader(),chunks=[];
  let n=0;
  try {
    for(;;){
      const {done,value}=await reader.read();
      if(done)break;
      n+=value.byteLength;
      if(n>MAX_BODY){await reader.cancel();throw Error("body");}
      chunks.push(value);
    }
  }finally{reader.releaseLock();}
  if(!n)throw Error("body");
  const data=new Uint8Array(n);
  let i=0;for(const chunk of chunks){data.set(chunk,i);i+=chunk.byteLength;}
  return JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(data));
}
export function target(text){
  if(typeof text!=="string"||text.length>1024||/\s/.test(text))return null;
  if(APP.test(text))return {app:text,region:"default"};
  try{
    const url=new URL(text);
    if(url.protocol!=="https:"||url.hostname!=="apps.apple.com"||url.port||url.username||url.password||url.hash)return null;
    const found=/\/id([1-9][0-9]{4,19})\/?$/.exec(url.pathname);
    if(!found)return null;
    return {app:found[1],region:url.pathname.split("/")[1]?.toLowerCase()==="cn"?"cn":"default"};
  }catch{return null;}
}
function actor(update,owner,now){
  if(!update||typeof update!=="object"||!Number.isSafeInteger(update.update_id)||update.update_id<0)return null;
  const m=update.message;
  if(!m||m.chat?.type!=="private"||m.from?.is_bot!==false||
    !Number.isSafeInteger(m.from?.id)||m.from.id<=0||m.chat.id!==m.from.id||String(m.from.id)!==owner||
    !Number.isSafeInteger(m.date)||m.date<now-86400||m.date>now+60||typeof m.text!=="string"||m.text.length>1024)return null;
  return {id:m.from.id,text:m.text.trim(),update:update.update_id,date:m.date};
}
const HELP="免费控制层试验版：仅登记任务，不自动下载。发送 App Store 链接或数字 App ID；/status 查看最近任务；/cancel 任务编号 取消；/get 任务编号 领取已核对的私有网盘链接（需配置）。每天最多登记 3 次，最多 30 个等待任务。不支持 TestFlight。";
export async function handle(request,env,now=Math.floor(Date.now()/1000),send=googleFetch,runtimeSend=fetch){
  const url=new URL(request.url);
  if(url.pathname.startsWith("/v1/runtime/"))return handleRuntime(request,env,now,runtimeSend);
  if(request.method!=="POST"||!["/telegram","/v1/link-register","/v1/link-retire"].includes(url.pathname)||url.search)return response(404,{ok:false});
  if(env.PILOT_ENABLED!=="1"||!OWNER.test(env.PILOT_OWNER_ID||"")||
     !SECRET.test(env.TELEGRAM_WEBHOOK_SECRET||"")||!env.DB?.prepare)return response(503,{ok:false});
  if(url.pathname!=="/telegram"){
    if(env.PILOT_LINK_ENABLED!=="1"||(url.pathname==="/v1/link-register"&&!linksConfigured(env))||!SECRET.test(env.PILOT_LINK_ISSUER_TOKEN||"")||
       env.PILOT_LINK_ISSUER_TOKEN===env.TELEGRAM_WEBHOOK_SECRET)return response(503,{ok:false});
    const supplied=request.headers.get("authorization")||"";
    if(!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(supplied)||!await sameSecret(supplied,"Bearer "+env.PILOT_LINK_ISSUER_TOKEN))return response(401,{ok:false});
    if(request.headers.get("content-type")!=="application/json")return response(400,{ok:false});
    try{
      const value=await body(request);
      if(url.pathname==="/v1/link-retire"){
        const retired=await retireLink(env.DB,env.PILOT_OWNER_ID,value,now);
        return response(retired?200:409,{ok:retired});
      }
      const stored=await registerLink(env.DB,env.PILOT_OWNER_ID,value,env,now,send);
      return response(stored?201:409,{ok:stored});
    }catch{return response(409,{ok:false});}
  }
  const supplied=request.headers.get("x-telegram-bot-api-secret-token")||"";
  if(!SECRET.test(supplied)||!await sameSecret(supplied,env.TELEGRAM_WEBHOOK_SECRET))return response(401,{ok:false});
  if(!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("content-type")||""))return response(400,{ok:false});
  let update;
  try{update=await body(request);}catch{return response(400,{ok:false});}
  const item=actor(update,env.PILOT_OWNER_ID,now);
  if(!item)return response(200);
  const owner=env.PILOT_OWNER_ID;
  const db=env.DB;
  try{
    if(item.text==="/start"||item.text==="/help")return say(item.id,HELP);
    if(item.text==="/status"){
      const result=await db.prepare(SQL.recent).bind(owner).all();
      if(result.success!==true||!Array.isArray(result.results))throw Error("db");
      const rows=result.results.map(row=>{
        if(!JOB.test(row.job_id)||!APP.test(row.app_id)||!["cn","default"].includes(row.region)||
          !["waiting_for_runtime","cancelled"].includes(row.state))throw Error("row");
        let label="等待可用计算环境";
        if(row.state==="cancelled")label="已取消";
        else if(Number.isSafeInteger(row.retired_at))label="链接已退役（不代表网盘已删除）";
        else if(Number.isSafeInteger(row.expires_at))label=row.expires_at<=now?"领取期限已过":"已登记私有文件（/get 核验领取）";
        return row.job_id+" · "+row.app_id+" · "+(row.region==="cn"?"国区":"外区")+" · "+label;
      });
      return say(item.id,"试验版最近任务（不自动下载）：\n"+(rows.join("\n")||"暂无"));
    }
    if(item.text.startsWith("/get ")){
      const id=item.text.slice(5).trim();
      if(!JOB.test(id))return say(item.id,"任务编号无效。");
      if(!linksConfigured(env))return say(item.id,"私有网盘链接功能尚未配置。");
      const link=await getLink(db,owner,id,env,now,send);
      if(!link)return say(item.id,"暂无有效链接，或任务已取消、领取期限已过。");
      // Only the authorized private sender receives this link; disable link previews.
      return response(200,{method:"sendMessage",chat_id:item.id,
        text:"私有文件链接（已存入，网盘信息已核对）\n文件："+link.filename+"\n大小："+link.bytes+" 字节\nSHA-256："+link.sha256+"\n请登录指定 Google 账号访问。领取期限不等于网盘权限到期。",
        reply_markup:{inline_keyboard:[[{text:"打开私有下载链接",url:link.url}]]},
        link_preview_options:{is_disabled:true}});
    }
    if(item.text.startsWith("/cancel ")){
      const id=item.text.slice(8).trim();
      if(!JOB.test(id))return say(item.id,"任务编号无效。");
      const result=await db.prepare(SQL.cancel).bind(owner,id).run();
      if(result.success!==true||![0,1].includes(result.meta?.changes))throw Error("db");
      return say(item.id,result.meta.changes===1?"已取消登记任务。":"没有可取消的等待任务。");
    }
    if(/^https:\/\/testflight\.apple\.com\//i.test(item.text))return say(item.id,"试验版尚未支持 TestFlight。");
    const app=target(item.text);
    if(!app)return say(item.id,HELP);
    const id="pilot_"+crypto.randomUUID().replaceAll("-","");
    const day=Math.floor(item.date/86400);
    const result=await db.prepare(SQL.insert).bind(id,owner,item.update,app.app,app.region,day,item.date,owner,day,owner).run();
    if(result.success!==true||![0,1].includes(result.meta?.changes))throw Error("db");
    if(result.meta.changes===1)return say(item.id,"已登记："+id+"\n等待可用计算环境；尚未开始下载或交付。");
    const previous=await db.prepare(SQL.existing).bind(owner,item.update).first();
    if(previous)return response(200);
    return say(item.id,"已达到每日登记或等待任务上限。未提交任务，不会升级付费。");
  }catch{
    // Free D1 quota, missing schema or an ambiguous write: do not fall back or dispatch.
    // Retrying the same Telegram update cannot create a duplicate because of its UNIQUE key.
    return response(503,{ok:false});
  }
}
export default {fetch(request,env){return handle(request,env);}};
