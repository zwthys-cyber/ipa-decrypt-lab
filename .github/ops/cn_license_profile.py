"""Only booleans/counts leave private SINF and checkpoint inspection."""
import base64
from pathlib import Path
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import private_fairplay_state as checkpoint

class LicenseProfileError(ValueError):pass

def atoms(blob,start,end):
    output=[];cursor=start
    while cursor<end:
        if end-cursor<8 or len(output)>=1024:raise LicenseProfileError()
        size=struct.unpack_from('>I',blob,cursor)[0]
        if size<8 or size>end-cursor:raise LicenseProfileError()
        output.append((blob[cursor+4:cursor+8],cursor+8,cursor+size));cursor+=size
    return output

def unique(items,kind):
    selected=[x for x in items if x[0]==kind]
    if len(selected)!=1:raise LicenseProfileError()
    return selected[0][1:]

def selector(blob):
    if not 8<=len(blob)<=1024*1024:raise LicenseProfileError()
    root=atoms(blob,0,len(blob))
    if len(root)!=1 or root[0]!=(b'sinf',8,len(blob)):raise LicenseProfileError()
    schi=unique(atoms(blob,8,len(blob)),b'schi');fields=atoms(blob,*schi)
    user=unique(fields,b'user');key=unique(fields,b'key ');private=unique(fields,b'priv')
    if user[1]-user[0]!=4 or key[1]-key[0]!=4:raise LicenseProfileError()
    return struct.unpack_from('>I',blob,user[0])[0],struct.unpack_from('>I',blob,key[0])[0],private[1]-private[0]

def profile(app,dsid,state,guid):
    try:
        paths=list((Path(app)/'SC_Info').glob('*.sinf'))
        if not 0<len(paths)<=64 or any(p.is_symlink() or not p.is_file() or p.stat().st_size>1024*1024 for p in paths):raise LicenseProfileError()
        values=[selector(p.read_bytes()) for p in paths];expected=int(dsid)&0xffffffff
        result={'status':'license_geometry_observed','sinf_count':len(values),'distinct_selector_count':len({(u,k) for u,k,_ in values}),
            'sinf_user_equals_account_low32':all(u==expected for u,_,_ in values),'zero_user_present':any(u==0 for u,_,_ in values),
            'key_identifiers_nonzero':all(k!=0 for _,k,_ in values),'private_record_bytes':sorted({n for _,_,n in values}),
            'account_identifier_exceeds_32_bits':int(dsid)>0xffffffff}
        if state:
            hardware,files=checkpoint.validate(checkpoint.decode_bytes(state,checkpoint.LIMIT))
            result['checkpoint_matches_configured_guid']=hardware.hex().upper()==guid
            result['checkpoint_files_bytes']={k:len(v) for k,v in files.items()}
        return result
    except Exception:return {'status':'license_profile_unavailable'}
