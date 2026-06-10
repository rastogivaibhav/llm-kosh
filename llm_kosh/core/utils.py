import datetime as dt
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Dict, Tuple

from .constants import UTC


def now_iso() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(text: str, limit: int = 64) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    if not text:
        text = "memory"
    return text[:limit].rstrip("-")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def ensure_root(root: Path) -> None:
    if not (root / "LLM_KOSH.json").exists():
        raise SystemExit(f"Not an AI cartridge root: {root}\nRun: llm_kosh_cli.py --root {root} init")


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    import tempfile
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=str(path.parent), delete=False, encoding=encoding) as tf:
        tf.write(text)
        temp_name = tf.name
    try:
        os.replace(temp_name, str(path))
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def write_json(path: Path, data: dict) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


GENESIS_HASH = "sha256:" + "0" * 64


def _lock_file(f) -> None:
    """Acquire an advisory lock on the file handle.

    On POSIX we use fcntl.flock (advisory, allows concurrent readers).
    On Windows we skip msvcrt.locking — it applies mandatory byte-range locks
    that block concurrent reads from other processes, which breaks concurrent
    append scenarios.  Windows append-mode writes are atomic for single-record
    JSON lines (well within the 4 KB atomic-write guarantee), so OS-level
    append serialisation is sufficient for cross-process safety.
    """
    try:
        if __import__("os").name != "nt":
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except Exception:
        pass  # locking is best-effort; never block the write itself


def _unlock_file(f) -> None:
    try:
        if __import__("os").name != "nt":
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


def row_hash(row: dict) -> str:
    """Canonical SHA-256 of a ledger row, excluding its own row_hash field."""
    payload = {k: v for k, v in row.items() if k != "row_hash"}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(canonical.encode("utf-8"))


def _read_chain_head(ledger: Path) -> str:
    """Last row hash in the chain: from CHAIN_HEAD cache, else tail scan, else genesis."""
    head_file = ledger.parent / "CHAIN_HEAD"
    if head_file.exists():
        try:
            cached = head_file.read_text(encoding="utf-8").strip()
            if cached.startswith("sha256:"):
                return cached
        except OSError:
            pass  # concurrent os.replace on Windows can make the file briefly unreadable
    if ledger.exists():
        last = None
        # Retry up to 10x with 5 ms gaps — on Windows, newly created files can be
        # transiently locked by AV/Defender before any advisory lock is involved.
        import time
        for _attempt in range(10):
            try:
                with ledger.open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if line.strip():
                            last = line
                break
            except OSError:
                if _attempt < 9:
                    time.sleep(0.005)
        if last:
            try:
                prev_row = json.loads(last)
                return prev_row.get("row_hash") or row_hash(prev_row)
            except Exception:
                pass
    return GENESIS_HASH


def _win32_acquire_write_lock(lock_path: Path, timeout_s: float = 10.0):
    """Acquire a cross-process write lock on Windows using msvcrt byte-range locking.

    Uses a PERSISTENT lock file (never created/deleted per-call) to avoid
    antivirus scanner interference — AV scanners on Windows CI hold newly
    created files open briefly, causing os.unlink to fail.

    The lock file stays on disk; mutual exclusion comes from msvcrt.LK_NBLCK
    which raises OSError(EACCES) if another process holds the same byte range.

    Returns an open file object.  Caller MUST call _win32_release_write_lock().
    """
    import msvcrt, time as _t
    lock_path.touch()  # create once; never deleted
    end = _t.monotonic() + timeout_s
    while True:
        try:
            f = lock_path.open("rb+")
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f
        except OSError:
            try:
                f.close()
            except Exception:
                pass
            if _t.monotonic() >= end:
                raise RuntimeError(
                    f"llm-kosh: could not acquire write lock after {timeout_s:.0f} s: {lock_path}"
                )
            _t.sleep(0.005)


def _win32_release_write_lock(f) -> None:
    import msvcrt
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        f.close()
    except OSError:
        pass


def append_ledger(root: Path, event: str, payload: dict) -> None:
    """Append a hash-chained event row. Locked, fsynced, tamper-evident.

    Each row carries `prev` (hash of the previous row) and `row_hash`
    (canonical SHA-256 of the row itself), forming a verifiable chain
    from GENESIS_HASH. Legacy rows without these fields remain valid.
    """
    import os
    ledger = root / "ledger" / "events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)

    # Cross-process mutual exclusion ──────────────────────────────────────────
    # On Windows, open("a") uses SetFilePointer+WriteFile (not atomic across
    # processes), so concurrent appends from separate processes can overlap.
    # We use msvcrt.locking on a persistent side-file for mutual exclusion.
    # The side-file is never deleted — this avoids AV scanners that hold
    # newly-created files open and prevent os.unlink.  The lock only covers
    # the side-file byte range, so it never blocks readers of events.jsonl.
    # On POSIX, fcntl.flock in _lock_file() provides the same guarantee.
    lock_fobj = None
    lock_path = ledger.parent / ".write.lock"
    if os.name == "nt":
        lock_fobj = _win32_acquire_write_lock(lock_path)

    try:
        prev = _read_chain_head(ledger)
        with ledger.open("a", encoding="utf-8") as f:
            _lock_file(f)
            try:
                row = {"event_id": f"evt_{uuid.uuid4().hex}", "event": event,
                       "time": now_iso(), **payload, "prev": prev}
                row["row_hash"] = row_hash(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
                try:
                    atomic_write_text(ledger.parent / "CHAIN_HEAD", row["row_hash"] + "\n")
                except OSError:
                    pass  # CHAIN_HEAD is a cache; readers fall back to ledger scan
            finally:
                _unlock_file(f)
    finally:
        if lock_fobj is not None:
            _win32_release_write_lock(lock_fobj)


def frontmatter(meta: Dict[str, object]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if isinstance(v, list):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            sv = str(v)
            if ":" in sv or "#" in sv or "\n" in sv or sv.strip() != sv:
                lines.append(f"{k}: {json.dumps(sv, ensure_ascii=False)}")
            else:
                lines.append(f"{k}: {sv}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip().splitlines()
    body = text[end + len("\n---"):].lstrip("\n")
    meta: Dict[str, str] = {}
    for line in raw:
        if not line.strip() or line.strip().startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            try:
                v = json.loads(v)
            except Exception:
                v = v.strip('"')
        elif v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    v = parsed
            except Exception:
                pass
        meta[k.strip()] = v
    return meta, body


def source_dir_for_kind(root: Path, kind: str) -> Path:
    mapping = {
        "project": "projects", "decision": "decisions", "prompt": "prompts",
        "note": "notes", "file": "intake", "conversation": "conversations",
        "receipt": "receipts", "correction": "corrections", "gap": "gaps",
        "suggestion": "suggestions",
    }
    return root / "source" / mapping.get(kind, kind + "s")
