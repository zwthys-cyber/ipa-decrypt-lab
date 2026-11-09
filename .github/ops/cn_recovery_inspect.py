"""Fixed-schema offline diagnostic; never emits selectors, paths, keys or models."""
import json
from pathlib import Path
import os
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import private_fairplay_state as checkpoint

BOOLS=('sidb_authenticated','exact_route_matched','first_block_accepted','full_license_accepted','model_written')
COUNTS=('registry_count','registry_records','tree_nodes','root_version','account_version','type_bytes','sign_bytes','value_bytes')
STATUSES={'input_rejected','sidb_rejected','route_rejected','class_derivation_rejected','first_block_rejected','full_license_rejected','license_accepted_diagnostic_only'}
STAGES={'load_inputs','decode_sidb','select_route','derive_class_key','first_block','full_license'}
def sanitized(raw):
    if not 0<len(raw)<=8192:raise ValueError('diagnostic_size')
    value=json.loads(raw)
    if type(value) is not dict or set(value)!=set(BOOLS+COUNTS+('schema','status','stage')):raise ValueError('diagnostic_schema')
    if value['schema']!='cn-offline-recovery-inspection-v1' or value['status'] not in STATUSES or value['stage'] not in STAGES:raise ValueError('diagnostic_schema')
    if any(type(value[k]) is not bool for k in BOOLS) or value['model_written'] is not False:raise ValueError('diagnostic_proof')
    if any(type(value[k]) is not int or not 0<=value[k]<=1048576 for k in COUNTS):raise ValueError('diagnostic_counts')
    if value['full_license_accepted'] and not value['first_block_accepted'] or value['first_block_accepted'] and not value['exact_route_matched'] or value['exact_route_matched'] and not value['sidb_authenticated']:raise ValueError('diagnostic_proof')
    return value

def inspect(binary,app,root,encoded):
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('requires_github_actions')
    state=checkpoint.materialize(encoded,root/'diagnostic-state')
    sinfs=list((app/'SC_Info').glob('*.sinf'))
    if len(sinfs)!=1 or sinfs[0].is_symlink():raise ValueError('diagnostic_sinf_count')
    result=subprocess.run([str(Path(binary).resolve()),str(state['fpsd']/'SC Info.sidb'),str(sinfs[0]),str(state['hardware'])],env={'PATH':'/usr/bin:/bin','GITHUB_ACTIONS':'true'},stdin=subprocess.DEVNULL,capture_output=True,timeout=120)
    if result.returncode:raise ValueError('diagnostic_process_rejected')
    return sanitized(result.stdout)
