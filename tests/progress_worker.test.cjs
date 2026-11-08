const {test}=require('node:test');
const assert=require('node:assert/strict');
const {validateSnapshot,uploaderEnvironment}=require('../.github/actions/export-progress/index.js');
const identity={rid:'a'.repeat(32),run:'12',commit:'b'.repeat(40)};
const fixture=()=>({schema:'ipa-stage-v2',request_id:identity.rid,run_id:identity.run,commit:identity.commit,stage:'downloading',sequence:1,updated_at:1000,measurement:{unit:'bytes',completed:5,total:10}});
test('only identity-bound fixed data and real counters may enter public snapshots',()=>{
 assert.ok(validateSnapshot(fixture(),identity,1000));
 for(const [key,value] of [['password','SECRET'],['request_id','f'.repeat(32)],['run_id','13'],['stage','SECRET'],['sequence',true],['updated_at',-100000]]) {
  const input={...fixture(),[key]:value};
  assert.equal(validateSnapshot(input,identity,1000),null);
 }
 for(const measurement of [{unit:'bytes',completed:true,total:10},{unit:'bytes',completed:11,total:10},{unit:'bytes',completed:1,total:2000000001},{unit:'bytes',completed:1,total:10,url:'SECRET'}])assert.equal(validateSnapshot({...fixture(),measurement},identity,1000),null);
});
test('artifact uploader inherits runtime authorization but no account or Telegram secrets',()=>{
 const env=uploaderEnvironment({PATH:'/bin',ACTIONS_RUNTIME_TOKEN:'runtime',APPLE_PASSWORD:'private-apple',APPLE_ID:'private-id',GH_TOKEN:'broad',GITHUB_TOKEN:'broad2',DELIVERY_AGE_IDENTITY:'private-key',FAIRPLAY_MODEL_B64:'private-model',TELEGRAM_BOT_TOKEN:'private-bot'},'/tmp/progress','progress-name');
 assert.equal(env.ACTIONS_RUNTIME_TOKEN,'runtime');
 assert.equal(env['INPUT_RETENTION-DAYS'],'1');
 assert.equal(env['INPUT_INCLUDE-HIDDEN-FILES'],'false');
 const encoded=JSON.stringify(env);
 for(const value of ['private-apple','private-id','broad','private-key','private-model','private-bot'])assert.equal(encoded.includes(value),false);
 assert.ok(env.GITHUB_OUTPUT.startsWith('/tmp/progress/'));
});
