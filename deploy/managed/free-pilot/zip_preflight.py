"""Bounded ZIP/ZIP64 metadata preflight for already prepared authorized archives.

Does not extract members, alter content, decrypt, verify CRCs or prove installation.
The uploader separately hashes the complete original file and checks Drive's digest.
"""
import os
import stat
import struct
import zipfile

MAX_ARCHIVE=10_000_000_000
MAX_EXPANDED=30_000_000_000
MAX_MEMBER=10_000_000_000
MAX_ENTRIES=32768
MAX_DIRECTORY=16*1024*1024

class ArchiveError(ValueError):pass
def need(ok):
    if not ok:raise ArchiveError("invalid_or_unsupported_archive")
def read_at(stream,offset,length):
    need(offset>=0 and 0<=length<=MAX_DIRECTORY)
    stream.seek(offset)
    data=stream.read(length);need(len(data)==length)
    return data

def directory(stream,size):
    # Validate the end records before ZipFile is allowed to allocate the directory.
    tail_size=min(size,65557)
    tail=read_at(stream,size-tail_size,tail_size)
    at=tail.rfind(b"PK\x05\x06")
    while at>=0:
        if len(tail)-at>=22:
            record=struct.unpack_from("<4s4H2IH",tail,at)
            if at+22+record[-1]==len(tail):break
        at=tail.rfind(b"PK\x05\x06",0,at)
    need(at>=0)
    end=size-tail_size+at
    _,disk,cd_disk,disk_count,count,length,offset,_=record
    need(disk==cd_disk==0)
    locator=read_at(stream,end-20,20) if end>=20 else b""
    wide=locator.startswith(b"PK\x06\x07")
    boundary=end
    if wide:
        _,loc_disk,wide_at,disks=struct.unpack("<4sIQI",locator)
        need(loc_disk==0 and disks==1 and wide_at+56<=end-20)
        header=read_at(stream,wide_at,56)
        sig,record_size,_,_,disk64,cd_disk64,disk_count64,count64,length64,offset64=struct.unpack("<4sQ2H2I4Q",header)
        need(sig==b"PK\x06\x06" and 44<=record_size<=4096 and wide_at+12+record_size==end-20)
        need(disk64==cd_disk64==0 and disk_count64==count64)
        need(disk_count in (count64,0xffff) and count in (count64,0xffff))
        need(length in (length64,0xffffffff) and offset in (offset64,0xffffffff))
        count,length,offset=count64,length64,offset64
        boundary=wide_at
    else:
        need(disk_count==count and count!=0xffff and length!=0xffffffff and offset!=0xffffffff)
    need(0<count<=MAX_ENTRIES and 46*count<=length<=MAX_DIRECTORY and offset>=30 and offset+length==boundary)
    return count,length,offset,wide

def inspect(stream):
    try:
        stream.seek(0,os.SEEK_END);size=stream.tell()
        need(0<size<=MAX_ARCHIVE)
        count,_,offset,wide=directory(stream,size)
        with zipfile.ZipFile(stream,allowZip64=True) as archive:
            entries=archive.infolist()
            need(len(entries)==count)
            names=set();offsets=set();expanded=0
            for item in entries:
                name=item.filename
                parts=name.rstrip("/").split("/")
                need(name==item.orig_filename and name and not name.startswith("/") and "\\" not in name and
                     "\x00" not in name and all(part not in ("",".","..") for part in parts))
                need(name not in names and item.header_offset not in offsets)
                names.add(name);offsets.add(item.header_offset)
                mode=stat.S_IFMT(item.external_attr>>16)
                need(mode in (0,stat.S_IFREG,stat.S_IFDIR) and not item.flag_bits&1 and
                     item.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED))
                need(0<=item.header_offset<offset and 0<=item.file_size<=MAX_MEMBER and 0<=item.compress_size<=size)
                if item.is_dir():need(item.file_size==0)
                if item.compress_type==zipfile.ZIP_STORED:need(item.file_size==item.compress_size)
                expanded+=item.file_size;need(expanded<=MAX_EXPANDED)
                # zipfile checks local header identity, offsets and member overlap on open.
                # Do not read member data here; this is a metadata-only preflight.
                with archive.open(item):pass
            need(min(offsets)==0)
        return {"archive_bytes":size,"declared_expanded_bytes":expanded,"entries":count,"zip64":wide,
                "whole_archive_crc_verified":False}
    except (ArchiveError,OSError,ValueError,RuntimeError,EOFError,struct.error,zipfile.BadZipFile,NotImplementedError):
        raise ArchiveError("invalid_or_unsupported_archive") from None
    finally:stream.seek(0)
