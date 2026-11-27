// One owner-private completion notification. Unknown sends are never repeated.
import {need} from "./runtime-auth.mjs";
export const NOTIFY_SCHEMA="CREATE TABLE IF NOT EXISTS runtime_notifications(job_id TEXT PRIMARY KEY,state TEXT NOT NULL,created_at INTEGER NOT NULL,message_id INTEGER)";
export async function notifyOwner(env,task,now,send){
 if(env.RUNTIME_TELEGRAM_ENABLED!=="1")return false;
 need(task.kind==="export"&&task.owner_id===env.RUNTIME_OWNER_ID&&task.file_id&&task.state==="link_ready"&&task.finished_at!==null,"runtime_notify_binding");
 const saved=await env.DB.prepare("SELECT state FROM runtime_notifications WHERE job_id=?").bind(task.job_id).first();
 if(saved)return saved.state==="sent";
 const intent=await env.DB.prepare("INSERT INTO runtime_notifications(job_id,state,created_at) VALUES(?,'intent',?) ON CONFLICT DO NOTHING").bind(task.job_id,now).run();
 need(intent.success===true,"runtime_notify_storage");if(intent.meta?.changes!==1)return false;
 let state="unknown",message=null;
 try{
  const token=env.TELEGRAM_BOT_TOKEN||"";
  need(/^[0-9]{5,20}:[A-Za-z0-9_-]{30,90}$/.test(token),"runtime_notify_configuration");
  const response=await send("https://api.telegram.org/bot"+token+"/sendMessage",{
   method:"POST",redirect:"manual",signal:AbortSignal.timeout(10000),headers:{"content-type":"application/json"},
   body:JSON.stringify({chat_id:Number(task.owner_id),
    text:"私有文件已核验\n文件："+task.filename+"\n大小："+task.plaintext_bytes+" 字节\n请登录自己的 Google 账号访问。",
    reply_markup:{inline_keyboard:[[{text:"打开私有文件",url:"https://drive.google.com/file/d/"+encodeURIComponent(task.file_id)+"/view"}]]},
    link_preview_options:{is_disabled:true}})
  });
  need(response.status===200,"runtime_notify_unconfirmed");
  const raw=await response.text();need(raw.length<=16384,"runtime_notify_limit");const result=JSON.parse(raw);
  need(result.ok===true&&result.result?.chat?.type==="private"&&String(result.result.chat.id)===task.owner_id&&
   Number.isSafeInteger(result.result.message_id)&&result.result.message_id>0,"runtime_notify_unconfirmed");
  state="sent";message=result.result.message_id;
 }catch{}
 const result=await env.DB.prepare("UPDATE runtime_notifications SET state=?,message_id=? WHERE job_id=? AND state='intent'").bind(state,message,task.job_id).run();
 need(result.success===true,"runtime_notify_storage");return state==="sent";
}
