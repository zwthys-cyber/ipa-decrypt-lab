// Additive catalog subtype: old runtime_jobs CHECK and every existing job remain intact.
import {need} from "./runtime-auth.mjs";
import {requireEntry,exportRequest,admitExport} from "./runtime-tasks.mjs";
export const CATALOG_SCHEMA=[
 "CREATE TABLE IF NOT EXISTS runtime_catalog_specs(job_id TEXT PRIMARY KEY REFERENCES runtime_jobs(job_id),before_id TEXT NOT NULL,page_index INTEGER NOT NULL,result_json TEXT)",
 "CREATE TABLE IF NOT EXISTS runtime_catalog_requests(request_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,profile TEXT NOT NULL,target TEXT NOT NULL,before_id TEXT NOT NULL,parent_view TEXT NOT NULL,family_id TEXT NOT NULL,force_refresh INTEGER NOT NULL,job_id TEXT NOT NULL REFERENCES runtime_jobs(job_id),created_at INTEGER NOT NULL)",
 "CREATE TABLE IF NOT EXISTS runtime_catalog_views(view_id TEXT PRIMARY KEY,request_id TEXT NOT NULL UNIQUE,owner_id TEXT NOT NULL,job_id TEXT NOT NULL,parent_view TEXT NOT NULL,family_id TEXT NOT NULL,created_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,state TEXT NOT NULL,message_id INTEGER,selected_id TEXT,export_request_id TEXT)"
].join(";")+";";
const VID=/^[a-f0-9]{32}$/,EXT=/^[1-9][0-9]{5,19}$/;
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(value))),b=>b.toString(16).padStart(2,"0")).join("").slice(0,32);
export async function catalogTask(db,row){
 const spec=await db.prepare("SELECT * FROM runtime_catalog_specs WHERE job_id=?").bind(row.job_id).first();
 return spec?{...row,kind:"catalog",catalog:spec}:row;
}
async function entry(env){
 const seal=await requireEntry(env);need(!seal.canary,"runtime_catalog_canary_forbidden");return seal;
}
function input(value){
 need(value&&["default","cn"].includes(value.profile),"runtime_catalog_profile");
 exportRequest({request_id:value.request_id,profile:value.profile,target:value.target,version:""});
 need(typeof value.before==="string"&&(!value.before||EXT.test(value.before))&&
  typeof value.parent_view==="string"&&(!value.parent_view||VID.test(value.parent_view))&&
  typeof value.force==="boolean","runtime_catalog_request");
}
async function requestResult(db,id,owner){
 return db.prepare("SELECT * FROM runtime_catalog_requests WHERE request_id=? AND owner_id=?").bind(id,owner).first();
}
async function open(env,value,now){
 await entry(env);input(value);
 const {DB:db,RUNTIME_OWNER_ID:owner}=env;
 const legacy=await db.prepare("SELECT request_id FROM runtime_legacy_tasks WHERE owner_id=? AND request_id=?").bind(owner,value.request_id).first();
 need(!legacy,"runtime_historical_request_held");
 let saved=await requestResult(db,value.request_id,owner);
 const immutable=row=>need(row&&row.profile===value.profile&&row.target===value.target&&row.before_id===value.before&&
  row.parent_view===value.parent_view&&row.force_refresh===Number(value.force),"runtime_catalog_request_immutable");
 if(saved){immutable(saved);return saved;}
 let page=0,family="";
 if(value.parent_view){
  const parent=await db.prepare("SELECT v.*,s.result_json,s.page_index,j.profile,j.target FROM runtime_catalog_views v JOIN runtime_catalog_specs s ON s.job_id=v.job_id JOIN runtime_jobs j ON j.job_id=v.job_id WHERE v.view_id=? AND v.owner_id=?").bind(value.parent_view,owner).first();
  need(parent&&parent.state==="sent"&&parent.expires_at>now&&parent.selected_id===null&&
   parent.profile===value.profile&&parent.target===value.target,"runtime_catalog_view_expired");
  family=parent.family_id;
  if(value.before){
   need(JSON.parse(parent.result_json).next_before===value.before&&parent.page_index<19,"runtime_catalog_page_limit");
   page=parent.page_index+1;
  }
 }else need(!value.before&&!value.force,"runtime_catalog_request");
 let row;
 if(!value.force){
  row=await db.prepare("SELECT j.job_id FROM runtime_jobs j JOIN runtime_catalog_specs s ON s.job_id=j.job_id WHERE j.owner_id=? AND j.profile=? AND j.target=? AND s.before_id=? AND s.page_index=? AND s.result_json IS NOT NULL AND j.finished_at IS NOT NULL AND j.state IN ('link_ready','completed') AND j.finished_at>=? ORDER BY j.finished_at DESC,j.job_id LIMIT 1")
   .bind(owner,value.profile,value.target,value.before,page,now-86400).first();
 }
 if(!row){
  const id="pilot_"+await hash("managed-catalog\0"+owner+"\0"+value.request_id);
  const inserted=await db.batch([
   db.prepare("INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline) SELECT ?,?,?,?,'export',?,'',?,'waiting',?,? WHERE (SELECT count(*) FROM runtime_jobs j JOIN runtime_catalog_specs s ON s.job_id=j.job_id WHERE j.owner_id=? AND j.created_at>=? AND j.created_at<?)<20 AND NOT EXISTS(SELECT 1 FROM runtime_jobs j JOIN runtime_catalog_specs s ON s.job_id=j.job_id WHERE j.owner_id=? AND j.profile=? AND j.created_at>?) AND (SELECT count(*) FROM runtime_jobs WHERE owner_id=? AND state='waiting')<30 ON CONFLICT DO NOTHING")
    .bind(id,owner,value.request_id,value.profile,value.target,env.RUNTIME_SOURCE_SHA,now,now+3600,owner,Math.floor(now/86400)*86400,Math.floor(now/86400)*86400+86400,owner,value.profile,now-(value.before?5:60),owner),
   db.prepare("INSERT INTO runtime_catalog_specs(job_id,before_id,page_index) SELECT job_id,?,? FROM runtime_jobs WHERE job_id=? AND owner_id=? AND request_id=? AND profile=? AND target=? AND source_sha=? AND state='waiting' ON CONFLICT DO NOTHING")
    .bind(value.before,page,id,owner,value.request_id,value.profile,value.target,env.RUNTIME_SOURCE_SHA)
  ]);
  need(inserted.every(r=>r.success===true),"runtime_catalog_storage");
  row=await db.prepare("SELECT j.*,s.before_id,s.page_index FROM runtime_jobs j JOIN runtime_catalog_specs s ON s.job_id=j.job_id WHERE j.job_id=? AND j.owner_id=?").bind(id,owner).first();
  need(row,"runtime_catalog_rate_limit");
  need(row.request_id===value.request_id&&row.profile===value.profile&&row.target===value.target&&
   row.before_id===value.before&&row.page_index===page&&row.source_sha===env.RUNTIME_SOURCE_SHA,"runtime_catalog_request_immutable");
 }
 const stored=await db.prepare("INSERT INTO runtime_catalog_requests(request_id,owner_id,profile,target,before_id,parent_view,family_id,force_refresh,job_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING")
  .bind(value.request_id,owner,value.profile,value.target,value.before,value.parent_view,family,Number(value.force),row.job_id,now).run();
 need(stored.success===true,"runtime_catalog_storage");
 saved=await requestResult(db,value.request_id,owner);immutable(saved);return saved;
}
export function verifyCatalog(task,value){
 const fields="account_profile,app_id,before,job_id,next_before,request_id,rows,run_id,schema,source_sha,total,worker_job_id";
 need(task.kind==="catalog"&&value&&Object.keys(value).sort().join(",")===fields&&
  value.schema==="circleci-version-catalog-v1"&&value.job_id===task.job_id&&value.request_id===task.request_id&&
  value.run_id===task.run_id&&value.worker_job_id===task.worker_job_id&&value.source_sha===task.source_sha&&
  value.account_profile===task.profile&&value.app_id===task.target&&value.before===task.catalog.before_id&&
  Number.isSafeInteger(value.total)&&value.total>=0&&value.total<=10000&&Array.isArray(value.rows)&&
  value.rows.length<=10&&value.rows.length<=value.total&&typeof value.next_before==="string"&&
  (!value.next_before||EXT.test(value.next_before)),"runtime_catalog_proof");
 let previous=value.before?BigInt(value.before):null;
 for(const row of value.rows){
  need(row&&Object.keys(row).sort().join(",")==="date,id,version"&&typeof row.id==="string"&&EXT.test(row.id)&&
   typeof row.version==="string"&&/^[0-9]{1,5}(?:\.[0-9]{1,5}){0,4}$/.test(row.version)&&
   typeof row.date==="string"&&/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(row.date),"runtime_catalog_proof");
  const date=new Date(row.date+"T00:00:00Z");
  need(!Number.isNaN(date.getTime())&&date.toISOString().slice(0,10)===row.date,"runtime_catalog_proof");
  const id=BigInt(row.id);
  need((previous===null||id<previous)&&(!value.next_before||id>=BigInt(value.next_before)),"runtime_catalog_cursor");
  previous=id;
 }
 need((!value.before||!value.next_before||BigInt(value.next_before)<BigInt(value.before))&&
  (value.before||value.rows.length||value.next_before),"runtime_catalog_cursor");
 return JSON.stringify(Object.fromEntries(Object.keys(value).sort().map(key=>[key,key==="rows"?value.rows.map(row=>({date:row.date,id:row.id,version:row.version})):value[key]])));
}
export async function saveCatalog(env,task,value,now){
 await entry(env);const encoded=verifyCatalog(task,value);
 const saved=await env.DB.batch([
  env.DB.prepare("UPDATE runtime_catalog_specs SET result_json=COALESCE(result_json,?) WHERE job_id=? AND (result_json IS NULL OR result_json=?) AND EXISTS(SELECT 1 FROM runtime_jobs WHERE job_id=? AND state IN ('running','link_ready') AND deadline>?)").bind(encoded,task.job_id,encoded,task.job_id,now),
  env.DB.prepare("UPDATE runtime_jobs SET state='link_ready',finished_at=COALESCE(finished_at,?) WHERE job_id=? AND worker_job_id=? AND state IN ('running','link_ready') AND EXISTS(SELECT 1 FROM runtime_catalog_specs WHERE job_id=? AND result_json=?)").bind(now,task.job_id,task.worker_job_id,task.job_id,encoded)
 ]);
 need(saved.every(x=>x.success===true)&&saved[0].meta?.changes===1&&saved[1].meta?.changes===1,"runtime_catalog_proof_immutable");
}
export async function notifyCatalog(env,request,now,send){
 const db=env.DB;
 const job=await db.prepare("SELECT j.*,s.result_json,s.page_index FROM runtime_jobs j JOIN runtime_catalog_specs s ON s.job_id=j.job_id WHERE j.job_id=? AND j.owner_id=?").bind(request.job_id,env.RUNTIME_OWNER_ID).first();
 if(!job?.result_json||job.finished_at===null||!["completed","link_ready"].includes(job.state))return false;
 const id=await hash("catalog-view\0"+env.RUNTIME_OWNER_ID+"\0"+request.request_id);
 let family=request.family_id||id;
 if(request.parent_view){
  const parent=await db.prepare("SELECT family_id,selected_id FROM runtime_catalog_views WHERE view_id=? AND owner_id=?").bind(request.parent_view,env.RUNTIME_OWNER_ID).first();
  need(parent,"runtime_catalog_view_expired");if(parent.selected_id!==null)return false;family=parent.family_id;
 }
 let view=await db.prepare("SELECT * FROM runtime_catalog_views WHERE view_id=? AND owner_id=?").bind(id,env.RUNTIME_OWNER_ID).first();
 if(view)return view.state==="sent";
 need(env.RUNTIME_TELEGRAM_ENABLED==="1","runtime_catalog_notify_disabled");
 const created=await db.prepare("INSERT INTO runtime_catalog_views(view_id,request_id,owner_id,job_id,parent_view,family_id,created_at,expires_at,state) SELECT ?,?,?,?,?,?,?,?,'intent' WHERE NOT EXISTS(SELECT 1 FROM runtime_catalog_views WHERE family_id=? AND owner_id=? AND selected_id IS NOT NULL) ON CONFLICT DO NOTHING")
  .bind(id,request.request_id,env.RUNTIME_OWNER_ID,job.job_id,request.parent_view,family,now,now+21600,family,env.RUNTIME_OWNER_ID).run();
 need(created.success===true,"runtime_catalog_storage");if(created.meta?.changes!==1)return false;
 const result=JSON.parse(job.result_json),buttons=result.rows.map(row=>[{text:row.version+" · "+row.date,callback_data:"cv:"+id+":v:"+row.id}]);
 const navigation=[];
 if(request.parent_view&&job.page_index>0)navigation.push({text:"上一页",callback_data:"cv:"+id+":p"});
 if(result.next_before&&job.page_index<19)navigation.push({text:"下一页",callback_data:"cv:"+id+":n"});
 if(navigation.length)buttons.push(navigation);
 buttons.push([{text:"刷新",callback_data:"cv:"+id+":r"}]);
 let state="unknown",message=null;
 try{
  need(/^[0-9]{5,20}:[A-Za-z0-9_-]{30,90}$/.test(env.TELEGRAM_BOT_TOKEN||""),"runtime_catalog_notify_configuration");
  const response=await send("https://api.telegram.org/bot"+env.TELEGRAM_BOT_TOKEN+"/sendMessage",{
   method:"POST",redirect:"manual",signal:AbortSignal.timeout(10000),headers:{"content-type":"application/json"},
   body:JSON.stringify({chat_id:Number(env.RUNTIME_OWNER_ID),text:(job.profile==="cn"?"国区":"默认账号")+"历史版本 · "+job.target+"\n第 "+(job.page_index+1)+" 页 · 共 "+result.total+" 个版本\n选择一个版本后，本列表将关闭。",
    reply_markup:{inline_keyboard:buttons}})
  });
  need(response.status===200,"runtime_catalog_notify_unconfirmed");
  const raw=await response.text();need(raw.length<=16384,"runtime_catalog_notify_unconfirmed");
  const reply=JSON.parse(raw);
  need(reply.ok===true&&reply.result?.chat?.type==="private"&&String(reply.result.chat.id)===env.RUNTIME_OWNER_ID&&
   Number.isSafeInteger(reply.result.message_id)&&reply.result.message_id>0,"runtime_catalog_notify_unconfirmed");
  state="sent";message=reply.result.message_id;
 }catch{}
 const stored=await db.prepare("UPDATE runtime_catalog_views SET state=?,message_id=? WHERE view_id=? AND state='intent'").bind(state,message,id).run();
 need(stored.success===true,"runtime_catalog_storage");return state==="sent";
}
export async function openCatalog(env,value,now,send){
 const record=await open(env,{...value,before:"",parent_view:"",force:false},now);
 return {ok:true,job_id:record.job_id,menu_notified:await notifyCatalog(env,record,now,send)};
}
export async function completeCatalogNotices(env,job,now,send){
 const records=await env.DB.prepare("SELECT * FROM runtime_catalog_requests WHERE job_id=? AND owner_id=? ORDER BY created_at LIMIT 20").bind(job.job_id,env.RUNTIME_OWNER_ID).all();
 let confirmed=false;
 for(const record of records.results||[])confirmed=(await notifyCatalog(env,record,now,send))||confirmed;
 return confirmed;
}
export async function catalogAction(env,value,now,send){
 await entry(env);
 need(VID.test(value.view_id||"")&&Number.isSafeInteger(value.message_id)&&value.message_id>0&&
  ["v","p","n","r"].includes(value.action)&&typeof value.version_id==="string","runtime_catalog_callback");
 const view=await env.DB.prepare("SELECT v.*,j.profile,j.target,s.result_json,s.page_index FROM runtime_catalog_views v JOIN runtime_jobs j ON j.job_id=v.job_id JOIN runtime_catalog_specs s ON s.job_id=v.job_id WHERE v.view_id=? AND v.owner_id=?").bind(value.view_id,env.RUNTIME_OWNER_ID).first();
 need(view&&view.state==="sent"&&view.message_id===value.message_id&&view.expires_at>now,"runtime_catalog_view_expired");
 const prefix=view.profile==="cn"?"cn_":"";
 exportRequest({request_id:value.request_id,profile:view.profile,target:view.target,version:""});
 const result=JSON.parse(view.result_json);
 if(value.action==="v"){
  need(EXT.test(value.version_id)&&result.rows.some(row=>row.id===value.version_id),"runtime_catalog_selection");
  const request_id=prefix+await hash("catalog-selection\0"+env.RUNTIME_OWNER_ID+"\0"+view.family_id);
  const claim=await env.DB.prepare("UPDATE runtime_catalog_views SET selected_id=?,export_request_id=? WHERE family_id=? AND owner_id=? AND NOT EXISTS(SELECT 1 FROM runtime_catalog_views WHERE family_id=? AND owner_id=? AND selected_id IS NOT NULL AND (selected_id<>? OR export_request_id<>?))")
   .bind(value.version_id,request_id,view.family_id,env.RUNTIME_OWNER_ID,view.family_id,env.RUNTIME_OWNER_ID,value.version_id,request_id).run();
  need(claim.success===true&&claim.meta?.changes>=1,"runtime_catalog_already_selected");
  const job=await admitExport(env,{request_id,profile:view.profile,target:view.target,version:value.version_id},now);
  return {ok:true,job_id:job.job_id,selected:true};
 }
 need(value.version_id===""&&view.selected_id===null,"runtime_catalog_already_selected");
 let record;
 if(value.action==="p"){
  need(view.page_index>0&&VID.test(view.parent_view||""),"runtime_catalog_page_limit");
  const parent=await env.DB.prepare("SELECT * FROM runtime_catalog_views WHERE view_id=? AND owner_id=?").bind(view.parent_view,env.RUNTIME_OWNER_ID).first();
  need(parent&&parent.expires_at>now&&parent.selected_id===null,"runtime_catalog_view_expired");
  // Reopen only an acknowledged, owner-bound previous page. No account query.
  const source=await requestResult(env.DB,parent.request_id,env.RUNTIME_OWNER_ID);
  const stored=await env.DB.prepare("INSERT INTO runtime_catalog_requests(request_id,owner_id,profile,target,before_id,parent_view,family_id,force_refresh,job_id,created_at) VALUES(?,?,?,?,?,?,?,0,?,?) ON CONFLICT DO NOTHING")
   .bind(value.request_id,env.RUNTIME_OWNER_ID,view.profile,view.target,source.before_id,parent.parent_view,view.family_id,parent.job_id,now).run();
  need(stored.success===true,"runtime_catalog_storage");
  record=await requestResult(env.DB,value.request_id,env.RUNTIME_OWNER_ID);
  need(record?.job_id===parent.job_id&&record.parent_view===parent.parent_view&&record.family_id===view.family_id,"runtime_catalog_request_immutable");
 }else{
  if(value.action==="n")need(result.next_before,"runtime_catalog_page_limit");
  record=await open(env,{request_id:value.request_id,profile:view.profile,target:view.target,
   before:value.action==="n"?result.next_before:"",parent_view:view.view_id,force:value.action==="r"},now);
 }
 return {ok:true,job_id:record.job_id,menu_notified:await notifyCatalog(env,record,now,send)};
}
