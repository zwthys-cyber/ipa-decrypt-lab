// Owner-facing text only. Full task identifiers stay in buttons and durable records.
export const PAGE_SIZE=3;
export const HOME="IPA 下载助手\n\n发送 App Store 链接或 App ID，获取最新版。\n需要旧版本？发送 /versions 加应用链接。\nTestFlight：直接发送邀请链接。";
export const HELP="使用帮助\n\n最新版：直接发送应用链接或 App ID。\n历史版本：/versions 加链接，然后点选版本。\n指定版本：/version 加链接和版本号。\n\n国区请保留完整 /cn/ 链接。\n任务、领取和取消都可使用下方按钮。\n文件请用自己的 Google 账号打开。";
export const MENU={inline_keyboard:[
 [{text:"进行中",callback_data:"rt:list:a:0"},{text:"已完成",callback_data:"rt:list:c:0"}],
 [{text:"历史记录",callback_data:"rt:list:h:0"},{text:"使用帮助",callback_data:"rt:help"}]
]};
export function formatBytes(value){
 if(!Number.isSafeInteger(value)||value<0)return "";
 if(value>=1e9)return (value/1e9).toFixed(2)+" GB";
 if(value>=1e6)return (value/1e6).toFixed(1)+" MB";
 if(value>=1e3)return (value/1e3).toFixed(1)+" KB";
 return value+" B";
}
function clean(value,limit=70){return Array.from(String(value).replace(/[\u0000-\u001f\u007f]/g," ")).slice(0,limit).join("");}
export function fileInfo(filename){
 const raw=typeof filename==="string"?filename:"";
 const match=/^(.*)_([0-9]+(?:\.[0-9]+){0,4})\.ipa$/i.exec(raw);
 const name=(match?match[1]:raw.replace(/\.ipa$/i,"")).replace(/_Beta$/i,"（测试版）");
 return {name:clean(name),version:match?match[2]:""};
}
export function taskName(row){
 return fileInfo(row.display_filename||row.filename).name||
  (row.profile==="tf"?"TestFlight 应用":(row.profile==="cn"?"国区应用":"App Store 应用")+" "+row.target);
}
export function fileCard(filename,bytes){
 const info=fileInfo(filename),detail=[info.version&&"版本 "+info.version,formatBytes(bytes)].filter(Boolean).join(" · ");
 return "文件已准备好\n\n"+info.name+(detail?"\n"+detail:"")+"\n\n请用自己的 Google 账号打开。";
}
export function taskView(records,group,page,now){
 const titles={a:"进行中",c:"已完成",h:"历史记录"},rows=records.slice(0,PAGE_SIZE),buttons=[];
 const labels={waiting:"排队中",dispatch_intent:"正在提交",dispatch_unknown:"提交待核对",submitted:"等待工作机",
  running:"处理中",uploading:"上传中",link_ready:"等待确认",completed:"已完成",
  closed:"未完成，任务已结束",cancelled:"已取消",cancel_pending:"取消待确认",failed_pending:"结束待确认"};
 const lines=rows.map((row,i)=>{
  const ready=row.finished_at!==null&&!!row.file_id&&["link_ready","completed"].includes(row.state);
  const available=ready&&row.link_expires>now;
  const catalog=!!row.catalog_job,info=fileInfo(row.filename);
  const version=group==="a"?(row.version||"最新版"):info.version;
  const detail=[catalog?"历史版本查询":version,formatBytes(row.plaintext_bytes),
   catalog&&row.catalog_ready?"列表已就绪":ready?(available?"可领取":"领取期限已过"):labels[row.state]||"状态待核对"].filter(Boolean).join(" · ");
  const label=clean(taskName(row),16);
  if(available)buttons.push([{text:label,callback_data:"rt:get:"+row.job_id.slice(6)}]);
  else if(group==="a")buttons.push([{text:"取消 "+(i+1)+" · "+label,callback_data:"rt:cancel:"+row.job_id.slice(6)}]);
  return (i+1)+". "+taskName(row)+"\n"+detail;
 });
 const paging=[];
 if(page>0)paging.push({text:"上一页",callback_data:"rt:list:"+group+":"+(page-1)});
 if(records.length>PAGE_SIZE&&page<9999)paging.push({text:"下一页",callback_data:"rt:list:"+group+":"+(page+1)});
 if(paging.length)buttons.push(paging);
 buttons.push([{text:"进行中",callback_data:"rt:list:a:0"},{text:"已完成",callback_data:"rt:list:c:0"},{text:"历史",callback_data:"rt:list:h:0"}]);
 buttons.push([{text:"刷新",callback_data:"rt:list:"+group+":"+page},{text:"首页",callback_data:"rt:home"}]);
 return {text:titles[group]+(page?" · 第 "+(page+1)+" 页":"")+"\n\n"+(lines.join("\n\n")||"暂无任务。"),
  reply_markup:{inline_keyboard:buttons}};
}
