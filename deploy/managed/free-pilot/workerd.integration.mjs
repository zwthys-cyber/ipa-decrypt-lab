// Run only on the CI runner with synthetic bindings; no remote D1, real bot or Apple account.
import test from "node:test";
import assert from "node:assert/strict";
import {readFile,mkdtemp,mkdir,copyFile,writeFile,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {Miniflare} from "miniflare";
const secret="T".repeat(48),owner=12345;
const stamp=Math.floor(Date.now()/1000);
const schema=(await Promise.all(["0001_pilot.sql","0002_links.sql","0003_links_10gb.sql","0004_retired_links.sql"].map(name=>readFile(new URL("./migrations/"+name,import.meta.url),"utf8")))).join("\n");
const config=JSON.parse(await readFile(new URL("./wrangler.example.json",import.meta.url),"utf8"));
function send(mf,id,text="123456",uid=owner,token=secret){
  return mf.dispatchFetch("http://localhost/telegram",{method:"POST",
    headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":token},
    body:JSON.stringify({update_id:id,message:{date:stamp,chat:{id:uid,type:"private"},from:{id:uid,is_bot:false},text}})});
}
test("workerd D1: isolated auth, concurrent quota, deduplication, cancellation and restart",{timeout:60000},async()=>{
  const folder=await mkdtemp(join(tmpdir(),"ipazake-d1-"));
  const make=()=>new Miniflare({modules:true,modulesRoot:fileURLToPath(new URL("../",import.meta.url)),scriptPath:fileURLToPath(new URL("./worker.mjs",import.meta.url)),
    compatibilityDate:config.compatibility_date,cf:false,host:"127.0.0.1",port:0,
    d1Databases:{DB:"11111111-1111-4111-8111-111111111111"},d1Persist:folder,
    bindings:{PILOT_ENABLED:"1",PILOT_OWNER_ID:String(owner),TELEGRAM_WEBHOOK_SECRET:secret}});
  let mf;
  try{
    mf=make();
    let db=await mf.getD1Database("DB");
    const statements=schema.replace(/^--.*$/gm,"").split(";").map(s=>s.trim()).filter(Boolean);
    const migration=await db.batch(statements.map(s=>db.prepare(s)));
    assert.ok(migration.every(x=>x.success));
    assert.equal((await send(mf,1,"123456",owner,"X".repeat(48))).status,401);
    assert.deepEqual(await (await send(mf,2,"123456",54321)).json(),{ok:true});
    assert.equal((await db.prepare("SELECT count(*) AS n FROM pilot_jobs").first()).n,0);
    const requests=await Promise.all([10,10,11,12,13,14,15].map(id=>send(mf,id)));
    for(const r of requests)assert.equal(r.status,200);
    await Promise.all(requests.map(r=>r.text()));
    let count=await db.prepare("SELECT count(*) AS n,count(DISTINCT update_id) AS u FROM pilot_jobs").first();
    assert.deepEqual(count,{n:3,u:3});
    const first=await db.prepare("SELECT job_id,update_id FROM pilot_jobs LIMIT 1").first();
    assert.match((await (await send(mf,20,"/cancel "+first.job_id)).json()).text,/已取消/);
    assert.match((await (await send(mf,21)).json()).text,/上限/);
    assert.match((await (await send(mf,22,"/status")).json()).text,/已取消/);
    await mf.dispose();mf=undefined;
    mf=make();db=await mf.getD1Database("DB");
    assert.equal((await db.prepare("SELECT count(*) AS n FROM pilot_jobs").first()).n,3);
    assert.equal((await db.prepare("SELECT state FROM pilot_jobs WHERE job_id=?").bind(first.job_id).first()).state,"cancelled");
    assert.deepEqual(await (await send(mf,first.update_id)).json(),{ok:true});
    assert.match((await (await send(mf,23)).json()).text,/上限/);
    // D1 failure stops the pilot; it does not generate a successful job or invoke external compute.
    await db.prepare("DROP TABLE pilot_jobs").run();
    assert.equal((await send(mf,24)).status,503);
  }finally{if(mf)await mf.dispose();await rm(folder,{recursive:true,force:true});}
});

test("workerd D1: 10 GB migration preserves old metadata and exact large integers",{timeout:60000},async()=>{
  const mf=new Miniflare({modules:true,modulesRoot:fileURLToPath(new URL("../",import.meta.url)),scriptPath:fileURLToPath(new URL("./worker.mjs",import.meta.url)),
    compatibilityDate:config.compatibility_date,cf:false,host:"127.0.0.1",port:0,
    d1Databases:{DB:"22222222-2222-4222-8222-222222222222"}});
  try{
    const db=await mf.getD1Database("DB");
    async function migrate(name){
      const raw=await readFile(new URL("./migrations/"+name,import.meta.url),"utf8");
      const statements=raw.replace(/^--.*$/gm,"").split(";").map(s=>s.trim()).filter(Boolean);
      const result=await db.batch(statements.map(s=>db.prepare(s)));
      assert.ok(result.every(x=>x.success));
    }
    await migrate("0001_pilot.sql");await migrate("0002_links.sql");
    const jobs=[1,2,3,4].map(n=>"pilot_"+String(n).padStart(32,"0"));
    for(let i=0;i<jobs.length;i++){
      await db.prepare("INSERT INTO pilot_jobs VALUES(?,?,?,?,?,?,?,?)")
        .bind(jobs[i],String(owner),i,"123456","default",1,86400,"waiting_for_runtime").run();
    }
    const sql="INSERT INTO pilot_links VALUES(?,?,?,?,?,?,?)";
    const row=(job,file,bytes)=>[job,String(owner),file,"Synthetic.zip",bytes,"a".repeat(64),stamp+7200];
    await db.prepare(sql).bind(...row(jobs[0],"syntheticOriginal123",2000000000)).run();
    await migrate("0003_links_10gb.sql");
    const old=await db.prepare("SELECT * FROM pilot_links WHERE job_id=?").bind(jobs[0]).first();
    assert.equal(old.bytes,2000000000);assert.equal(old.file_id,"syntheticOriginal123");
    assert.equal(old.expires_at,stamp+7200);
    await db.prepare(sql).bind(...row(jobs[1],"syntheticLarge123",4294967297)).run();
    await db.prepare(sql).bind(...row(jobs[2],"syntheticMax123",10000000000)).run();
    assert.equal((await db.prepare("SELECT bytes FROM pilot_links WHERE job_id=?").bind(jobs[1]).first()).bytes,4294967297);
    assert.equal((await db.prepare("SELECT bytes FROM pilot_links WHERE job_id=?").bind(jobs[2]).first()).bytes,10000000000);
    await assert.rejects(db.prepare(sql).bind(...row(jobs[3],"syntheticOver123",10000000001)).run());
    assert.equal((await db.prepare("SELECT count(*) AS n FROM pilot_links").first()).n,3);
    await migrate("0004_retired_links.sql");
    const receipt=row(jobs[2],"syntheticMax123",10000000000);
    const {LINK_SQL}=await import("./private-link.mjs");
    const at=stamp+7200+86400;
    const params=[jobs[2],String(owner),"syntheticMax123","Synthetic.zip",10000000000,"a".repeat(64)];
    assert.equal((await db.prepare(LINK_SQL.retire).bind(at,...params,stamp+7199).run()).meta.changes,0);
    assert.equal((await db.prepare(LINK_SQL.retire).bind(at,...params,stamp+7200).run()).meta.changes,1);
    assert.equal((await db.prepare("SELECT retired_at FROM pilot_links WHERE job_id=?").bind(jobs[2]).first()).retired_at,at);
  }finally{await mf.dispose();}
});

test("workerd D1: registered Drive link is returned only in the owner's private /get reply",{timeout:60000},async()=>{
  const folder=await mkdtemp(join(tmpdir(),"ipazake-link-d1-"));
  const fileId="syntheticFileId123456";
  const issuer="I".repeat(48);
  const fixture={file_id:fileId,filename:"Synthetic.txt",bytes:1024,sha256:"a".repeat(64)};
  const entry=join(folder,"test-entry.mjs");
  let mf;
  try{
    await mkdir(join(folder,"free-pilot"));await mkdir(join(folder,"circleci"));
    await Promise.all(["worker.mjs","private-link.mjs","drive-auth.mjs"].map(name=>
      copyFile(new URL("./"+name,import.meta.url),join(folder,"free-pilot",name))));
    await Promise.all(["control.mjs","control-schema.mjs","dispatch.mjs","oidc.mjs"].map(name=>
      copyFile(new URL("../circleci/"+name,import.meta.url),join(folder,"circleci",name))));
    await writeFile(entry,`
      import {handle} from "./free-pilot/worker.mjs";
      const fileId=${JSON.stringify(fileId)};
      const record=${JSON.stringify(fixture)};
      async function drive(url,init){
        const u=new URL(url);
        if(u.origin!=="https://www.googleapis.com"||init.method!=="GET"||init.redirect!=="manual")
          throw Error("unexpected provider request");
        if(u.pathname==="/drive/v3/files/"+fileId)
          return Response.json({id:fileId,name:record.filename,size:String(record.bytes),sha256Checksum:record.sha256,trashed:false,ownedByMe:true,mimeType:"text/plain"});
        if(u.pathname==="/drive/v3/files/"+fileId+"/permissions")
          return Response.json({permissions:[{type:"user",role:"owner",emailAddress:"owner@example.invalid",deleted:false}]});
        throw Error("unexpected provider request");
      }
      export default {fetch(request,env){
        const now=${stamp}+(request.headers.get("x-synthetic-expired")==="1"?7200:0);
        return handle(request,env,now,drive);
      }};
    `);
    mf=new Miniflare({modules:true,modulesRoot:folder,scriptPath:entry,compatibilityDate:config.compatibility_date,
      cf:false,host:"127.0.0.1",port:0,d1Databases:{DB:"33333333-3333-4333-8333-333333333333"},
      bindings:{PILOT_ENABLED:"1",PILOT_LINK_ENABLED:"1",PILOT_OWNER_ID:String(owner),
        TELEGRAM_WEBHOOK_SECRET:secret,PILOT_LINK_ISSUER_TOKEN:issuer,
        PILOT_DRIVE_ACCESS_TOKEN:"synthetic-test-only-access-token",PILOT_DRIVE_RECIPIENT_EMAIL:"owner@example.invalid"}});
    const db=await mf.getD1Database("DB");
    const statements=schema.replace(/^--.*$/gm,"").split(";").map(s=>s.trim()).filter(Boolean);
    assert.ok((await db.batch(statements.map(s=>db.prepare(s)))).every(x=>x.success));

    assert.equal((await send(mf,101)).status,200);
    const {job_id}=await db.prepare("SELECT job_id FROM pilot_jobs").first();
    const register=token=>mf.dispatchFetch("http://localhost/v1/link-register",{method:"POST",
      headers:{"content-type":"application/json",authorization:"Bearer "+token},
      body:JSON.stringify({...fixture,job_id})});
    assert.equal((await register(secret)).status,401);
    assert.equal((await register(issuer)).status,201);
    assert.equal((await register(issuer)).status,409);

    assert.deepEqual(await (await send(mf,102,"/get "+job_id,54321)).json(),{ok:true});
    const reply=await (await send(mf,103,"/get "+job_id)).json();
    assert.equal(reply.method,"sendMessage");
    assert.equal(reply.chat_id,owner);
    assert.equal(reply.reply_markup.inline_keyboard[0][0].url,"https://drive.google.com/file/d/"+fileId+"/view");
    assert.ok(reply.text.includes(fixture.sha256));
    assert.equal(reply.link_preview_options.is_disabled,true);

    const expired=await mf.dispatchFetch("http://localhost/telegram",{method:"POST",
      headers:{"content-type":"application/json","x-telegram-bot-api-secret-token":secret,"x-synthetic-expired":"1"},
      body:JSON.stringify({update_id:104,message:{date:stamp,chat:{id:owner,type:"private"},from:{id:owner,is_bot:false},text:"/get "+job_id}})});
    assert.match((await expired.json()).text,/领取期限已过/);
    assert.match((await (await send(mf,105,"/cancel "+job_id)).json()).text,/已取消/);
    assert.equal((await (await send(mf,106,"/get "+job_id)).json()).reply_markup,undefined);
  }finally{if(mf)await mf.dispose();await rm(folder,{recursive:true,force:true});}
});
