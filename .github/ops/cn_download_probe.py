"""Bounded CN free-app download using only a restored saved session; no login."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from cn_session import decode
from native_store import classify_download,download_diagnostics

TARGET='1530340312'
LIMIT=200*1024*1024

class CNDownloadError(ValueError):pass

def require(value,label):
    if not value:raise CNDownloadError(label)

def check_metadata(value):
    require(isinstance(value,dict) and value.get('resultCount')==1 and isinstance(value.get('results'),list) and len(value['results'])==1,'cn_sample_unavailable')
    app=value['results'][0]
    require(isinstance(app,dict) and app.get('trackId')==int(TARGET) and app.get('wrapperType')=='software'
        and app.get('kind')=='software' and type(app.get('price')) in (int,float) and app['price']==0 and app.get('currency')=='CNY'
        and isinstance(app.get('bundleId'),str) and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',app['bundleId']), 'cn_sample_ineligible')
    size=app.get('fileSizeBytes')
    require(isinstance(size,str) and re.fullmatch(r'[0-9]{1,12}',size) and 0<int(size)<=LIMIT,'cn_sample_too_large')
    return {'app_id':TARGET,'bundle_id':app['bundleId'],'listed_bytes':int(size)}

def metadata():
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('https://itunes.apple.com/lookup?'+urllib.parse.urlencode({'id':TARGET,'country':'cn','entity':'software'}),timeout=20) as response:
        require(response.status==200,'cn_metadata_http_failed');raw=response.read(2*1024*1024+1)
    require(len(raw)<=2*1024*1024,'cn_metadata_oversized')
    return check_metadata(json.loads(raw))

def safe_failure(result):
    text=((result.stdout or '')+'\n'+(result.stderr or '')).lower()
    diagnostic=download_diagnostics(result)
    diagnostic['store_device_proof_failed']='storeamd' in text
    diagnostic['terms_confirmation_required']='terms' in text
    diagnostic['verification_required']='verification' in text and 'code' in text
    diagnostic['token_expired']='token' in text and 'expired' in text
    return diagnostic

def probe(binary,env,info,execute=None):
    require(info.get('app_id')==TARGET and isinstance(info.get('bundle_id'),str) and re.fullmatch(r'[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+',info['bundle_id']),'cn_sample_invalid')
    value,_=decode(env)
    home=Path(env['HOME']);base=home/'.ipatool';folder=base/hashlib.md5(value['email'].lower().encode()).hexdigest()
    require(not base.is_symlink() and not folder.exists() and not folder.is_symlink(),'cn_cache_not_empty')
    base.mkdir(mode=0o700,exist_ok=True);folder.mkdir(mode=0o700)
    path=folder/'account.json'
    child={key:env[key] for key in ('HOME','PATH','LANG','LAB_KBSYNC_HELPER') if key in env};child['GITHUB_ACTIONS']='true'
    execute=execute or subprocess.run
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(value['account'],stream)
        with tempfile.TemporaryDirectory(prefix='cn-original-private-') as directory:
            root=Path(directory);root.chmod(0o700);ipa=root/'original.ipa'
            result=execute([binary,'download',value['email'],info['bundle_id'],'--guid',value['guid'],'--output',str(ipa)],
                env=child,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300)
            report={'schema':'cn-download-session-v1','app_id':TARGET,'country_bound':'cn','login_attempted':False,
                'verification_code_used':False,'machine_authorization_attempted':False,'deauthorization_attempted':False,
                'downloaded':False,'decryption_proven':False,'plaintext_retained':False}
            if result.returncode:
                report.update(status=classify_download(result),diagnostic=safe_failure(result));return report
            require(ipa.is_file() and not ipa.is_symlink() and 0<ipa.stat().st_size<=LIMIT,'cn_ipa_invalid')
            with zipfile.ZipFile(ipa) as z:
                entries=z.infolist();require(0<len(entries)<=100000 and sum(x.file_size for x in entries)<=2*1024**3,'cn_ipa_inventory')
                require(len({x.filename for x in entries})==len(entries) and all(not x.filename.startswith(('/','\\')) and '..' not in Path(x.filename).parts for x in entries),'cn_ipa_inventory')
                plists=[x for x in entries if re.fullmatch(r'Payload/[^/]+[.]app/Info[.]plist',x.filename)]
                require(len(plists)==1 and 0<plists[0].file_size<=1024*1024,'cn_ipa_metadata')
                app=plistlib.loads(z.read(plists[0]));require(app.get('CFBundleIdentifier')==info['bundle_id'],'cn_ipa_bundle')
            report.update(status='cn_original_downloaded_with_saved_session',downloaded=True,session_reused=True,ipa_bytes=ipa.stat().st_size)
            return report
    finally:shutil.rmtree(folder)

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('--metadata',action='store_true');p.add_argument('--binary');args=p.parse_args()
    try:
        require(os.environ.get('GITHUB_ACTIONS')=='true','requires_github_actions')
        if args.metadata:
            value=metadata();Path('cn-sample-metadata.json').write_text(json.dumps(value));print(json.dumps({'schema':'cn-sample-v1','status':'eligible','app_id':TARGET}));return 0
        info=json.loads(Path('cn-sample-metadata.json').read_text())
        value=probe(str(Path(args.binary).resolve()),dict(os.environ),info)
    except Exception as exc:
        known={'cn_sample_unavailable','cn_sample_ineligible','cn_sample_too_large','cn_cache_not_empty','cn_ipa_invalid','cn_ipa_inventory','cn_ipa_metadata','cn_ipa_bundle'}
        value={'schema':'cn-download-session-v1','status':str(exc) if isinstance(exc,CNDownloadError) and str(exc) in known else 'cn_download_probe_failed','downloaded':False,'login_attempted':False,'plaintext_retained':False}
    Path('cn-download-receipt.json').write_text(json.dumps(value));print(json.dumps(value),flush=True)
    return 0 if value.get('downloaded') is True else 2
if __name__=='__main__':raise SystemExit(main())
