"""Drain private child output while forwarding only fixed, bounded byte counters."""
import os
import re
import selectors
import subprocess
import time

MARKER=re.compile(rb"IPA_LAB_DOWNLOAD_BYTES:([0-9]{1,10}):([0-9]{1,10})")
MAX_CAPTURE=8*1024*1024

def run_download(binary,args,env,timeout,measure):
    child=subprocess.Popen([binary]+args,env=env,stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    selector=selectors.DefaultSelector()
    selector.register(child.stdout,selectors.EVENT_READ,"stdout")
    selector.register(child.stderr,selectors.EVENT_READ,"stderr")
    captured={"stdout":bytearray(),"stderr":bytearray()}
    partial=bytearray()
    deadline=time.monotonic()+timeout
    last_completed,last_total=-1,None
    try:
        while selector.get_map():
            if time.monotonic()>=deadline:
                raise subprocess.TimeoutExpired([binary],timeout)
            for key,_ in selector.select(min(0.5,max(0,deadline-time.monotonic()))):
                block=os.read(key.fd,65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                data=captured[key.data]
                data.extend(block)
                if len(data)>MAX_CAPTURE: del data[:-MAX_CAPTURE]
                if key.data!="stdout": continue
                partial.extend(block)
                while b"\n" in partial:
                    line,_,remaining=partial.partition(b"\n")
                    partial[:]=remaining
                    match=MARKER.fullmatch(line.rstrip(b"\r"))
                    if match:
                        completed,total=map(int,match.groups())
                        if 0<=completed<=total<=2_000_000_000 and total>0 and completed>=last_completed and (last_total is None or total==last_total):
                            last_completed,last_total=completed,total
                            try: measure(completed,total)
                            except Exception: pass
                if len(partial)>8192: partial.clear()
        child.wait(timeout=max(0.01,deadline-time.monotonic()))
        return subprocess.CompletedProcess([],child.returncode,
            captured["stdout"].decode("utf-8",errors="replace"),captured["stderr"].decode("utf-8",errors="replace"))
    finally:
        if child.poll() is None: child.kill()
        child.wait()
        selector.close()
        for pipe in (child.stdout,child.stderr): pipe.close()
