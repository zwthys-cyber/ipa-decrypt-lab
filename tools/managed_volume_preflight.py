"""Check a mounted controller volume using only disposable local data."""
from contextlib import closing
import fcntl
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from capacity import MIN_FREE_BYTES
from persistent_journal import PersistentJournal
from telegram_daemon import require_managed_volume
from telegram_queue import QueueError


def check_volume(root):
    require_managed_volume(root)
    filesystem = os.statvfs(root)
    if filesystem.f_flag & os.ST_RDONLY:
        raise QueueError("managed_volume_read_only")
    if filesystem.f_bavail * filesystem.f_frsize < MIN_FREE_BYTES:
        raise QueueError("managed_volume_insufficient_space")

    with TemporaryDirectory(prefix=".ipazake-preflight-", dir=root) as directory:
        staging = Path(directory)
        lock = staging / "probe.lock"
        with lock.open("a") as held, lock.open("a") as contender:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise QueueError("managed_volume_lock_unavailable")

        database = staging / "probe.sqlite3"
        with closing(PersistentJournal(database, 1)) as journal:
            if journal.db.execute("PRAGMA journal_mode").fetchone() != ("wal",):
                raise QueueError("managed_volume_wal_unavailable")
            journal.claim_update(0)
            journal.finish_update(0)
        with closing(PersistentJournal(database, 1)) as journal:
            if journal.offset() != 1:
                raise QueueError("managed_volume_journal_readback_failed")


def main():
    os.umask(0o077)
    try:
        check_volume(Path(os.environ.get("IPAZAKE_STATE", "/var/lib/ipazake")))
    except QueueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error):
        print("managed_volume_probe_failed", file=sys.stderr)
        return 2
    print("managed_controller_volume_ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
