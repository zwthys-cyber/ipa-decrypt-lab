"""Bounded private subprocesses; cancellation kills the complete child process group."""
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from task_context import require

def run(binary,args,env,timeout,root,checkpoint=lambda:None):
    require(Path(binary).is_absolute() and Path(root).is_dir() and timeout>0,"private_process_arguments")
    require(not any(k.startswith("GITHUB_") or k in ("GH_TOKEN","CIRCLE_TOKEN","CIRCLE_OIDC_TOKEN_V3",
        "TELEGRAM_BOT_TOKEN","CF_API_TOKEN","CIRCLECI_API_TOKEN") for k in env),"private_process_environment")
    checkpoint()
    with tempfile.TemporaryFile(dir=root) as out,tempfile.TemporaryFile(dir=root) as err:
        child=subprocess.Popen([str(binary),*map(str,args)],stdin=subprocess.DEVNULL,stdout=out,stderr=err,
            cwd=root,env=env,start_new_session=True,close_fds=True)
        deadline=time.monotonic()+timeout
        try:
            while child.poll() is None:
                checkpoint()
                require(time.monotonic()<deadline,"private_process_timeout")
                require(os.fstat(out.fileno()).st_size<=8*1024*1024 and
                    os.fstat(err.fileno()).st_size<=8*1024*1024,"private_process_output_limit")
                time.sleep(0.2)
            checkpoint()
            require(os.fstat(out.fileno()).st_size<=8*1024*1024 and
                os.fstat(err.fileno()).st_size<=8*1024*1024,"private_process_output_limit")
            out.seek(0);err.seek(0)
            return subprocess.CompletedProcess([str(binary),*map(str,args)],child.returncode,
                out.read().decode("utf-8",errors="replace"),err.read().decode("utf-8",errors="replace"))
        finally:
            # Also reap any descendants left by a successfully exited launcher.
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:pass
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
