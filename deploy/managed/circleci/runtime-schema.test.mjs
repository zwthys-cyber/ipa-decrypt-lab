import test from "node:test";
import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import {schemaStatements} from "./runtime-api.mjs";
test("the exact live initializer executes as independent SQLite statements and preserves unknown dispatches",()=>{
 const script="import json,sqlite3,sys\n"+
 "db=sqlite3.connect(':memory:')\n"+
 "statements=json.load(sys.stdin)\n"+
 "for sql in statements:db.execute(sql)\n"+
 "db.execute(\"INSERT INTO runtime_jobs(job_id,owner_id,request_id,profile,kind,target,version,source_sha,state,created_at,deadline) VALUES('pilot_unknown','12345','opaque','default','export','123456','','source','dispatch_unknown',1,2)\")\n"+
 "for sql in statements:db.execute(sql)\n"+
 "assert db.execute(\"SELECT state FROM runtime_jobs WHERE job_id='pilot_unknown'\").fetchone()==('dispatch_unknown',)\n"+
 "assert db.execute(\"SELECT name FROM sqlite_master WHERE name='runtime_canary_windows'\").fetchone()\n"+
 "assert db.execute(\"SELECT name FROM sqlite_master WHERE name='runtime_notifications'\").fetchone()\n";
 const run=spawnSync("python3",["-c",script],{input:JSON.stringify(schemaStatements()),encoding:"utf8"});
 assert.equal(run.status,0,run.stderr);
});
