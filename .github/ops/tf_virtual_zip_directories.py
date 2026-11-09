"""Canonical empty ZIP directories without changing any member payload or mode."""
import copy
import hashlib
from pathlib import Path
import shutil
import zipfile

def inventory(path):
    result={}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.filename in result:raise ValueError()
            digest=hashlib.sha256()
            with archive.open(info) as source:
                for block in iter(lambda:source.read(1024*1024),b""):digest.update(block)
            result[info.filename]=(info.file_size,info.CRC,info.external_attr,digest.hexdigest())
    return result

def canonicalize(source,destination):
    before=inventory(source)
    changed=0
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(destination,"x",allowZip64=True) as output:
        output.comment=original.comment
        for info in original.infolist():
            target=copy.copy(info)
            if info.is_dir():
                if info.file_size!=0 or info.CRC!=0 or original.read(info)!=b"":raise ValueError()
                if info.compress_type!=zipfile.ZIP_STORED or info.compress_size!=0:changed+=1
                target.compress_type=zipfile.ZIP_STORED
                output.writestr(target,b"")
            else:
                with original.open(info) as src,output.open(target,"w",force_zip64=True) as dst:
                    shutil.copyfileobj(src,dst,1024*1024)
    destination.chmod(0o600)
    if inventory(destination)!=before:raise ValueError()
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or any(info.is_dir() and (info.compress_type!=zipfile.ZIP_STORED or info.compress_size!=0) for info in archive.infolist()):raise ValueError()
    return {"empty_directories_canonicalized":changed,"payloads_unchanged":True,"member_count":len(before)}
