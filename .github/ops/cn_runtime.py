"""Provenance-bound CN variant; normal runtime producer and cache are unchanged."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from native_runtime import fingerprint as base_fingerprint, allowed, digest, unpack, host_pool, MAX_ARCHIVE, MAX_EXPANDED
from telegram_queue import GitHub

WORKFLOW='.github/workflows/cn-auth-runtime.yml'
def fingerprint(root=Path('.')):
    root=Path(root);h=hashlib.sha256(bytes.fromhex(base_fingerprint(root)))
    for name in [WORKFLOW,'.github/ops/ChinaLogin.swift','.github/ops/LabCNLoginFlow.swift','.github/ops/LabCNLoginFlowTests.swift','.github/ops/patch_cn_login.py']:
        h.update(name.encode()+b'\0');h.update(bytes.fromhex(digest(root/name)))
    return h.hexdigest()

def pack(root=Path('.')):
    root=Path(root);runtime=root/'base-runtime'
    shutil.copyfile(root/'native-source/ApplePackage/.build/debug/ApplePackageTool',runtime/'ApplePackageTool')
    files={}
    for p in sorted(runtime.rglob('*')):
        if p.name=='manifest.json':continue
        if p.is_symlink():raise ValueError('CN runtime symlink')
        if p.is_file():
            name=p.relative_to(runtime).as_posix()
            if not allowed(name):raise ValueError('unexpected CN runtime file')
            files[name]={'size':p.stat().st_size,'sha256':digest(p)}
    if sum(x['size'] for x in files.values())>MAX_EXPANDED:raise ValueError('CN runtime size')
    manifest={'schema':'native-runtime-v1','profile':'cn-auth-session-v1','fingerprint':fingerprint(root),
              'pool':'macos-26-intel','commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'files':files}
    raw=json.dumps(manifest,sort_keys=True).encode();target=root/'cn-runtime-out/native-runtime.tar.gz';target.parent.mkdir()
    with tarfile.open(target,'w:gz') as z:
        entry=tarfile.TarInfo('manifest.json');entry.size=len(raw);z.addfile(entry,io.BytesIO(raw))
        for name in files:z.add(runtime/name,arcname=name,recursive=False)
    if target.stat().st_size>MAX_ARCHIVE:raise ValueError('CN archive size')
    unpack(target,root/'relocated-cn-runtime',manifest['fingerprint'],'macos-26-intel',manifest['commit'],manifest['run_id'])
    print(json.dumps({'schema':'cn-auth-runtime-build-v1','fingerprint':manifest['fingerprint'],'files':len(files)}))

def fetch(destination):
    if host_pool()!='macos-26-intel':raise ValueError('CN runtime platform')
    client=GitHub(os.environ['GH_TOKEN']);stamp=fingerprint();name='cn-auth-runtime-macos-26-intel-'+stamp
    items=client.call('/actions/artifacts?per_page=20&name='+name).get('artifacts',[])
    for item in items:
        if item.get('name')!=name or item.get('expired') is not False:continue
        run=client.call('/actions/runs/'+str(item.get('workflow_run',{}).get('id')))
        if not (run.get('path')==WORKFLOW and run.get('head_branch')=='main' and run.get('event')=='workflow_dispatch'
                and run.get('status')=='completed' and run.get('conclusion')=='success'
                and run.get('head_sha')==item.get('workflow_run',{}).get('head_sha')):continue
        if not re.fullmatch('sha256:[a-f0-9]{64}',item.get('digest','')) or not 0<item.get('size_in_bytes',0)<=MAX_ARCHIVE:raise ValueError('CN artifact bounds')
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'bundle.zip';client.archive(item['id'],archive,max_bytes=MAX_ARCHIVE)
            if 'sha256:'+digest(archive)!=item['digest']:raise ValueError('CN artifact digest')
            with zipfile.ZipFile(archive) as zipped:
                entries=zipped.infolist()
                if len(entries)!=1 or entries[0].filename!='native-runtime.tar.gz' or entries[0].file_size>MAX_ARCHIVE:raise ValueError('CN artifact inventory')
                packed=Path(directory)/'runtime.tar.gz'
                with zipped.open(entries[0]) as src,packed.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
            result=unpack(packed,destination,stamp,'macos-26-intel',run['head_sha'],run['id'])
            if result.get('profile')!='cn-auth-session-v1':raise ValueError('CN profile binding')
        print(json.dumps({'schema':'cn-auth-runtime-fetch-v1','producer':run['id'],'fingerprint':stamp}));return
    raise ValueError('validated_CN_runtime_missing')

if __name__=='__main__':
    if sys.argv[1]=='pack':pack()
    elif sys.argv[1]=='fingerprint':print(fingerprint())
    else:fetch(Path(sys.argv[2]))
