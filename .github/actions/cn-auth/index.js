const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {uploaderEnvironment}=require('../export-progress/index.js');
const REV='cf430e030ddbb5b0abf93d22962f4752f3646cd9';
function validateRequest(v,run,commit,now=Math.floor(Date.now()/1000)) {
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join(',')!=='auth_run,commit,expires,nonce,schema')return null;
  if(v.schema!=='cn-live-request-v1'||v.auth_run!==run||v.commit!==commit||!/^[a-f0-9]{32}$/.test(v.nonce||''))return null;
  if(!Number.isSafeInteger(v.expires)||v.expires<=now||v.expires>now+300)return null;
  return {...v};
}
function upload(action,env) {
  return new Promise(resolve=>{
    const p=spawn(process.execPath,[action],{env,stdio:'ignore',timeout:30000});
    p.once('error',()=>resolve(1));p.once('exit',code=>resolve(code===null?1:code));
  });
}
async function main() {
  const env=process.env;
  if(env.GITHUB_REPOSITORY!=='zwthys-cyber/ipa-decrypt-lab'||!/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID||'')||!/^[a-f0-9]{40}$/.test(env.GITHUB_SHA||''))throw Error();
  const root=fs.mkdtempSync(path.join(env.RUNNER_TEMP||os.tmpdir(),'cn-auth-public-'));fs.chmodSync(root,0o700);
  const input=path.join(root,'waiting.json');const folder=path.join(root,'upload');fs.mkdirSync(folder,{mode:0o700});
  const action=path.resolve(env.RUNNER_WORKSPACE,'../_actions/actions/upload-artifact',REV,'dist/upload/index.js');
  if(!fs.existsSync(action))throw Error();
  let sent=false,inFlight=null,worker;
  async function publish() {
    if(sent||inFlight)return;
    let value;
    try {if(fs.statSync(input).size>2048)return;value=validateRequest(JSON.parse(fs.readFileSync(input,'utf8')),env.GITHUB_RUN_ID,env.GITHUB_SHA)}catch{return}
    if(!value)return;
    sent=true;
    fs.writeFileSync(path.join(folder,'request.json'),JSON.stringify(value),{mode:0o600});
    const uploadEnv=uploaderEnvironment(env,folder,`cn-auth-request-${value.auth_run}-${value.nonce}`);
    uploadEnv.INPUT_PATH=path.join(folder,'request.json');
    for(const key of ['GITHUB_OUTPUT','GITHUB_ENV','GITHUB_STATE','GITHUB_STEP_SUMMARY'])fs.writeFileSync(uploadEnv[key],'',{mode:0o600});
    inFlight=upload(action,uploadEnv);
    const code=await inFlight;
    if(code!==0){console.log('{"schema":"cn-auth-request-v1","status":"request_publication_failed"}');if(worker&&!worker.killed)worker.kill('SIGTERM')}
  }
  const timer=setInterval(()=>{publish().catch(()=>{if(worker)worker.kill('SIGTERM')})},1000);
  try {
    const commands={auth:'exec python3 .github/ops/cn_live_auth.py --binary cn-runtime/ApplePackageTool --crypt cn-runtime/delivery-crypt --sealer cn-runtime/cn-session-seal',
      model_trial:'exec python3 .github/ops/cn_model.py --runtime cn-runtime --mode trial',
      model_replay:'exec python3 .github/ops/cn_model.py --runtime cn-runtime --mode replay',
      arm_model_trial:'exec python3 .github/ops/cn_arm_model.py --mode trial',
      arm_model_replay:'exec python3 .github/ops/cn_arm_model.py --mode replay',
      relay_probe:'exec python3 .github/ops/cn_live_relay_probe.py --crypt cn-relay-crypto/delivery-crypt'};
    const role=env.CN_LIVE_TASK||'auth';if(!Object.hasOwn(commands,role))throw Error();
    worker=spawn('bash',['-e','-c','ulimit -c 0\n'+commands[role]],{
      env:{...env,CN_HANDSHAKE_FILE:input,PYTHONUNBUFFERED:'1'},stdio:['ignore','inherit','inherit']});
    for(const signal of ['SIGTERM','SIGINT'])process.once(signal,()=>{if(worker&&!worker.killed)worker.kill(signal)});
    const code=await new Promise(resolve=>{worker.once('error',()=>resolve(2));worker.once('exit',code=>resolve(code===null?2:code))});
    clearInterval(timer);if(inFlight)await inFlight;process.exitCode=code;
  }finally{clearInterval(timer);fs.rmSync(root,{recursive:true,force:true})}
}
module.exports={validateRequest,uploaderEnvironment};
if(require.main===module)main().catch(()=>{console.log('{"schema":"ipa-cn-auth-live-v1","status":"live_wrapper_failed"}');process.exitCode=2});
