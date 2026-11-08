const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const STAGES = new Set(['auth_retry','resolving_version','metadata','authenticating','downloading','auditing','decrypting','verifying','encrypting','artifact_ready','failed']);
const UPLOAD_REV = 'ea165f8d65b6e75b540449e92b4886f43607fa02';

function validateSnapshot(value, identity, now = Math.floor(Date.now()/1000)) {
  const keys = new Set(['schema','request_id','run_id','commit','stage','sequence','updated_at','stage_started','measurement']);
  if (!value || Array.isArray(value) || typeof value !== 'object' || Object.keys(value).some(k => !keys.has(k))) return null;
  if (value.schema !== 'ipa-stage-v2' || value.request_id !== identity.rid || value.run_id !== identity.run || value.commit !== identity.commit || !STAGES.has(value.stage)) return null;
  if (!Number.isSafeInteger(value.sequence) || value.sequence < 1 || value.sequence > 1000000 || !Number.isSafeInteger(value.updated_at) || value.updated_at > now+120 || value.updated_at < now-86400) return null;
  if (value.stage_started !== undefined && (!Number.isSafeInteger(value.stage_started) || value.stage_started > value.updated_at || value.stage_started < value.updated_at-86400)) return null;
  if (value.measurement !== undefined) {
    const m=value.measurement;
    if (value.stage !== 'downloading' || !m || Object.keys(m).sort().join(',') !== 'completed,total,unit' || m.unit !== 'bytes' || !Number.isSafeInteger(m.completed) || !Number.isSafeInteger(m.total) || m.completed < 0 || m.completed > m.total || m.total <= 0 || m.total > 2000000000) return null;
  }
  return JSON.parse(JSON.stringify(value));
}
function uploaderEnvironment(env, folder, name) {
  const result={};
  for (const key of ['PATH','HOME','LANG','RUNNER_TEMP','RUNNER_OS','RUNNER_ARCH','GITHUB_ACTIONS','GITHUB_WORKSPACE','GITHUB_REPOSITORY','GITHUB_REPOSITORY_ID','GITHUB_REPOSITORY_OWNER','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_JOB','GITHUB_SHA','GITHUB_REF','GITHUB_SERVER_URL','GITHUB_API_URL','ACTIONS_RUNTIME_TOKEN','ACTIONS_RUNTIME_URL','ACTIONS_RESULTS_URL','ACTIONS_CACHE_URL']) {
    if (env[key] !== undefined) result[key]=env[key];
  }
  result.INPUT_NAME=name;
  result.INPUT_PATH=path.join(folder,'progress.json');
  result['INPUT_RETENTION-DAYS']='1';
  result['INPUT_COMPRESSION-LEVEL']='0';
  result['INPUT_IF-NO-FILES-FOUND']='error';
  result.INPUT_OVERWRITE='false';
  result['INPUT_INCLUDE-HIDDEN-FILES']='false';
  for(const key of ['GITHUB_OUTPUT','GITHUB_ENV','GITHUB_STATE','GITHUB_STEP_SUMMARY']) result[key]=path.join(folder,key.toLowerCase());
  return result;
}
function launch(command,args,options) {
  return new Promise(resolve => {
    const child=spawn(command,args,options);
    let done=false;
    const finish=code => {if(!done){done=true;resolve(code)}};
    if(child.stdout)child.stdout.resume();
    if(child.stderr)child.stderr.resume();
    child.once('error',()=>finish(1));
    child.once('exit',code=>finish(code === null ? 1 : code));
  });
}
async function main() {
  const env=process.env;
  const identity={rid:env.DELIVERY_REQUEST_ID,run:env.GITHUB_RUN_ID,commit:env.GITHUB_SHA};
  if (!/^[a-f0-9]{32}$/.test(identity.rid||'') || !/^[0-9]+$/.test(identity.run||'') || !/^[a-f0-9]{40}$/.test(identity.commit||'') || env.GITHUB_REPOSITORY !== 'zwthys-cyber/ipa-decrypt-lab') throw new Error('invalid_progress_identity');
  const root=fs.mkdtempSync(path.join(env.RUNNER_TEMP||os.tmpdir(),'ipa-progress-'));
  fs.chmodSync(root,0o700);
  const input=path.join(root,'worker.json');
  const action=path.resolve(env.RUNNER_WORKSPACE,'../_actions/actions/upload-artifact',UPLOAD_REV,'dist/upload/index.js');
  let inFlight=null,lastSequence=0,lastStage=null,count=0,failures=0,lastUpload=-Infinity,disabled=!fs.existsSync(action);
  async function uploadLatest(force=false) {
    if(disabled||inFlight)return;
    let value;
    try {
      const stat=fs.statSync(input);
      if(!stat.isFile()||stat.size>2048)return;
      value=validateSnapshot(JSON.parse(fs.readFileSync(input,'utf8')),identity);
    } catch {return;}
    if(!value||value.sequence<=lastSequence)return;
    if(!force&&Date.now()-lastUpload<5000)return;
    // Bound tiny public snapshots, reserving capacity for stage transitions.
    if(count>=64&&value.stage===lastStage)return;
    if(count>=80)return;
    const folder=path.join(root,String(value.sequence));
    fs.mkdirSync(folder,{mode:0o700});
    fs.writeFileSync(path.join(folder,'progress.json'),JSON.stringify(value),{mode:0o600});
    const name=`progress-${identity.rid}-${String(value.sequence).padStart(6,'0')}`;
    lastUpload=Date.now();
    inFlight=launch(process.execPath,[action],{env:uploaderEnvironment(env,folder,name),stdio:['ignore','pipe','pipe'],timeout:30000});
    const status=await inFlight;
    inFlight=null;
    // An uncertain artifact upload is never repeated under the same name.
    lastSequence=value.sequence;lastStage=value.stage;count++;
    failures=status===0?0:failures+1;
    if(failures>=3)disabled=true;
    fs.rmSync(folder,{recursive:true,force:true});
  }
  const timer=setInterval(()=>{uploadLatest().catch(()=>{disabled=true})},1000);
  let worker;
  try {
    const probe=env.INPUT_PROBE === 'true';
    if(probe && (identity.rid !== 'f'.repeat(32) || ['APPLE_ID','APPLE_PASSWORD','FAIRPLAY_MODEL_B64','DELIVERY_AGE_IDENTITY','TELEGRAM_BOT_TOKEN'].some(key => env[key]))) throw new Error('invalid_probe_context');
    const command=probe ? 'ulimit -c 0\nexec python3 tools/progress_probe.py' : 'ulimit -c 0\nexec python3 tools/private_export.py --binary runtime/ApplePackageTool --engine runtime/offline-engine --crypt runtime/delivery-crypt';
    worker=spawn('bash',['-e','-c',command],{env:{...env,IPA_PROGRESS_FILE:input,PYTHONUNBUFFERED:'1'},stdio:['ignore','inherit','inherit']});
    const terminate=signal=>{if(worker&&!worker.killed)worker.kill(signal)};
    process.once('SIGTERM',()=>terminate('SIGTERM'));
    process.once('SIGINT',()=>terminate('SIGINT'));
    const status=await new Promise(resolve=>{worker.once('error',()=>resolve(1));worker.once('exit',code=>resolve(code===null?1:code))});
    clearInterval(timer);
    try {
      if(inFlight)await inFlight;
      await uploadLatest(true);
    } catch {disabled=true;}
    console.log(JSON.stringify({schema:'ipa-progress-feed-v1',snapshots:count,available:!disabled}));
    process.exitCode=status;
  } finally {
    clearInterval(timer);
    try {fs.rmSync(root,{recursive:true,force:true})} catch {}
  }
}
module.exports={validateSnapshot,uploaderEnvironment};
if(require.main===module)main().catch(()=>{console.log('{"schema":"ipa-progress-feed-v1","status":"worker_wrapper_failed"}');process.exitCode=1});
