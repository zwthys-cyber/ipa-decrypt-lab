"""Prune only verified release directories after successful deployment."""
import json
from pathlib import Path
import re
import shutil

def prune(base):
    base=Path(base)
    releases=base/"releases"
    if releases.is_symlink() or not releases.is_dir():
        return 0
    releases=releases.resolve()
    keep=set()
    for name in ("current","previous"):
        link=base/name
        if not link.is_symlink():
            return 0
        target=link.resolve(strict=True)
        if target.parent!=releases or not re.fullmatch(r"[a-f0-9]{40}",target.name) or not target.is_dir():
            return 0
        keep.add(target)
    # No glob-recursive deletion or state/config cleanup. Unknown files stay.
    removed=0
    for item in releases.iterdir():
        if (not item.is_symlink() and item.is_dir()
                and re.fullmatch(r"[a-f0-9]{40}",item.name)
                and item.resolve() not in keep):
            shutil.rmtree(item)
            removed+=1
    return removed

if __name__=="__main__":
    try:
        print(json.dumps({"status":"release_cleanup_complete","removed":prune("/opt/ipazake")}))
    except Exception:
        print('{"status":"release_cleanup_deferred"}')
        raise SystemExit(2)
