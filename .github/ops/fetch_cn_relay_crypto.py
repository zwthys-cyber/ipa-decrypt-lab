"""Load only the public crypto helper from the pinned verified Linux producer."""
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
from telegram_queue import GitHub,sha256,require
RUN=42543061196
COMMIT='b92dc1575123e1b7eab2283b62d355539fc71e4d'

def main():
    api=GitHub(os.environ['GH_TOKEN']);run=api.call('/actions/runs/'+str(RUN))
    require(run.get('path')=='.github/workflows/vps-release.yml' and run.get('display_title')=='VPS-controller-build'
            and run.get('head_branch')=='main' and run.get('head_sha')==COMMIT and run.get('status')=='completed' and run.get('conclusion')=='success','unverified_cn_crypto_producer')
    items=api.call('/actions/runs/'+str(RUN)+'/artifacts?per_page=100')['artifacts']
    found=[x for x in items if x.get('name')=='vps-controller-'+COMMIT and x.get('expired') is False]
    require(len(found)==1,'cn_crypto_artifact_missing');item=found[0]
    require(re.fullmatch(r'sha256:[a-f0-9]{64}',item.get('digest','')) and 0<item.get('size_in_bytes',0)<=128*1024*1024,'cn_crypto_artifact_bounds')
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);bundle=root/'bundle.zip';api.archive(item['id'],bundle,max_bytes=128*1024*1024)
        require('sha256:'+sha256(bundle)==item['digest'],'cn_crypto_artifact_digest')
        with zipfile.ZipFile(bundle) as z:
            require(len(z.infolist())==2 and set(z.namelist())=={'vps-controller.tar.gz','vps-controller.sha256'},'cn_crypto_zip_inventory')
            expected=z.read('vps-controller.sha256').decode().split()[0]
            packed=root/'package.tar.gz'
            with z.open('vps-controller.tar.gz') as src,packed.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
        require(sha256(packed)==expected,'cn_crypto_package_digest')
        with tarfile.open(packed,'r:gz') as z:
            files={};total=0
            for entry in z:
                name=entry.name.removeprefix('./')
                require(not entry.issym() and not entry.islnk(),'cn_crypto_link')
                if entry.isdir():continue
                require(entry.isfile() and not entry.sparse and name not in files,'cn_crypto_inventory')
                total+=entry.size;require(total<=512*1024*1024,'cn_crypto_expansion')
                files[name]=entry
            require({'SOURCE_COMMIT','bin/delivery-crypt'}<=set(files),'cn_crypto_missing')
            require(z.extractfile(files['SOURCE_COMMIT']).read().decode().strip()==COMMIT,'cn_crypto_source_binding')
            target=Path('cn-relay-crypto');target.mkdir()
            with z.extractfile(files['bin/delivery-crypt']) as src,(target/'delivery-crypt').open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
            (target/'delivery-crypt').chmod(0o755)
    print('{"schema":"cn-relay-crypto-v1","status":"verified"}')
if __name__=='__main__':main()
