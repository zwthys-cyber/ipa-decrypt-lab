const test=require('node:test');const assert=require('node:assert/strict');
const {validateRequest,uploaderEnvironment}=require('../actions/cn-auth/index.js');
test('handshake accepts only source/run/nonce with bounded live expiry',()=>{
 const value={schema:'cn-live-request-v1',auth_run:'12',commit:'a'.repeat(40),nonce:'b'.repeat(32),expires:1100};
 assert.ok(validateRequest(value,'12','a'.repeat(40),1000));
 for(const bad of [{...value,password:'PRIVATE'},{...value,expires:999},{...value,expires:1500},{...value,auth_run:'13'},{...value,nonce:'bad'}])assert.equal(validateRequest(bad,'12','a'.repeat(40),1000),null);
});
test('handshake uploader receives no CN credentials, code, delivery identity or GitHub token',()=>{
 const result=uploaderEnvironment({PATH:'/bin',ACTIONS_RUNTIME_TOKEN:'runtime',APPLE_CN_PASSWORD:'PRIVATE',APPLE_CN_2FA_CODE:'123456',DELIVERY_AGE_IDENTITY:'PRIVATE',GH_TOKEN:'PRIVATE'},'/tmp/public','safe-name');
 for(const key of ['APPLE_CN_PASSWORD','APPLE_CN_2FA_CODE','DELIVERY_AGE_IDENTITY','GH_TOKEN'])assert.equal(result[key],undefined);
 assert.equal(result.INPUT_ARCHIVE,'true');assert.equal(result.ACTIONS_RUNTIME_TOKEN,'runtime');
});
