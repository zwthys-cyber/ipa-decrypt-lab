"""Public native country-context contract; actual hardware never enters its receipt."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
BOOLS=('account_login_attempted','authorization_request_attempted','model_recovered','cn_override_bound','body_preserved','native_guid_preserved','anisette_preserved')
def sanitized(value):
    if type(value) is not dict or set(value)!=set(BOOLS+('schema','status','default_country')):raise ValueError('storefront_schema')
    if value['schema']!='cn-storefront-contract-v1' or value['status']!='constructor_observed' or value['default_country'] not in ('cn','us','de','other','absent'):raise ValueError('storefront_constructor_unavailable')
    if any(type(value[k]) is not bool for k in BOOLS):raise ValueError('storefront_proof')
    if any(value[k] for k in BOOLS[:3]) or not all(value[k] for k in BOOLS[3:]):raise ValueError('storefront_proof')
    return value

def main():
    os.umask(0o077);env={k:os.environ[k] for k in ('HOME','PATH','LANG') if k in os.environ};env['GITHUB_ACTIONS']='true'
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('requires_github_actions')
    identity=subprocess.check_output(['public-native/native-device-identity'],env=env,timeout=10)
    if not re.fullmatch(rb'[A-F0-9]{12}',identity):raise ValueError('native_identity_unavailable')
    with tempfile.TemporaryDirectory(prefix='cn-public-storefront-') as directory:
        root=Path(directory);root.chmod(0o700);path=root/'report.json'
        process=subprocess.run(['public-native/cn-storefront-probe',str(path)],env=env,input=json.dumps({'guid':identity.decode()}).encode(),capture_output=True,timeout=50)
        if process.returncode or not path.is_file() or path.stat().st_size>8192:raise ValueError('storefront_probe_failed')
        report=sanitized(json.loads(path.read_bytes()))
    report.update(pool=os.environ['CN_PUBLIC_POOL'],run_id=os.environ['GITHUB_RUN_ID'],source_commit=os.environ['GITHUB_SHA'])
    Path('cn-storefront-report.json').write_text(json.dumps(report));print(json.dumps(report),flush=True)
if __name__=='__main__':main()
