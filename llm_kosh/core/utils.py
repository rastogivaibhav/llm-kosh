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


def append_ledger(root: Path, event: str, payload: dict) -> None:
    ledger = root / "ledger" / "events.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    row = {"event_id": f"evt_{uuid.uuid4().hex}", "event": event, "time": now_iso(), **payload}
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


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
        meta[k.strip()] = v.strip().strip('"')
    return meta, body


def source_dir_for_kind(root: Path, kind: str) -> Path:
    mapping = {
        "project": "projects", "decision": "decisions", "prompt": "prompts",
        "note": "notes", "file": "generated-files", "conversation": "conversations",
        "receipt": "receipts", "correction": "corrections", "gap": "gaps",
        "suggestion": "suggestions",
    }
    return root / "source" / mapping.get(kind, kind + "s")
