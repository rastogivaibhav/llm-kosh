#!/usr/bin/env python3
"""
AI Memory Cartridge v0.2

A local-first, human-readable AI memory cartridge.

Core loop:
  init -> add/ingest -> index/query -> pack -> upload to LLM -> absorb receipt -> audit/heal

What changed in v0.2 (vs v0):
  1. absorb is no longer a stub. It parses a MEMORY_RECEIPT into TYPED memories
     (decisions, corrections, generated-files, gaps, suggestions) and records
     provenance (each item links back to the receipt it came from).
  2. Supersession. A Correction can retire the belief it corrects: the old item
     is marked status=superseded with a superseded_by backlink, and the new item
     records what it supersedes. Nothing is deleted -- source stays the truth and
     history is preserved, so it is fully reversible.
  3. Redaction gate at the pack boundary. pack now scans every doc that would
     leave the machine for secrets and BLOCKS by default. Use --redact to mask
     them in the export (source untouched) or --allow-secrets to override.
  4. Incremental index. The FTS index is only rebuilt when the source corpus
     fingerprint changes, instead of on every single command.
  5. Hardened query: FTS terms are quoted (no more operator-injection surprises)
     and snippets are computed in Python (the old contentless snippet() returned None).

No cloud dependency. No vendor dependency. Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import uuid
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

UTC = dt.timezone.utc
APP_VERSION = "1.0.0"

KINDS = {
    "project", "decision", "prompt", "note", "file", "conversation",
    "receipt", "correction", "gap", "suggestion",
}
VISIBILITIES = ["private", "personal", "work-safe", "shareable", "public", "blocked", "quarantine"]
SHAREABLE_VIS = {"public", "work-safe", "shareable"}
DEFAULT_ROOT_NAME = "AI-Cartridge"

# Secret detectors used by the pack redaction gate. Each entry is (label, regex).
# The regex's group(1) (if present) is the value that gets masked; otherwise the
# whole match is masked. Patterns are intentionally conservative to limit false
# positives -- known prefixes plus keyword=value assignments.
SECRET_PATTERNS: List[Tuple[str, "re.Pattern"]] = [
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("stripe_live_key", re.compile(r"\b(?:sk|pk|rk)_live_[0-9A-Za-z]{16,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\b")),
    # keyword = value (catches generic "password: ...", "api_key=...", "token: ...")
    ("keyword_secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|secret[_-]?key|password|passwd|pwd|access[_-]?token|auth[_-]?token|bearer|client[_-]?secret)\b\s*[:=]\s*(?P<val>[^\s'\";]{6,})"
    )),
]

RECEIPT_SECTIONS = {
    "new decisions": "decision",
    "corrections": "correction",
    "generated files": "file",
    "open gaps": "gap",
    "suggested memory updates": "suggestion",
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

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
    if not (root / "CARTRIDGE.json").exists():
        raise SystemExit(f"Not an AI cartridge root: {root}\nRun: cartridge.py --root {root} init")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #

def init_cartridge(root: Path, owner: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel in [
        "source/identity", "source/preferences", "source/projects", "source/decisions",
        "source/prompts", "source/notes", "source/generated-files", "source/conversations",
        "source/receipts", "source/corrections", "source/gaps", "source/suggestions",
        "ledger", "indexes", "exports", "quarantine", "reports", "attachments/imports",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)

    config = {
        "schema": "ai-memory-cartridge.v0",
        "version": APP_VERSION,
        "cartridge_id": "cart_" + uuid.uuid4().hex[:12],
        "owner": owner,
        "created_at": now_iso(),
        "principles": [
            "Human-readable source is the truth.",
            "Indexes are rebuildable.",
            "Exports are bootable context packs.",
            "LLM outputs should return MEMORY_RECEIPT blocks.",
            "Corrections supersede; they never silently delete. History is preserved.",
            "Nothing leaves the machine through a pack without passing the secret gate.",
        ],
    }
    write_json(root / "CARTRIDGE.json", config)

    (root / "BOOT.md").write_text(boot_text(owner), encoding="utf-8")

    append_ledger(root, "cartridge.initialized", {"root": str(root), "owner": owner})
    rebuild_index(root, force=True)
    print(f"Initialized AI Memory Cartridge v{APP_VERSION} at: {root}")


def boot_text(owner: str = "") -> str:
    who = f"\nThis cartridge was created for: **{owner}**.\n" if owner else ""
    return f"""# AI Memory Cartridge Boot Instructions

You are reading a portable AI memory cartridge or a focused context pack exported from one.

## How to use this pack

1. Read `MANIFEST.json` first if present.
2. Read `02_CONTEXT_BRIEF.md` next.
3. Use `03_MATCHED_MEMORY.md`, `04_DECISIONS.md`, and `05_SOURCE_MAP.json` as the working source.
4. Do not assume missing systems, files, services, or prior decisions exist.
5. Preserve existing decisions unless the user explicitly asks you to change them.
6. At the end of substantial work, return a `MEMORY_RECEIPT` section so the user can
   absorb your output back into their cartridge.

## MEMORY_RECEIPT format (grammar the absorber understands)

```markdown
# MEMORY_RECEIPT

## New decisions
- Short title :: Optional longer body explaining the decision [project: Name]

## Corrections
- What was wrong and what is now true [ref: <existing-memory-id>]

## Generated files
- filename.ext :: what it is / where it lives

## Open gaps
- Something still unresolved

## Suggested memory updates
- A non-binding suggestion for the owner to consider
```

Notes for the model:
- `::` separates a short title from a longer body. If you omit it, the whole line is used.
- `[project: Name]` attaches the item to a project.
- `[ref: <id>]` in a Correction names the exact memory it corrects, so absorb can
  retire it deterministically. If you do not know the id, just describe the correction
  and the owner's tool will try to match it (and flag it if unsure).
{who}"""


# --------------------------------------------------------------------------- #
# add / update memories
# --------------------------------------------------------------------------- #

def add_memory(
    root: Path, kind: str, title: str, body: str,
    project: str = "", visibility: str = "private",
    source_file: Optional[Path] = None, extra_meta: Optional[dict] = None,
    reindex: bool = True, quiet: bool = False,
) -> Path:
    ensure_root(root)
    if kind not in KINDS:
        raise SystemExit(f"Unsupported kind {kind}. Use one of: {', '.join(sorted(KINDS))}")
    item_id = f"{kind}.{slugify(project) + '.' if project else ''}{slugify(title)}.{uuid.uuid4().hex[:8]}"
    created = now_iso()
    dest_dir = source_dir_for_kind(root, kind)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{slugify(title)}-{uuid.uuid4().hex[:6]}.md"

    copied_file_rel = ""
    if source_file:
        if not source_file.exists():
            raise SystemExit(f"Source file not found: {source_file}")
        files_dir = root / "attachments" / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        copied = files_dir / f"{uuid.uuid4().hex[:8]}-{source_file.name}"
        shutil.copy2(source_file, copied)
        copied_file_rel = str(copied.relative_to(root))
        if not body:
            body = f"Attached file: `{copied_file_rel}`\n\nOriginal filename: `{source_file.name}`\n"

    meta: Dict[str, object] = {
        "type": kind, "id": item_id, "title": title, "project": project,
        "visibility": visibility, "status": "active", "created": created,
    }
    if copied_file_rel:
        meta["attached_file"] = copied_file_rel
    if extra_meta:
        meta.update(extra_meta)

    content = f"{frontmatter(meta)}\n\n# {title}\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")
    append_ledger(root, f"{kind}.created", {
        "id": item_id, "path": str(path.relative_to(root)), "hash": sha256_file(path),
        **({"source_receipt": meta["source_receipt"]} if meta.get("source_receipt") else {}),
    })
    if reindex:
        rebuild_index(root)
    if not quiet:
        print(f"Added {kind}: {title}")
        print(path)
    return path


def update_doc_meta(root: Path, rel_path: str, updates: Dict[str, object]) -> dict:
    """Rewrite a source doc's frontmatter in place (body preserved). Non-destructive."""
    path = root / rel_path
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)
    meta.update({k: str(v) for k, v in updates.items()})
    meta["updated"] = now_iso()
    content = f"{frontmatter(meta)}\n\n{body.strip()}\n"
    path.write_text(content, encoding="utf-8")
    return meta


def find_doc_by_id(root: Path, doc_id: str) -> Optional[str]:
    for p in iter_source_files(root):
        meta, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if meta.get("id") == doc_id:
            return str(p.relative_to(root))
    return None


def supersede(root: Path, old_id: str, new_id: str, reason: str = "") -> bool:
    """Mark old_id superseded by new_id. Returns False if old_id not found.
    Non-destructive: the old file remains, only its frontmatter status/backlink change."""
    old_rel = find_doc_by_id(root, old_id)
    if not old_rel:
        return False
    update_doc_meta(root, old_rel, {"status": "superseded", "superseded_by": new_id})
    new_rel = find_doc_by_id(root, new_id)
    if new_rel:
        new_meta, _ = parse_frontmatter((root / new_rel).read_text(encoding="utf-8", errors="replace"))
        existing = new_meta.get("supersedes", "")
        merged = ",".join([s for s in (existing.split(",") if existing else []) + [old_id] if s])
        update_doc_meta(root, new_rel, {"supersedes": merged})
    append_ledger(root, "memory.superseded", {"old_id": old_id, "new_id": new_id, "reason": reason})
    return True


# --------------------------------------------------------------------------- #
# indexing
# --------------------------------------------------------------------------- #

def iter_source_files(root: Path) -> Iterable[Path]:
    base = root / "source"
    if not base.exists():
        return
    for p in sorted(base.rglob("*.md")):
        if p.is_file():
            yield p


def get_db(root: Path) -> sqlite3.Connection:
    db_path = root / "indexes" / "memory.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def corpus_fingerprint(root: Path) -> str:
    """A single hash over (relpath, content-hash) pairs. Changes iff the corpus changes."""
    h = hashlib.sha256()
    for p in iter_source_files(root):
        h.update(str(p.relative_to(root)).encode("utf-8"))
        h.update(sha256_file(p).encode("utf-8"))
    return h.hexdigest()


def rebuild_index(root: Path, force: bool = False) -> bool:
    """Rebuild the FTS index only when the corpus fingerprint changed.
    Returns True if a rebuild actually happened."""
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "indexes" / "index_state.json"
    db_path = root / "indexes" / "memory.sqlite"
    fp = corpus_fingerprint(root)
    if not force and db_path.exists():
        prev = read_json(state_path, {})
        if prev.get("fingerprint") == fp:
            return False  # up to date, skip the expensive rebuild

    conn = get_db(root)
    conn.executescript(
        """
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS documents_fts;
        CREATE TABLE documents (
          id TEXT PRIMARY KEY, kind TEXT, title TEXT, project TEXT,
          visibility TEXT, status TEXT, path TEXT, body TEXT, hash TEXT,
          created TEXT, supersedes TEXT, superseded_by TEXT, source_receipt TEXT
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
          id UNINDEXED, title, project, kind, body, content=''
        );
        """
    )
    seen_index_ids = set()
    for path in iter_source_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        doc_id = meta.get("id") or f"doc.{uuid.uuid4().hex}"
        # A duplicate id is a corruption audit should *report*, not a crash. Index the
        # first occurrence under its id; suffix later collisions so the rebuild survives.
        if doc_id in seen_index_ids:
            doc_id = f"{doc_id}#dup-{uuid.uuid4().hex[:6]}"
        seen_index_ids.add(doc_id)
        conn.execute(
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, meta.get("type") or "note", meta.get("title") or path.stem,
             meta.get("project", ""), meta.get("visibility", "private"),
             meta.get("status", "active"), str(path.relative_to(root)), body,
             sha256_file(path), meta.get("created", ""), meta.get("supersedes", ""),
             meta.get("superseded_by", ""), meta.get("source_receipt", "")),
        )
        conn.execute(
            "INSERT INTO documents_fts(rowid, id, title, project, kind, body) "
            "VALUES ((SELECT rowid FROM documents WHERE id=?), ?, ?, ?, ?, ?)",
            (doc_id, doc_id, meta.get("title") or path.stem, meta.get("project", ""),
             meta.get("type") or "note", body),
        )
    conn.commit()
    conn.close()
    write_json(state_path, {"fingerprint": fp, "rebuilt_at": now_iso()})
    return True


# --------------------------------------------------------------------------- #
# query
# --------------------------------------------------------------------------- #

FOLDER_TO_KIND = {
    "projects": "project", "decisions": "decision", "prompts": "prompt",
    "notes": "note", "generated-files": "file", "conversations": "conversation",
    "receipts": "receipt", "corrections": "correction", "gaps": "gap",
    "suggestions": "suggestion",
}

# --------------------------------------------------------------------------- #
# text similarity (pure-stdlib TF-IDF cosine) — powers correction matching and
# query re-ranking without any third-party dependency.
# --------------------------------------------------------------------------- #

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_]+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with", "is",
    "are", "was", "be", "this", "that", "it", "as", "at", "by", "from", "we",
    "our", "must", "should", "will", "can", "use", "using", "via", "into", "not",
    "but", "they", "them", "than", "then", "now", "new", "its", "has", "have",
}


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower()) if t not in _STOPWORDS]


def _build_idf(doc_tokens: List[List[str]]) -> Dict[str, float]:
    import math
    from collections import Counter
    df: "Counter" = Counter()
    for toks in doc_tokens:
        for t in set(toks):
            df[t] += 1
    n = max(1, len(doc_tokens))
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def _vec(tokens: List[str], idf: Dict[str, float], default_idf: float = 1.0) -> Dict[str, float]:
    from collections import Counter
    if not tokens:
        return {}
    tf = Counter(tokens)
    n = len(tokens)
    return {t: (cnt / n) * idf.get(t, default_idf) for t, cnt in tf.items()}


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    import math
    if not a or not b:
        return 0.0
    common = a.keys() & b.keys()
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _doc_text(m: dict, title_boost: int = 3) -> str:
    """Title repeated so title hits weigh more than body hits."""
    return (((m.get("title") or "") + " ") * title_boost) + (m.get("body") or m.get("snippet") or "")


def top_matches(root: Path, text: str, kinds: List[str], k: int = 3,
                semantic: bool = False) -> List[Tuple[float, str, str]]:
    """Return up to k (score, id, title) candidates for `text` among active `kinds`.
    Uses the vector index when semantic=True and an index exists; else in-memory TF-IDF."""
    if semantic and _vmeta(root):
        res = semantic_search(root, text, k=k, kinds=kinds, active_only=True)
        return [(r["score"], r["id"], r["title"]) for r in res]
    conn = get_db(root)
    ph = ",".join("?" for _ in kinds)
    rows = conn.execute(
        f"SELECT id,title,body FROM documents WHERE status='active' AND kind IN ({ph})",
        tuple(kinds),
    ).fetchall()
    conn.close()
    if not rows:
        return []
    docs = [{"id": r[0], "title": r[1], "body": r[2]} for r in rows]
    corpus = [tokenize(_doc_text(d)) for d in docs]
    idf = _build_idf(corpus + [tokenize(text)])
    qv = _vec(tokenize(text), idf)
    scored = [(round(_cosine(qv, _vec(t, idf)), 4), d["id"], d["title"]) for d, t in zip(docs, corpus)]
    scored.sort(reverse=True)
    return scored[:k]


def best_match(root: Path, text: str, kinds: List[str], threshold: float = 0.18,
               semantic: bool = False) -> Tuple[Optional[str], float]:
    """Best active memory similar to `text`. Returns (id, score); id None below threshold."""
    tm = top_matches(root, text, kinds, k=1, semantic=semantic)
    if tm and tm[0][0] >= threshold:
        return tm[0][1], tm[0][0]
    return None, (tm[0][0] if tm else 0.0)


def _fts_query(query: str) -> Optional[str]:
    """Quote each term so FTS5 treats it literally (no NEAR/AND/OR injection)."""
    terms = [t for t in re.split(r"\W+", query) if len(t) > 1]
    if not terms:
        return None
    return " OR ".join('"' + t.replace('"', "") + '"' for t in terms)


def make_snippet(body: str, query: str, width: int = 200) -> str:
    body = re.sub(r"\s+", " ", body).strip()
    if not body:
        return ""
    terms = [t.lower() for t in re.split(r"\W+", query) if len(t) > 1]
    low = body.lower()
    # find all term hit positions, then pick the window covering the most hits
    hits = sorted(p for t in terms for p in [low.find(t)] if p != -1)
    if not hits:
        # broaden: any term occurrence anywhere
        hits = sorted(m.start() for t in terms for m in re.finditer(re.escape(t), low)) if terms else []
    if not hits:
        return body[:width] + ("…" if len(body) > width else "")
    best_start, best_count = hits[0], 0
    for h in hits:
        c = sum(1 for x in hits if h <= x < h + width)
        if c > best_count:
            best_count, best_start = c, h
    start = max(0, best_start - width // 4)
    end = min(len(body), start + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(body) else ""
    return f"{prefix}{body[start:end]}{suffix}"


def query_memory(
    root: Path, query: str, limit: int = 10, include_private: bool = True,
    active_only: bool = False, kinds: Optional[List[str]] = None,
    project: str = "", status: str = "", rerank: bool = True,
) -> List[dict]:
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)
    clauses = []
    params: List[object] = []
    if not include_private:
        clauses.append("d.visibility NOT IN ('private','blocked','quarantine')")
    if active_only:
        clauses.append("d.status = 'active'")
    if status:
        clauses.append("d.status = ?")
        params.append(status)
    if kinds:
        clauses.append("d.kind IN (" + ",".join("?" for _ in kinds) + ")")
        params.extend(kinds)
    if project:
        clauses.append("lower(d.project) = lower(?)")
        params.append(project)
    where_extra = (" AND " + " AND ".join(clauses)) if clauses else ""

    cols = ("d.id,d.kind,d.title,d.project,d.visibility,d.status,d.path,d.body,"
            "d.supersedes,d.superseded_by,d.source_receipt")
    # Recall: pull a wider candidate pool from FTS, then re-rank for precision.
    pool = max(limit * 5, 25)
    fts = _fts_query(query)
    rows: List[tuple] = []
    if fts:
        try:
            rows = conn.execute(
                f"""SELECT {cols} FROM documents_fts
                    JOIN documents d ON d.rowid = documents_fts.rowid
                    WHERE documents_fts MATCH ?{where_extra} ORDER BY rank LIMIT ?""",
                (fts, *params, pool),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    if not rows:
        rows = conn.execute(
            f"""SELECT {cols} FROM documents d
                WHERE lower(d.title||' '||d.body||' '||d.project||' '||d.kind) LIKE lower(?){where_extra}
                LIMIT ?""",
            (f"%{query}%", *params, pool),
        ).fetchall()
    conn.close()

    items = [{
        "id": r[0], "kind": r[1], "title": r[2], "project": r[3], "visibility": r[4],
        "status": r[5], "path": r[6], "body": r[7], "snippet": make_snippet(r[7] or "", query),
        "supersedes": r[8], "superseded_by": r[9], "source_receipt": r[10],
    } for r in rows]

    if rerank and items and query.strip():
        corpus = [tokenize(_doc_text(it)) for it in items]
        idf = _build_idf(corpus + [tokenize(query)])
        qv = _vec(tokenize(query), idf)
        for it, toks in zip(items, corpus):
            it["score"] = round(_cosine(qv, _vec(toks, idf)), 4)
        items.sort(key=lambda x: x["score"], reverse=True)
    else:
        for it in items:
            it["score"] = None

    for it in items:
        it.pop("body", None)  # keep body out of the returned/printed payload
    return items[:limit]


def print_query_results(results: List[dict]) -> None:
    if not results:
        print("No matches found.")
        return
    for i, r in enumerate(results, 1):
        tag = f" [SUPERSEDED -> {r['superseded_by']}]" if r["status"] == "superseded" else ""
        score = f"  ·  score {r['score']}" if r.get("score") is not None else ""
        print(f"\n{i}. [{r['kind']}] {r['title']}  ({r['project'] or 'no project'}){tag}{score}")
        print(f"   path: {r['path']}")
        print(f"   visibility: {r['visibility']} | status: {r['status']}")
        if r.get("source_receipt"):
            print(f"   from receipt: {r['source_receipt']}")
        print(f"   {r['snippet']}")


def read_doc(root: Path, rel_path: str) -> str:
    return (root / rel_path).read_text(encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# secret gate
# --------------------------------------------------------------------------- #

def scan_secrets(text: str) -> List[Tuple[str, str]]:
    """Return list of (label, matched_value) for any secrets found."""
    findings: List[Tuple[str, str]] = []
    for label, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            val = m.groupdict().get("val") or m.group(0)
            findings.append((label, val))
    return findings


def redact_text(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    findings: List[Tuple[str, str]] = []
    out = text
    for label, pat in SECRET_PATTERNS:
        def _sub(m):
            val = m.groupdict().get("val") or m.group(0)
            findings.append((label, val))
            whole = m.group(0)
            if "val" in m.groupdict() and m.group("val"):
                return whole.replace(m.group("val"), f"«REDACTED:{label}»")
            return f"«REDACTED:{label}»"
        out = pat.sub(_sub, out)
    return out, findings


# --------------------------------------------------------------------------- #
# pack
# --------------------------------------------------------------------------- #

PACK_PROFILES = ("chatgpt", "claude", "gemini", "deepseek", "codex", "human")
BUDGETS = {  # (max_docs, max_chars)
    "small": (5, 8000),
    "medium": (12, 30000),
    "large": (30, 120000),
}
PROVIDER_FILE = {
    "chatgpt": "CHATGPT_CONTEXT.md", "claude": "CLAUDE_CONTEXT.md",
    "gemini": "GEMINI_CONTEXT.md", "deepseek": "DEEPSEEK_CONTEXT.txt",
    "codex": "CODEX_CONTEXT.md", "human": "HUMAN_CONTEXT.md",
}
# files a valid pack must contain
PACK_REQUIRED = [
    "01_BOOT.md", "02_CONTEXT_BRIEF.md", "03_TASK_CONTEXT.md", "04_MATCHED_MEMORY.md",
    "05_DECISIONS.md", "06_OPEN_GAPS.md", "07_PROMPTS.md", "08_GENERATED_FILES.md",
    "09_DO_NOT_ASSUME.md", "10_SOURCE_MAP.json", "11_MANIFEST.json",
    "12_MEMORY_RECEIPT_TEMPLATE.md",
]
MANIFEST_REQUIRED_KEYS = ["target", "query", "created_at", "redacted", "match_count",
                          "cartridge_id", "cartridge_version"]


def cartridge_meta(root: Path) -> dict:
    cfg = read_json(root / "CARTRIDGE.json", {}) or {}
    cid = cfg.get("cartridge_id")
    if not cid:  # deterministic, stable id for pre-v0.6 cartridges (no file mutation)
        seed = (cfg.get("owner", "") + "|" + cfg.get("created_at", "")).encode("utf-8")
        cid = "cart_" + hashlib.sha256(seed).hexdigest()[:12]
    return {"cartridge_id": cid, "cartridge_version": cfg.get("version", APP_VERSION),
            "owner": cfg.get("owner", "")}


def _provider_context(profile: str, query: str, decisions: List[dict], projects: List[dict],
                      n: int) -> Tuple[str, str]:
    """Return (filename, content) for the active profile's provider file."""
    fname = PROVIDER_FILE.get(profile, "CONTEXT.md")
    dlist = "\n".join(f"- {d['title']}" for d in decisions[:12]) or "- (none in this pack)"
    if profile == "deepseek":  # compact plain text
        body = (f"CARTRIDGE CONTEXT (deepseek)\nQUERY: {query}\nITEMS: {n}\n"
                f"READ 01_BOOT.md FIRST, THEN 02..12 IN ORDER.\n"
                f"DECISIONS:\n{dlist}\n"
                f"DO NOT ASSUME ANYTHING NOT IN 04_MATCHED_MEMORY.md OR 05_DECISIONS.md.\n"
                f"RETURN A MEMORY_RECEIPT AT THE END (SEE 12_MEMORY_RECEIPT_TEMPLATE.md).\n")
        return fname, body
    if profile == "codex":  # code/repo emphasis
        plist = "\n".join(f"- {p['title']}" for p in projects[:12]) or "- (none in this pack)"
        body = (f"# Codex Context\n\nTask query: {query}\n\n"
                f"This pack is a code/engineering context extract. Prioritise project and "
                f"decision records below; treat them as binding constraints on any code you write.\n\n"
                f"## Projects in scope\n{plist}\n\n## Active engineering decisions\n{dlist}\n\n"
                f"Read 01_BOOT.md, then 03_TASK_CONTEXT.md and 05_DECISIONS.md. Do not invent APIs, "
                f"services, or files not present in 04_MATCHED_MEMORY.md / 08_GENERATED_FILES.md. "
                f"Return a MEMORY_RECEIPT at the end.\n")
        return fname, body
    if profile == "human":  # handover narrative
        body = (f"# Handover Note\n\nYou're picking up work related to: **{query}**.\n\n"
                f"This pack is a snapshot of the relevant memory: {n} item(s), including the "
                f"decisions listed below. Start with 02_CONTEXT_BRIEF.md and 03_TASK_CONTEXT.md "
                f"for framing, then 05_DECISIONS.md for what's already settled and "
                f"06_OPEN_GAPS.md / 09_DO_NOT_ASSUME.md for what isn't. The full source for every "
                f"item is under source-files/ and mapped in 10_SOURCE_MAP.json.\n\n"
                f"## Decisions already made\n{dlist}\n")
        return fname, body
    # chatgpt / claude / gemini — standard markdown context view
    body = (f"# {profile.upper()} Context\n\n"
            f"Compact context view for {profile}.\n\nQuery: {query}\nItems in pack: {n}\n\n"
            f"Instructions:\n- Read 01_BOOT.md, then files 02–12 in order.\n"
            f"- Do not assume anything listed in 09_DO_NOT_ASSUME.md exists.\n"
            f"- Treat 05_DECISIONS.md as settled unless the user says otherwise.\n"
            f"- Return a MEMORY_RECEIPT at the end (grammar in 12_MEMORY_RECEIPT_TEMPLATE.md).\n")
    return fname, body


def _scan_dir_for_secrets(tmp: Path) -> Dict[str, List[Tuple[str, str]]]:
    hits: Dict[str, List[Tuple[str, str]]] = {}
    for p in tmp.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".md", ".json", ".txt"}:
            f = scan_secrets(p.read_text(encoding="utf-8", errors="replace"))
            if f:
                hits[str(p.relative_to(tmp))] = f
    return hits


def _redact_dir(tmp: Path) -> int:
    n = 0
    for p in tmp.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".md", ".json", ".txt"}:
            red, finds = redact_text(p.read_text(encoding="utf-8", errors="replace"))
            if finds:
                p.write_text(red, encoding="utf-8")
                n += len(finds)
    return n


def pack_context(
    root: Path, query: str, target: str, out: Path, limit: int = 12,
    include_private: bool = False, include_superseded: bool = False,
    redact: bool = False, allow_secrets: bool = False,
    budget: str = "", max_docs: Optional[int] = None, max_chars: Optional[int] = None,
    allow_blocked: bool = False, enforce_policy: bool = False,
) -> dict:
    ensure_root(root)
    profile = target if target in PACK_PROFILES else "chatgpt"
    b_docs, b_chars = BUDGETS.get(budget, BUDGETS["medium"])
    eff_max_docs = max_docs if max_docs is not None else (b_docs if budget else limit)
    eff_max_chars = max_chars if max_chars is not None else b_chars

    matches = query_memory(root, query, limit=eff_max_docs,
                           include_private=include_private,
                           active_only=not include_superseded)

    # --- visibility gate: blocked never leaves unless explicitly allowed ---
    policy = load_policy(root) if enforce_policy else None
    kept, dropped = [], []
    for m in matches:
        vis = m.get("visibility", "private")
        if vis == "blocked" and not allow_blocked:
            dropped.append((m, "blocked")); continue
        if policy:
            allowed = policy.get("allowed_export_visibility", [])
            if allowed and vis not in allowed:
                dropped.append((m, f"policy:not-in-allowed({vis})")); continue
        kept.append(m)
    if dropped:
        append_ledger(root, "policy.export_filtered", {
            "query": query, "target": profile, "enforce_policy": enforce_policy,
            "allow_blocked": allow_blocked,
            "dropped": [{"id": m["id"], "visibility": m.get("visibility"), "reason": r} for m, r in dropped],
        })
    matches = kept
    meta = cartridge_meta(root)

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = root / "exports" / f"tmp-pack-{uuid.uuid4().hex}"
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "source-files").mkdir(parents=True)
    (tmp / "provider").mkdir()

    _pack_dropped = dropped  # surfaced in DO_NOT_ASSUME below

    # --- assemble source files under a character budget ---
    chars_used = 0
    omitted = 0
    source_map = []
    matched_lines = ["# Matched Memory\n"]
    for idx, m in enumerate(matches, 1):
        text = read_doc(root, m["path"])
        snippet = m.get("snippet") or ""
        if redact:
            text, _ = redact_text(text)
            snippet, _ = redact_text(snippet)
        included = True
        reason = ""
        if chars_used >= eff_max_chars and idx > 1:
            included = False
            reason = "char budget"
            omitted += 1
        elif chars_used + len(text) > eff_max_chars:
            keep = max(0, eff_max_chars - chars_used)
            text = text[:keep] + "\n\n…[truncated for pack budget]\n"
            chars_used += len(text)
            reason = "truncated for budget"
        else:
            chars_used += len(text)
        safe_name = f"{idx:02d}_{slugify(m['kind'])}_{slugify(m['title'])}.md"
        if included:
            (tmp / "source-files" / safe_name).write_text(text, encoding="utf-8")
            matched_lines.append(f"\n## {idx}. [{m['kind']}] {m['title']}"
                                 + (f"  ·  score {m['score']}" if m.get("score") is not None else "") + "\n")
            if m.get("project"):
                matched_lines.append(f"Project: {m['project']}\n")
            matched_lines.append(f"Source: `source-files/{safe_name}`"
                                 + (f"  ({reason})" if reason else "") + "\n\n")
            matched_lines.append(snippet + "\n")
        source_map.append({
            "id": m["id"], "kind": m["kind"], "title": m["title"], "project": m.get("project", ""),
            "visibility": m.get("visibility", ""), "status": m.get("status", ""),
            "source_path": m["path"], "pack_file": f"source-files/{safe_name}" if included else "",
            "included": included, "reason": reason,
        })

    decisions = [m for m in matches if m["kind"] == "decision"]
    projects = [m for m in matches if m["kind"] == "project"]
    prompts = [m for m in matches if m["kind"] == "prompt"]
    gen_files = [m for m in matches if m["kind"] == "file"]

    # open gaps + open corrections are global safety context (gated below like everything else)
    open_gaps = query_memory(root, query or "gap", limit=20, include_private=include_private,
                             kinds=["gap"])
    open_gaps = [g for g in open_gaps if g["status"] in ("open", "active")]
    open_corr = [c for c in query_memory(root, query or "correction", limit=20,
                                         include_private=include_private, kinds=["correction"])
                 if c["status"] == "open"]

    # --- write the 12 ordered files ---
    read_order = "\n".join(f"{i+1}. `{name}`" for i, name in enumerate(PACK_REQUIRED))
    (tmp / "01_BOOT.md").write_text(
        "# BOOT — read this first\n\n"
        "You are reading a portable AI memory cartridge context pack. Read the files in this "
        "exact order before doing anything else:\n\n" + read_order + "\n\n"
        "Rules:\n- Treat 05_DECISIONS.md as already settled unless the user explicitly changes them.\n"
        "- Do NOT assume anything listed in 09_DO_NOT_ASSUME.md exists.\n"
        "- Every claim you rely on should trace to an item in 10_SOURCE_MAP.json.\n"
        "- At the end of substantial work, return a MEMORY_RECEIPT (see 12).\n", encoding="utf-8")

    (tmp / "02_CONTEXT_BRIEF.md").write_text(
        f"# Context Brief\n\n**Query:** {query}\n\n**Target profile:** {profile}\n\n"
        f"**Cartridge:** {meta['cartridge_id']} (v{meta['cartridge_version']})\n\n"
        f"This is a focused extract from a larger personal memory cartridge — {len(matches)} matched "
        f"item(s). Superseded memories are excluded unless explicitly included.\n", encoding="utf-8")

    (tmp / "03_TASK_CONTEXT.md").write_text(
        f"# Task Context\n\n## Your task\n\n{query}\n\n## How to use this pack\n\n"
        f"Use the matched memory and decisions as binding working context. If something needed "
        f"for the task is not present here, say so rather than inventing it (see 09_DO_NOT_ASSUME.md).\n",
        encoding="utf-8")

    (tmp / "04_MATCHED_MEMORY.md").write_text("\n".join(matched_lines), encoding="utf-8")

    dec_md = ["# Decisions\n"]
    for d in decisions:
        dec_md.append(f"\n## {d['title']}\n")
        if d.get("project"):
            dec_md.append(f"Project: {d['project']}\n")
        dec_md.append((redact_text(d.get('snippet') or '')[0] if redact else (d.get('snippet') or '')) + "\n")
    if not decisions:
        dec_md.append("\n(no decisions matched this query)\n")
    (tmp / "05_DECISIONS.md").write_text("\n".join(dec_md), encoding="utf-8")

    gaps_md = ["# Open Gaps\n"]
    for g in open_gaps:
        gaps_md.append(f"- {g['title']}\n")
    if not open_gaps:
        gaps_md.append("\n(no open gaps recorded)\n")
    (tmp / "06_OPEN_GAPS.md").write_text("".join(gaps_md), encoding="utf-8")

    pr_md = ["# Prompts\n"]
    for p in prompts:
        pr_md.append(f"\n## {p['title']}\n")
        pr_md.append((redact_text(p.get('snippet') or '')[0] if redact else (p.get('snippet') or '')) + "\n")
    if not prompts:
        pr_md.append("\n(no prompts matched this query)\n")
    (tmp / "07_PROMPTS.md").write_text("\n".join(pr_md), encoding="utf-8")

    gf_md = ["# Generated Files\n"]
    for f in gen_files:
        gf_md.append(f"- **{f['title']}** — `{f['path']}`\n")
    if not gen_files:
        gf_md.append("\n(no generated-file records matched this query)\n")
    (tmp / "08_GENERATED_FILES.md").write_text("".join(gf_md), encoding="utf-8")

    dna = ["# Do Not Assume\n",
           "The following are unproven, missing, or unresolved. Do not assume them or invent details:\n\n"]
    for g in open_gaps:
        dna.append(f"- Open gap: {g['title']}\n")
    for cc in open_corr:
        dna.append(f"- Unresolved correction: {cc['title']}\n")
    if omitted:
        dna.append(f"- {omitted} matched item(s) were omitted from this pack for budget; do not assume their contents.\n")
    if _pack_dropped:
        dna.append(f"- {len(_pack_dropped)} item(s) were withheld by visibility/policy and are intentionally absent.\n")
    dna.append("- Anything not present in 04_MATCHED_MEMORY.md, 05_DECISIONS.md or source-files/.\n")
    (tmp / "09_DO_NOT_ASSUME.md").write_text("".join(dna), encoding="utf-8")

    write_json(tmp / "10_SOURCE_MAP.json", {
        "cartridge_id": meta["cartridge_id"], "cartridge_version": meta["cartridge_version"],
        "query": query, "matches": source_map,
    })

    manifest = {
        "schema": "ai-memory-context-pack.v1", "created_at": now_iso(),
        "target": profile, "query": query,
        "cartridge_id": meta["cartridge_id"], "cartridge_version": meta["cartridge_version"],
        "app_version": APP_VERSION, "include_private": include_private,
        "include_superseded": include_superseded, "redacted": redact,
        "match_count": len(matches), "docs_selected": sum(1 for s in source_map if s["included"]),
        "docs_omitted_for_budget": omitted, "budget": budget or "medium",
        "policy_enforced": enforce_policy, "allow_blocked": allow_blocked,
        "withheld_by_policy": len(_pack_dropped),
        "max_docs": eff_max_docs, "chars_budget": eff_max_chars, "chars_used": chars_used,
        "read_order": PACK_REQUIRED,
        "instructions": "Read 01_BOOT.md first; read 02–12 in order. Return MEMORY_RECEIPT at the end.",
    }
    write_json(tmp / "11_MANIFEST.json", manifest)

    (tmp / "12_MEMORY_RECEIPT_TEMPLATE.md").write_text(
        "# MEMORY_RECEIPT\n\n## New decisions\n- Short title :: Optional body [project: Name]\n\n"
        "## Corrections\n- What changed and what is now true [ref: <existing-memory-id>]\n\n"
        "## Generated files\n- filename.ext :: what it is\n\n"
        "## Open gaps\n- Something still unresolved\n\n"
        "## Suggested memory updates\n- A non-binding suggestion\n", encoding="utf-8")

    fname, pcontent = _provider_context(profile, query, decisions, projects, len(matches))
    (tmp / "provider" / fname).write_text(pcontent, encoding="utf-8")

    # --- final secret gate over EVERYTHING that will be zipped ---
    redactions = 0
    if redact:
        redactions = _redact_dir(tmp)
    hits = _scan_dir_for_secrets(tmp)
    if hits and not allow_secrets:
        if redact:
            redactions += _redact_dir(tmp)
            hits = _scan_dir_for_secrets(tmp)
        if hits:
            print("PACK BLOCKED: secrets detected in content that would be exported.\n")
            for path, finds in hits.items():
                print(f"  {path}")
                for label, val in finds:
                    print(f"     - {label}: {(val[:6] + '…') if len(val) > 7 else val}")
            print("\nChoose: --redact (mask in export; source untouched) or --allow-secrets (override).")
            append_ledger(root, "context_pack.blocked", {"query": query, "offending": list(hits.keys())})
            shutil.rmtree(tmp)
            raise SystemExit(2)

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(tmp.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(tmp))
    pack_size = out.stat().st_size
    shutil.rmtree(tmp)

    append_ledger(root, "context_pack.exported", {
        "query": query, "target": profile, "output": str(out), "match_count": len(matches),
        "redactions": redactions, "chars_used": chars_used, "size_bytes": pack_size,
        "cartridge_id": meta["cartridge_id"],
    })
    print(f"Created context pack: {out}")
    print(f"  profile: {profile} · matched: {len(matches)} · included: {manifest['docs_selected']}"
          + (f" · omitted(budget): {omitted}" if omitted else ""))
    print(f"  chars: {chars_used}/{eff_max_chars} · size: {pack_size} bytes"
          + (f" · redactions: {redactions}" if redactions else ""))
    return manifest


def validate_pack(zip_path: Path) -> dict:
    """Check a pack zip is structurally valid and self-contained."""
    issues = []
    if not zip_path.exists():
        raise SystemExit(f"Pack not found: {zip_path}")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            for req in PACK_REQUIRED:
                if req not in names:
                    issues.append(f"missing required file: {req}")
            if "11_MANIFEST.json" in names:
                try:
                    man = json.loads(zf.read("11_MANIFEST.json"))
                    for k in MANIFEST_REQUIRED_KEYS:
                        if k not in man:
                            issues.append(f"manifest missing key: {k}")
                except json.JSONDecodeError:
                    issues.append("11_MANIFEST.json is not valid JSON")
            if "10_SOURCE_MAP.json" in names:
                try:
                    sm = json.loads(zf.read("10_SOURCE_MAP.json"))
                    if "matches" not in sm:
                        issues.append("source map missing 'matches'")
                    else:
                        for e in sm["matches"]:
                            if not e.get("id") or not e.get("source_path"):
                                issues.append("source map entry missing id/source_path")
                                break
                except json.JSONDecodeError:
                    issues.append("10_SOURCE_MAP.json is not valid JSON")
    except zipfile.BadZipFile:
        issues.append("not a valid zip file")
    ok = not issues
    print(("PASS" if ok else "FAIL") + f": {zip_path}")
    for i in issues:
        print(f"  - {i}")
    return {"ok": ok, "issues": issues}


def explain_pack(zip_path: Path) -> dict:
    if not zip_path.exists():
        raise SystemExit(f"Pack not found: {zip_path}")
    size = zip_path.stat().st_size
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        man = json.loads(zf.read("11_MANIFEST.json")) if "11_MANIFEST.json" in names else {}
        sm = json.loads(zf.read("10_SOURCE_MAP.json")) if "10_SOURCE_MAP.json" in names else {"matches": []}
    print(f"Pack: {zip_path}  ({size} bytes)")
    print(f"  target profile : {man.get('target')}")
    print(f"  query          : {man.get('query')}")
    print(f"  created        : {man.get('created_at')}")
    print(f"  cartridge      : {man.get('cartridge_id')} (v{man.get('cartridge_version')})")
    print(f"  redacted       : {man.get('redacted')}")
    print(f"  matched/incl   : {man.get('match_count')} / {man.get('docs_selected')}"
          + (f" (omitted {man.get('docs_omitted_for_budget')})" if man.get('docs_omitted_for_budget') else ""))
    print(f"  char budget    : {man.get('chars_used')}/{man.get('chars_budget')}")
    print("  read order     : " + " → ".join(man.get("read_order", [])[:4]) + " → …")
    print("  included items :")
    for e in sm.get("matches", []):
        if e.get("included"):
            print(f"    - [{e['kind']}] {e['title']}  ({e['id']})  ⟵ {e['source_path']}")
    return {"manifest": man, "size": size}


# --------------------------------------------------------------------------- #
# absorb (the real one)
# --------------------------------------------------------------------------- #

_TAG_RE = re.compile(r"\[(?P<key>[a-zA-Z_]+)\s*:\s*(?P<val>[^\]]+)\]")


def _parse_bullet(line: str) -> dict:
    """Parse one receipt bullet into {title, body, project, ref}."""
    line = line.strip()
    line = re.sub(r"^[-*]\s+", "", line)
    tags = {m.group("key").lower(): m.group("val").strip() for m in _TAG_RE.finditer(line)}
    text = _TAG_RE.sub("", line).strip()
    if "::" in text:
        title, body = text.split("::", 1)
        title, body = title.strip(), body.strip()
    else:
        title, body = text, text
    if len(title) > 90:
        title = title[:90].rstrip() + "…"
    return {"title": title or "(untitled)", "body": body, "project": tags.get("project", ""), "ref": tags.get("ref", "")}


def parse_receipt(text: str) -> Dict[str, List[dict]]:
    """Parse a MEMORY_RECEIPT markdown blob into typed, structured items."""
    sections: Dict[str, List[dict]] = {v: [] for v in RECEIPT_SECTIONS.values()}
    current: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        h = re.match(r"^#{1,6}\s+(.*)$", line)
        if h:
            name = h.group(1).strip().lower()
            current = RECEIPT_SECTIONS.get(name)
            continue
        if current and re.match(r"^\s*[-*]\s+", line):
            bullet = _parse_bullet(line)
            # ignore empty placeholder bullets like "- ..." or "- "
            if bullet["title"] in {"...", "(untitled)", ""} and not bullet["body"].strip("."):
                continue
            sections[current].append(bullet)
    return sections


def absorb_receipt(root: Path, receipt_path: Path, dry_run: bool = False) -> dict:
    ensure_root(root)
    if not receipt_path.exists():
        raise SystemExit(f"Receipt not found: {receipt_path}")
    text = receipt_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_receipt(text)

    summary = {"decisions": 0, "corrections_applied": 0, "corrections_unmatched": 0,
               "files": 0, "gaps": 0, "suggestions": 0, "actions": []}

    if dry_run:
        print("DRY RUN — nothing will be written.\n")
        for sect, items in parsed.items():
            for it in items:
                print(f"  [{sect}] {it['title']}" + (f"  (ref:{it['ref']})" if it["ref"] else ""))
        return summary

    # 1. Store the raw receipt as a provenance anchor.
    receipt_title = f"Receipt {receipt_path.stem}"
    receipt_doc = add_memory(root, "receipt", receipt_title, text, project="",
                             visibility="private", reindex=False, quiet=True)
    receipt_meta, _ = parse_frontmatter(receipt_doc.read_text(encoding="utf-8"))
    receipt_id = receipt_meta["id"]

    # 2. New decisions -> typed decision memories with provenance.
    for it in parsed["decision"]:
        add_memory(root, "decision", it["title"], it["body"], project=it["project"],
                   visibility="private", extra_meta={"source_receipt": receipt_id},
                   reindex=False, quiet=True)
        summary["decisions"] += 1
        summary["actions"].append(f"decision: {it['title']}")

    # 3. Corrections -> create the corrected belief, then supersede the old one.
    rebuild_index(root, force=True)  # make new decisions searchable for matching
    for it in parsed["correction"]:
        new_path = add_memory(root, "correction", it["title"], it["body"], project=it["project"],
                              visibility="private", extra_meta={"source_receipt": receipt_id},
                              reindex=False, quiet=True)
        rebuild_index(root, force=True)
        new_meta, _ = parse_frontmatter(new_path.read_text(encoding="utf-8"))
        new_id = new_meta["id"]

        target_id = it["ref"]
        match_score = None
        if not target_id:
            # similarity match against active decisions/projects/notes
            target_id, match_score = best_match(
                root, it["title"] + " " + it["body"],
                kinds=["decision", "project", "note"], threshold=0.18,
            )

        if target_id and supersede(root, target_id, new_id, reason=it["title"]):
            update_doc_meta(root, str(new_path.relative_to(root)),
                            {"match_score": match_score if match_score is not None else "ref"})
            summary["corrections_applied"] += 1
            summary["actions"].append(f"correction superseded {target_id} (score={match_score})")
        else:
            update_doc_meta(root, str(new_path.relative_to(root)),
                            {"status": "open", "best_candidate_score": match_score})
            summary["corrections_unmatched"] += 1
            summary["actions"].append(f"correction (unmatched, left open; best={match_score}): {it['title']}")

    # 4. Generated files, 5. gaps, 6. suggestions.
    for it in parsed["file"]:
        add_memory(root, "file", it["title"], it["body"], project=it["project"],
                   visibility="private", extra_meta={"source_receipt": receipt_id},
                   reindex=False, quiet=True)
        summary["files"] += 1
    for it in parsed["gap"]:
        add_memory(root, "gap", it["title"], it["body"], project=it["project"],
                   visibility="private", extra_meta={"source_receipt": receipt_id, "status": "open"},
                   reindex=False, quiet=True)
        summary["gaps"] += 1
    for it in parsed["suggestion"]:
        add_memory(root, "suggestion", it["title"], it["body"], project=it["project"],
                   visibility="private", extra_meta={"source_receipt": receipt_id, "status": "suggested"},
                   reindex=False, quiet=True)
        summary["suggestions"] += 1

    rebuild_index(root, force=True)
    append_ledger(root, "receipt.absorbed", {
        "source": str(receipt_path), "receipt_id": receipt_id,
        "stored_as": str(receipt_doc.relative_to(root)), "summary": {k: v for k, v in summary.items() if k != "actions"},
    })

    print("Absorbed memory receipt:")
    print(f"  decisions added:        {summary['decisions']}")
    print(f"  corrections applied:    {summary['corrections_applied']}")
    print(f"  corrections unmatched:  {summary['corrections_unmatched']} (saved as open items for review)")
    print(f"  generated files logged: {summary['files']}")
    print(f"  open gaps logged:       {summary['gaps']}")
    print(f"  suggestions logged:     {summary['suggestions']}")
    return summary


# --------------------------------------------------------------------------- #
# embeddings + vector index (a persistent on-disk vector DB in SQLite)
#
# Two pluggable backends share one interface:
#   - "tfidf": pure stdlib, zero-dependency, works fully offline (default).
#   - "st":    sentence-transformers (local model on your machine), optional.
# Vectors are stored uniformly as {dimension_key: weight} dicts so the same
# cosine works for sparse (tfidf) and dense (st) representations. The index is
# rebuildable from source at any time — consistent with the cartridge principle
# that indexes are derived, not truth.
# --------------------------------------------------------------------------- #

VECTOR_DB = "indexes/vectors.sqlite"


class TfidfEmbedder:
    name = "tfidf"

    def __init__(self):
        self.idf: Dict[str, float] = {}

    def fit(self, texts: List[str]) -> "TfidfEmbedder":
        self.idf = _build_idf([tokenize(t) for t in texts])
        return self

    def embed(self, text: str) -> Dict[str, float]:
        return _vec(tokenize(text), self.idf)

    def embed_many(self, texts: List[str]) -> List[Dict[str, float]]:
        return [self.embed(t) for t in texts]


class STEmbedder:
    name = "st"

    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer  # optional dependency
        self.model_name = model
        self._m = SentenceTransformer(model)

    def embed_many(self, texts: List[str]) -> List[Dict[str, float]]:
        arr = self._m.encode(texts, normalize_embeddings=True)
        return [{str(i): float(x) for i, x in enumerate(row)} for row in arr]

    def embed(self, text: str) -> Dict[str, float]:
        return self.embed_many([text])[0]


def get_embedder(backend: str, model: str = "all-MiniLM-L6-v2"):
    if backend == "tfidf":
        return TfidfEmbedder()
    if backend in ("st", "sentence-transformers"):
        try:
            return STEmbedder(model)
        except ImportError:
            raise SystemExit(
                "Backend 'st' needs sentence-transformers.\n"
                "Install on your machine:  pip install sentence-transformers\n"
                "(it runs a local model — nothing leaves your machine — but is not bundled "
                "so the cartridge stays zero-dependency by default.)"
            )
    raise SystemExit(f"Unknown embedding backend: {backend}")


def build_vector_index(root: Path, backend: str = "tfidf", model: str = "all-MiniLM-L6-v2") -> dict:
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)
    rows = conn.execute("SELECT id,kind,status,title,body FROM documents").fetchall()
    conn.close()
    texts = [_doc_text({"title": r[3], "body": r[4]}) for r in rows]
    emb = get_embedder(backend, model)
    idf_json = ""
    if isinstance(emb, TfidfEmbedder):
        emb.fit(texts)
        idf_json = json.dumps(emb.idf)
    vecs = emb.embed_many(texts) if rows else []
    dim = len(emb.idf) if isinstance(emb, TfidfEmbedder) else (len(vecs[0]) if vecs else 0)

    vdb = root / VECTOR_DB
    if vdb.exists():
        vdb.unlink()
    vc = sqlite3.connect(str(vdb))
    vc.executescript(
        "CREATE TABLE vectors(id TEXT PRIMARY KEY, kind TEXT, status TEXT, vec TEXT);"
        "CREATE TABLE vmeta(backend TEXT, model TEXT, dim INT, idf TEXT, built_at TEXT, count INT);"
    )
    for r, v in zip(rows, vecs):
        vc.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)",
                   (r[0], r[1], r[2], json.dumps(v)))
    vc.execute("INSERT INTO vmeta VALUES (?,?,?,?,?,?)",
               (getattr(emb, "name", backend), getattr(emb, "model_name", ""),
                dim, idf_json, now_iso(), len(rows)))
    vc.commit()
    vc.close()
    append_ledger(root, "vector_index.built", {"backend": backend, "dim": dim, "count": len(rows)})
    return {"backend": getattr(emb, "name", backend), "dim": dim, "count": len(rows)}


def _vmeta(root: Path) -> Optional[dict]:
    vdb = root / VECTOR_DB
    if not vdb.exists():
        return None
    vc = sqlite3.connect(str(vdb))
    try:
        row = vc.execute("SELECT backend,model,dim,idf,built_at,count FROM vmeta").fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        vc.close()
    if not row:
        return None
    return {"backend": row[0], "model": row[1], "dim": row[2], "idf": row[3],
            "built_at": row[4], "count": row[5]}


def semantic_search(root: Path, query: str, k: int = 10, kinds: Optional[List[str]] = None,
                    active_only: bool = False, project: str = "") -> List[dict]:
    meta = _vmeta(root)
    if not meta:
        raise SystemExit("No vector index yet. Build one:  cartridge.py --root <root> embed")
    if meta["backend"] == "tfidf":
        emb = TfidfEmbedder()
        emb.idf = json.loads(meta["idf"] or "{}")
        qv = emb.embed(query)
    else:
        qv = get_embedder("st", meta["model"] or "all-MiniLM-L6-v2").embed(query)

    vc = sqlite3.connect(str(root / VECTOR_DB))
    vrows = vc.execute("SELECT id,kind,status,vec FROM vectors").fetchall()
    vc.close()
    scored = []
    for rid, kind, status, vec in vrows:
        if active_only and status != "active":
            continue
        if kinds and kind not in kinds:
            continue
        s = _cosine(qv, json.loads(vec))
        if s > 0:
            scored.append((s, rid, kind, status))
    scored.sort(reverse=True)

    rebuild_index(root)
    conn = get_db(root)
    out = []
    for s, rid, kind, status in scored:
        d = conn.execute(
            "SELECT title,project,visibility,path,body,supersedes,superseded_by,source_receipt "
            "FROM documents WHERE id=?", (rid,)).fetchone()
        if not d:
            continue
        if project and (d[1] or "").lower() != project.lower():
            continue
        out.append({"id": rid, "kind": kind, "title": d[0], "project": d[1],
                    "visibility": d[2], "status": status, "path": d[3],
                    "snippet": make_snippet(d[4] or "", query),
                    "supersedes": d[5], "superseded_by": d[6], "source_receipt": d[7],
                    "score": round(s, 4)})
        if len(out) >= k:
            break
    conn.close()
    return out


# --------------------------------------------------------------------------- #
# resolve — close out corrections that absorb left "open"
# --------------------------------------------------------------------------- #

def list_open_corrections(root: Path) -> List[dict]:
    conn = get_db(root)
    rows = conn.execute(
        "SELECT id,title,body,path FROM documents WHERE kind='correction' AND status='open'"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "body": r[2], "path": r[3]} for r in rows]


def resolve(root: Path, correction: str = "", target: str = "", dismiss: bool = False,
            auto: bool = False, threshold: float = 0.18, semantic: bool = False) -> dict:
    ensure_root(root)
    rebuild_index(root)
    result = {"applied": 0, "dismissed": 0, "still_open": 0}

    def _correction_rel(cid: str) -> Optional[str]:
        rel = find_doc_by_id(root, cid)
        if not rel:
            raise SystemExit(f"Correction not found: {cid}")
        return rel

    # explicit apply
    if correction and target:
        if not supersede(root, target, correction, reason="manual resolve"):
            raise SystemExit(f"Target not found: {target}")
        update_doc_meta(root, _correction_rel(correction), {"status": "active", "resolved": "manual"})
        rebuild_index(root, force=True)
        append_ledger(root, "correction.resolved", {"correction": correction, "target": target, "mode": "manual"})
        print(f"Resolved: {correction} now supersedes {target}.")
        result["applied"] = 1
        return result

    # explicit dismiss (keep correction as a standalone active memory, supersedes nothing)
    if correction and dismiss:
        update_doc_meta(root, _correction_rel(correction), {"status": "active", "resolved": "dismissed"})
        rebuild_index(root, force=True)
        append_ledger(root, "correction.resolved", {"correction": correction, "mode": "dismissed"})
        print(f"Dismissed: {correction} kept as a standalone memory (supersedes nothing).")
        result["dismissed"] = 1
        return result

    # auto: re-match every open correction with the best available matcher
    if auto:
        for oc in list_open_corrections(root):
            tid, score = best_match(root, oc["title"] + " " + oc["body"],
                                    kinds=["decision", "project", "note"],
                                    threshold=threshold, semantic=semantic)
            if tid and supersede(root, tid, oc["id"], reason="auto resolve"):
                update_doc_meta(root, find_doc_by_id(root, oc["id"]),
                                {"status": "active", "resolved": f"auto:{score}"})
                rebuild_index(root, force=True)
                append_ledger(root, "correction.resolved",
                              {"correction": oc["id"], "target": tid, "mode": "auto", "score": score})
                result["applied"] += 1
                print(f"  auto-resolved {oc['id']} -> supersedes {tid} (score {score})")
            else:
                result["still_open"] += 1
        print(f"Auto-resolve: {result['applied']} applied, {result['still_open']} still open "
              f"({'semantic' if semantic else 'tfidf'} backend, threshold {threshold}).")
        return result

    # default: list open corrections with candidate targets to choose from
    open_items = list_open_corrections(root)
    if not open_items:
        print("No open corrections. Nothing to resolve.")
        return result
    result["still_open"] = len(open_items)
    print(f"{len(open_items)} open correction(s):\n")
    for oc in open_items:
        print(f"• {oc['title']}")
        print(f"  id: {oc['id']}")
        cands = top_matches(root, oc["title"] + " " + oc["body"],
                            kinds=["decision", "project", "note"], k=3, semantic=semantic)
        if cands:
            print("  candidate targets:")
            for score, cid, ctitle in cands:
                print(f"    [{score}] {ctitle}  ({cid})")
        else:
            print("  candidate targets: none found")
        print(f"  apply:   resolve --correction {oc['id']} --target <id>")
        print(f"  dismiss: resolve --correction {oc['id']} --dismiss\n")
    return result


# --------------------------------------------------------------------------- #
# audit / heal / status
# --------------------------------------------------------------------------- #

def _all_docs_meta(root: Path) -> List[Tuple[Path, dict, str]]:
    out = []
    for p in iter_source_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        out.append((p, meta, body))
    return out


def index_is_stale(root: Path) -> bool:
    state = read_json(root / "indexes" / "index_state.json", {})
    return state.get("fingerprint") != corpus_fingerprint(root)


def vector_index_stale(root: Path) -> Optional[bool]:
    """True/False if a vector index exists, else None (no index = not applicable)."""
    vm = _vmeta(root)
    if not vm:
        return None
    conn = get_db(root)
    n_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    return vm.get("count") != n_docs


def audit(root: Path) -> dict:
    ensure_root(root)
    rebuild_index(root)
    report = {"time": now_iso(), "checks": [], "issues": [], "summary": {}}
    docs = _all_docs_meta(root)
    all_ids = {m.get("id") for _, m, _ in docs if m.get("id")}
    ids: Dict[str, str] = {}
    titles: Dict[str, List[str]] = {}

    def add(sev, typ, **extra):
        report["issues"].append({"severity": sev, "type": typ, **extra})

    for p, meta, body in docs:
        rel = str(p.relative_to(root))
        # frontmatter / id
        if not meta.get("id") or not meta.get("type"):
            add("medium", "missing_frontmatter_or_id", path=rel)
        doc_id = meta.get("id")
        if doc_id:
            if doc_id in ids:
                add("high", "duplicate_id", id=doc_id, paths=[ids[doc_id], rel])
            else:
                ids[doc_id] = rel
        # duplicate titles (within same kind+project)
        key = f"{meta.get('type','')}|{meta.get('project','')}|{(meta.get('title') or '').strip().lower()}"
        titles.setdefault(key, []).append(rel)
        # secrets
        finds = scan_secrets(p.read_text(encoding="utf-8", errors="replace"))
        if finds:
            shareable = meta.get("visibility", "private") in SHAREABLE_VIS
            add("high" if shareable else "medium",
                "secret_in_shareable" if shareable else "secret_in_source",
                path=rel, labels=sorted({l for l, _ in finds}))
        # supersession links
        sb = meta.get("superseded_by")
        if sb and sb not in all_ids:
            add("medium", "dangling_superseded_by", path=rel, missing_id=sb)
        # superseded item that is still marked exportable (would leak retired info)
        if meta.get("status") == "superseded" and meta.get("visibility") in SHAREABLE_VIS:
            add("medium", "superseded_still_exportable", path=rel)
        # generated file with no attached_file / source linkage
        if meta.get("type") == "file" and not meta.get("attached_file") \
                and not meta.get("source_path") and not meta.get("source_receipt"):
            add("low", "generated_file_without_source", path=rel)
        # open corrections / unresolved suggestions
        if meta.get("type") == "correction" and meta.get("status") == "open":
            add("low", "open_correction", path=rel, id=doc_id)
        if meta.get("type") == "suggestion" and meta.get("status") == "suggested":
            add("low", "unresolved_suggestion", path=rel, id=doc_id)

    for key, paths in titles.items():
        if len(paths) > 1:
            add("low", "duplicate_title", title=key.split("|", 2)[2], paths=paths)

    # cartridge-level checks
    if not (root / "BOOT.md").exists():
        add("medium", "missing_boot")
    if index_is_stale(root):
        add("low", "stale_fts_index")
    vstale = vector_index_stale(root)
    if vstale is True:
        add("low", "vector_index_out_of_date")
    # ledger health
    led = verify_ledger(root, quiet=True)
    if led["bad_rows"]:
        add("medium", "corrupt_ledger_rows", count=led["bad_rows"], lines=led["bad_lines"][:10])
    # export packs missing manifests
    for zp in (root / "exports").glob("*.zip"):
        try:
            with zipfile.ZipFile(zp) as zf:
                if "11_MANIFEST.json" not in zf.namelist() and "MANIFEST.json" not in zf.namelist():
                    add("low", "pack_missing_manifest", path=str(zp.relative_to(root)))
        except zipfile.BadZipFile:
            add("low", "corrupt_pack", path=str(zp.relative_to(root)))

    report["checks"] = [
        "frontmatter_and_ids", "duplicate_ids", "duplicate_titles", "secrets_in_source",
        "supersession_links", "superseded_exportable", "generated_file_sources",
        "open_corrections", "unresolved_suggestions", "missing_boot", "stale_fts_index",
        "vector_index_freshness", "ledger_integrity", "pack_manifests",
    ]
    report["summary"] = {
        "source_files": len(docs), "issues": len(report["issues"]),
        "high_issues": sum(1 for i in report["issues"] if i.get("severity") == "high"),
        "by_type": {t: sum(1 for i in report["issues"] if i["type"] == t)
                    for t in {i["type"] for i in report["issues"]}},
    }
    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    write_json(reports_dir / "AUDIT_REPORT.json", report)
    md = ["# Audit Report\n", f"Time: {report['time']}\n", f"Source files: {len(docs)}\n",
          f"Issues: {len(report['issues'])} (high: {report['summary']['high_issues']})\n"]
    for issue in sorted(report["issues"], key=lambda i: {"high": 0, "medium": 1, "low": 2}.get(i["severity"], 3)):
        rest = {k: v for k, v in issue.items() if k not in {"severity", "type"}}
        md.append(f"\n- **{issue['severity']}** `{issue['type']}`: {json.dumps(rest)}\n")
    (reports_dir / "AUDIT_REPORT.md").write_text("".join(md), encoding="utf-8")
    append_ledger(root, "audit.completed", report["summary"])
    return report


def verify_ledger(root: Path, quiet: bool = False) -> dict:
    """Check every ledger row is valid JSON with the required fields."""
    ensure_root(root)
    path = root / "ledger" / "events.jsonl"
    good, bad_lines = 0, []
    if path.exists():
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if "event" in row and "time" in row:
                    good += 1
                else:
                    bad_lines.append(i)
            except json.JSONDecodeError:
                bad_lines.append(i)
    result = {"good_rows": good, "bad_rows": len(bad_lines), "bad_lines": bad_lines}
    if not quiet:
        print(f"Ledger: {good} valid row(s), {len(bad_lines)} bad row(s).")
        if bad_lines:
            print(f"  bad line numbers: {bad_lines[:20]}")
    return result


def build_repair_plan(root: Path) -> dict:
    """Derive a human-readable, safe repair plan from the current audit. No changes made."""
    report = audit(root)
    actions = []
    docs = {str(p.relative_to(root)): (p, m) for p, m, _ in _all_docs_meta(root)}

    for issue in report["issues"]:
        t = issue["type"]
        if t == "missing_frontmatter_or_id":
            actions.append({"op": "assign_id_and_type", "path": issue["path"], "safe": True,
                            "why": "memory has no id/type"})
        elif t == "duplicate_id":
            actions.append({"op": "regen_id", "path": issue["paths"][-1], "safe": True,
                            "why": f"duplicate id {issue['id']}"})
        elif t == "dangling_superseded_by":
            actions.append({"op": "clear_dangling_supersede", "path": issue["path"], "safe": True,
                            "why": f"superseded_by points to missing {issue['missing_id']}"})
        elif t == "missing_boot":
            actions.append({"op": "regenerate_boot", "safe": True, "why": "BOOT.md missing"})
        elif t == "stale_fts_index":
            actions.append({"op": "rebuild_fts", "safe": True, "why": "FTS index out of date"})
        elif t == "vector_index_out_of_date":
            actions.append({"op": "rebuild_vectors", "safe": True, "why": "vector index out of date"})
        elif t == "secret_in_shareable":
            actions.append({"op": "downgrade_visibility", "path": issue["path"], "safe": False,
                            "requires": "--fix-visibility", "why": "secret in shareable doc"})
        elif t == "duplicate_title":
            actions.append({"op": "warn_duplicate_title", "paths": issue["paths"], "safe": True,
                            "why": "same title within kind/project"})
        elif t == "superseded_still_exportable":
            actions.append({"op": "mark_superseded_private", "path": issue["path"], "safe": False,
                            "requires": "--fix-visibility", "why": "retired item still exportable"})
        # open_correction / unresolved_suggestion / generated_file_without_source are
        # surfaced as advisories only (need human judgement), not auto-actions.

    plan = {"created": now_iso(), "issues": len(report["issues"]),
            "safe_actions": [a for a in actions if a.get("safe")],
            "manual_actions": [a for a in actions if not a.get("safe")],
            "advisories": [i for i in report["issues"]
                           if i["type"] in {"open_correction", "unresolved_suggestion",
                                            "generated_file_without_source", "corrupt_ledger_rows",
                                            "pack_missing_manifest", "corrupt_pack"}]}
    return plan


def write_repair_plan(root: Path, out: Optional[Path] = None) -> Path:
    plan = build_repair_plan(root)
    out = out or (root / "reports" / "REPAIR_PLAN.json")
    write_json(out, plan)
    md = [f"# Repair Plan\n\nGenerated: {plan['created']}\n", f"Issues found: {plan['issues']}\n",
          f"\n## Safe automatic actions ({len(plan['safe_actions'])})\n"]
    for a in plan["safe_actions"]:
        md.append(f"- `{a['op']}` {a.get('path', a.get('paths',''))} — {a['why']}\n")
    md.append(f"\n## Manual / opt-in actions ({len(plan['manual_actions'])})\n")
    for a in plan["manual_actions"]:
        md.append(f"- `{a['op']}` {a.get('path','')} — {a['why']} (needs {a.get('requires','review')})\n")
    md.append(f"\n## Advisories ({len(plan['advisories'])})\n")
    for i in plan["advisories"]:
        md.append(f"- `{i['type']}` {i.get('path','')}\n")
    md_out = out.with_suffix(".md")
    md_out.write_text("".join(md), encoding="utf-8")
    print(f"Wrote repair plan: {out}  and  {md_out}")
    print(f"  safe actions: {len(plan['safe_actions'])} · manual: {len(plan['manual_actions'])} · advisories: {len(plan['advisories'])}")
    return out


def heal_safe(root: Path, dry_run: bool = False, fix_visibility: bool = False,
              write_plan: bool = False, apply_plan: Optional[Path] = None,
              safe: bool = True) -> dict:
    ensure_root(root)
    if write_plan:
        write_repair_plan(root)
        return {"wrote_plan": True}

    repairs: List[str] = []
    record = repairs.append

    def docs_meta():
        return [(p, m) for p, m, _ in _all_docs_meta(root)]

    # If applying a saved plan, restrict to that plan's listed paths/ops.
    plan_paths = None
    if apply_plan is not None:
        plan = read_json(apply_plan, {})
        if not plan:
            raise SystemExit(f"Could not read repair plan: {apply_plan}")
        plan_paths = {a.get("path") for a in plan.get("safe_actions", [])}
        if fix_visibility:
            plan_paths |= {a.get("path") for a in plan.get("manual_actions", [])}
        print(f"Applying repair plan {apply_plan} ({len(plan_paths)} target path(s)).")

    def in_scope(rel):
        return plan_paths is None or rel in plan_paths

    # Pass 1: structural — infer type, assign/regen id.
    seen_ids: Dict[str, Path] = {}
    for p, meta in docs_meta():
        rel = str(p.relative_to(root))
        updates: Dict[str, object] = {}
        kind = meta.get("type")
        if not kind and in_scope(rel):
            kind = FOLDER_TO_KIND.get(p.parent.name, "note")
            updates["type"] = kind
            record(f"inferred type={kind} for {rel}")
        kind = kind or meta.get("type") or "note"
        doc_id = meta.get("id")
        if (not doc_id or doc_id in seen_ids) and in_scope(rel):
            new_id = f"{kind}.{slugify(meta.get('project','')) + '.' if meta.get('project') else ''}{slugify(meta.get('title', p.stem))}.{uuid.uuid4().hex[:8]}"
            updates["id"] = new_id
            record(("assign id" if not doc_id else "regen duplicate id") + f" {doc_id or 'None'} -> {new_id} ({rel})")
            doc_id = new_id
        if updates and not dry_run:
            update_doc_meta(root, rel, updates)
        if doc_id:
            seen_ids[doc_id] = p

    id_to_rel = {m.get("id"): str(p.relative_to(root)) for p, m in docs_meta() if m.get("id")}
    all_ids = set(id_to_rel)

    # Pass 2: supersession reciprocity + dangling links.
    for p, meta in docs_meta():
        rel = str(p.relative_to(root))
        if not in_scope(rel):
            continue
        for old_id in [s for s in meta.get("supersedes", "").split(",") if s]:
            if old_id in id_to_rel:
                om = parse_frontmatter((root / id_to_rel[old_id]).read_text(encoding="utf-8"))[0]
                if om.get("superseded_by") != meta.get("id") or om.get("status") != "superseded":
                    record(f"repair backlink: {old_id} superseded_by {meta.get('id')}")
                    if not dry_run:
                        update_doc_meta(root, id_to_rel[old_id],
                                        {"superseded_by": meta.get("id"), "status": "superseded"})
        sb = meta.get("superseded_by")
        if sb and sb not in all_ids:
            record(f"clear dangling superseded_by={sb}, reactivate {rel}")
            if not dry_run:
                update_doc_meta(root, rel, {"superseded_by": "", "status": "active"})
        elif sb and sb in id_to_rel:
            tm = parse_frontmatter((root / id_to_rel[sb]).read_text(encoding="utf-8"))[0]
            existing = [s for s in tm.get("supersedes", "").split(",") if s]
            if meta.get("id") not in existing:
                record(f"repair forward link: {sb} supersedes {meta.get('id')}")
                if not dry_run:
                    update_doc_meta(root, id_to_rel[sb], {"supersedes": ",".join(existing + [meta.get('id')])})

    # Pass 3 (opt-in): downgrade shareable docs containing secrets.
    if fix_visibility:
        for p, meta in docs_meta():
            rel = str(p.relative_to(root))
            if not in_scope(rel):
                continue
            if meta.get("visibility") in SHAREABLE_VIS and scan_secrets(p.read_text(encoding="utf-8", errors="replace")):
                record(f"downgrade visibility {meta.get('visibility')} -> private (secret) {rel}")
                if not dry_run:
                    update_doc_meta(root, rel, {"visibility": "private"})
            elif meta.get("status") == "superseded" and meta.get("visibility") in SHAREABLE_VIS:
                record(f"mark superseded private {rel}")
                if not dry_run:
                    update_doc_meta(root, rel, {"visibility": "private"})

    # Cartridge-level safe fixes.
    if not (root / "BOOT.md").exists():
        record("regenerate BOOT.md")
        if not dry_run:
            cfg = read_json(root / "CARTRIDGE.json", {})
            (root / "BOOT.md").write_text(boot_text(cfg.get("owner", "")), encoding="utf-8")

    if dry_run:
        print(f"DRY RUN — {len(repairs)} repair(s) would be applied:")
        for r in repairs:
            print(f"  - {r}")
        return {"repairs": repairs, "applied": False}

    rebuild_index(root, force=True)
    if _vmeta(root):  # keep an existing vector index fresh
        build_vector_index(root, backend=_vmeta(root)["backend"], model=_vmeta(root).get("model") or "all-MiniLM-L6-v2")
        record("rebuilt vector index")
    memory_map(root, quiet=True)
    report = audit(root)
    append_ledger(root, "heal.completed",
                  {"repairs": repairs, "issues_remaining": report["summary"]["issues"],
                   "mode": "apply_plan" if apply_plan else ("fix_visibility" if fix_visibility else "safe")})
    print(f"Heal completed: applied {len(repairs)} repair(s), rebuilt index, regenerated MEMORY_MAP.md")
    for r in repairs:
        print(f"  - {r}")
    if report["summary"]["issues"]:
        print(f"Issues remaining for manual review: {report['summary']['issues']} (see reports/AUDIT_REPORT.md)")
    return {"repairs": repairs, "applied": True, "issues_remaining": report["summary"]["issues"]}


def memory_map(root: Path, quiet: bool = False) -> Path:
    """Regenerate MEMORY_MAP.md: projects, active decisions, open corrections/gaps,
    recent receipts, export packs, index health."""
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)

    def rows(sql, *a):
        return conn.execute(sql, a).fetchall()

    projects = rows("SELECT DISTINCT project FROM documents WHERE project!='' ORDER BY project")
    decisions = rows("SELECT title,project FROM documents WHERE kind='decision' AND status='active' ORDER BY project,title")
    opencorr = rows("SELECT title FROM documents WHERE kind='correction' AND status='open' ORDER BY title")
    gaps = rows("SELECT title FROM documents WHERE kind='gap' AND status IN ('open','active') ORDER BY title")
    receipts = rows("SELECT title,created FROM documents WHERE kind='receipt' ORDER BY created DESC LIMIT 5")
    conn.close()
    packs = sorted((root / "exports").glob("*.zip"))

    L = ["# Memory Map\n", f"\nGenerated: {now_iso()}\n"]
    L.append("\n## Projects\n")
    L += [f"- {p[0]}\n" for p in projects] or ["- (none)\n"]
    L.append("\n## Active decisions\n")
    L += [f"- **{d[0]}**{f' — {d[1]}' if d[1] else ''}\n" for d in decisions] or ["- (none)\n"]
    L.append("\n## Open corrections\n")
    L += [f"- {c[0]}\n" for c in opencorr] or ["- (none)\n"]
    L.append("\n## Open gaps\n")
    L += [f"- {g[0]}\n" for g in gaps] or ["- (none)\n"]
    L.append("\n## Recent receipts\n")
    L += [f"- {r[0]} ({r[1]})\n" for r in receipts] or ["- (none)\n"]
    L.append("\n## Export packs\n")
    L += [f"- `{zp.name}`\n" for zp in packs] or ["- (none)\n"]
    L.append("\n## Index health\n")
    L.append(f"- FTS index: {'stale — run heal/index' if index_is_stale(root) else 'current'}\n")
    vstale = vector_index_stale(root)
    L.append(f"- Vector index: {'none' if vstale is None else ('out of date — run embed' if vstale else 'current')}\n")
    out = root / "MEMORY_MAP.md"
    out.write_text("".join(L), encoding="utf-8")
    # keep the legacy filename too, for older references
    (root / "MEMORY.map.md").write_text("".join(L), encoding="utf-8")
    if not quiet:
        print(f"Wrote {out}")
    return out


def status(root: Path) -> None:
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)
    counts = conn.execute("SELECT kind, COUNT(*) FROM documents GROUP BY kind ORDER BY kind").fetchall()
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    superseded = conn.execute("SELECT COUNT(*) FROM documents WHERE status='superseded'").fetchone()[0]
    conn.close()
    ledger_path = root / "ledger" / "events.jsonl"
    events = sum(1 for _ in ledger_path.open("r", encoding="utf-8")) if ledger_path.exists() else 0
    print(f"AI Memory Cartridge v{APP_VERSION}: {root}")
    print(f"Total source documents: {total}  (superseded: {superseded})")
    print(f"Ledger events: {events}")
    for kind, count in counts:
        print(f"- {kind}: {count}")
    audit_report = root / "reports" / "AUDIT_REPORT.json"
    if audit_report.exists():
        report = read_json(audit_report, {})
        print(f"Last audit issues: {report.get('summary', {}).get('issues', 'unknown')}")
    vm = _vmeta(root)
    if vm:
        print(f"Vector index: {vm['backend']} (dim {vm['dim']}, {vm['count']} vectors, built {vm['built_at']})")
    else:
        print("Vector index: not built (run `embed` for semantic search)")


TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".rst", ".json", ".yaml", ".yml", ".py", ".js",
    ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".sh", ".toml", ".ini",
    ".csv", ".html", ".css", ".sql", ".log",
}
MAX_CHUNK = 6000


def _existing_source_hashes(root: Path) -> set:
    out = set()
    for p in iter_source_files(root):
        meta, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if meta.get("source_hash"):
            out.add(meta["source_hash"])
    return out


def _split_markdown(text: str) -> List[Tuple[str, str]]:
    """Split a markdown doc into (heading, section-body) on level-1/2 headings."""
    parts: List[Tuple[str, str]] = []
    cur_title, cur_buf = None, []
    for line in text.splitlines():
        h = re.match(r"^(#{1,2})\s+(.*)$", line)
        if h:
            if cur_title is not None or cur_buf:
                parts.append((cur_title or "(intro)", "\n".join(cur_buf).strip()))
            cur_title, cur_buf = h.group(2).strip(), []
        else:
            cur_buf.append(line)
    if cur_title is not None or cur_buf:
        parts.append((cur_title or "(intro)", "\n".join(cur_buf).strip()))
    return [(t, b) for t, b in parts if b]


def _chunk_text(text: str, size: int = MAX_CHUNK) -> List[str]:
    if len(text) <= size:
        return [text]
    chunks, i = [], 0
    while i < len(text):
        end = min(len(text), i + size)
        nl = text.rfind("\n", i, end)  # prefer a line boundary
        if nl > i + size // 2:
            end = nl
        chunks.append(text[i:end])
        i = end
    return chunks


def _extract_file(root: Path, path: Path, project: str, visibility: str,
                  split: bool, seen: set) -> Dict[str, int]:
    stats = {"added": 0, "dupe": 0, "binary": 0}
    if path.suffix.lower() not in TEXT_EXTS:
        stats["binary"] += 1
        return stats
    digest = sha256_file(path)
    if digest in seen:
        stats["dupe"] += 1
        return stats
    seen.add(digest)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        stats["binary"] += 1
        return stats

    base_meta = {
        "source_path": str(path), "source_hash": digest,
        "bytes": str(path.stat().st_size), "ingested_at": now_iso(),
    }

    units: List[Tuple[str, str]]
    if split and path.suffix.lower() in {".md", ".markdown"} and _split_markdown(text):
        units = [(f"{path.name}: {t}", b) for t, b in _split_markdown(text)]
    elif len(text) > MAX_CHUNK:
        chunks = _chunk_text(text)
        units = [(f"{path.name} (part {i}/{len(chunks)})", c) for i, c in enumerate(chunks, 1)]
    else:
        units = [(path.name, text)]

    for title, body in units:
        add_memory(root, "file", title, body, project=project, visibility=visibility,
                   extra_meta=dict(base_meta), reindex=False, quiet=True)
        stats["added"] += 1
    return stats


def ingest_path(root: Path, path: Path, project: str = "", visibility: str = "private",
                split: bool = True) -> dict:
    ensure_root(root)
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")
    seen = _existing_source_hashes(root)
    totals = {"added": 0, "dupe": 0, "binary": 0, "files_seen": 0}
    targets = [path] if path.is_file() else [p for p in sorted(path.rglob("*")) if p.is_file()]
    for p in targets:
        totals["files_seen"] += 1
        try:
            s = _extract_file(root, p, project, visibility, split, seen)
            for k in ("added", "dupe", "binary"):
                totals[k] += s[k]
        except Exception as e:
            print(f"Skipped {p}: {e}")
    rebuild_index(root, force=True)
    append_ledger(root, "ingest.completed", {"path": str(path), **totals})
    print(f"Ingested from {path}:")
    print(f"  memories added:   {totals['added']}")
    print(f"  duplicates skipped: {totals['dupe']}")
    print(f"  non-text skipped: {totals['binary']}")
    return totals


# --------------------------------------------------------------------------- #
# v0.5 — conversation importers
#
# Bring in real history from ChatGPT, Claude, Gemini exports and generic files.
# Principles honoured here:
#   - raw export is copied verbatim under attachments/imports/<import_id>/ and
#     never mutated or deleted;
#   - only deterministic, typed `conversation` records are created (no invented
#     decisions);
#   - full provenance frontmatter on every record;
#   - unknown/broken exports produce a human-readable import report instead of a
#     stack trace;
#   - import.started / import.completed / import.failed land in the ledger.
# --------------------------------------------------------------------------- #

IMPORT_FILE_EXTS = {".json", ".md", ".markdown", ".txt", ".html", ".htm"}
SPEAKER_RE = re.compile(
    r"^\s*(user|human|me|you|assistant|ai|bot|chatgpt|claude|gemini|bard|system)\s*[:>-]\s*",
    re.IGNORECASE,
)
_ROLE_CANON = {
    "user": "user", "human": "user", "me": "user", "you": "user",
    "assistant": "assistant", "ai": "assistant", "bot": "assistant",
    "chatgpt": "assistant", "claude": "assistant", "gemini": "assistant",
    "bard": "assistant", "system": "system",
}


def _new_import_id() -> str:
    return "imp_" + uuid.uuid4().hex[:12]


def _epoch_to_iso(v) -> str:
    try:
        return dt.datetime.fromtimestamp(float(v), UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return ""


def _collect_input_files(path: Path) -> List[Tuple[str, bytes]]:
    """Return [(display_name, raw_bytes)] for importable members of a file/folder/zip."""
    out: List[Tuple[str, bytes]] = []
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for n in zf.namelist():
                if n.endswith("/"):
                    continue
                if Path(n).suffix.lower() in IMPORT_FILE_EXTS:
                    out.append((n, zf.read(n)))
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file() and p.suffix.lower() in IMPORT_FILE_EXTS:
                out.append((str(p.relative_to(path)), p.read_bytes()))
    elif path.is_file():
        out.append((path.name, path.read_bytes()))
    return out


def _preserve_raw(root: Path, import_id: str, path: Path) -> str:
    dest = root / "attachments" / "imports" / import_id
    dest.mkdir(parents=True, exist_ok=True)
    if path.is_dir():
        target = dest / path.name
        shutil.copytree(path, target, dirs_exist_ok=True)
        return str(target.relative_to(root))
    target = dest / path.name
    shutil.copy2(path, target)
    return str(target.relative_to(root))


# ---- provider parsers: each returns List[{title, date, messages:[{role,text}]}] ----

def parse_chatgpt(data) -> List[dict]:
    convs = []
    items = data if isinstance(data, list) else data.get("conversations", [data])
    for c in items:
        if not isinstance(c, dict) or "mapping" not in c:
            continue
        mapping = c.get("mapping") or {}
        root_id = next((nid for nid, n in mapping.items() if not n.get("parent")), None)
        msgs, seen = [], set()

        def emit(node):
            m = node.get("message") or {}
            role = (m.get("author") or {}).get("role")
            parts = (m.get("content") or {}).get("parts") or []
            text = "\n".join(p for p in parts if isinstance(p, str)).strip()
            if role in ("user", "assistant") and text:
                msgs.append({"role": role, "text": text})

        def walk(nid):
            if not nid or nid in seen or nid not in mapping:
                return
            seen.add(nid)
            emit(mapping[nid])
            for ch in mapping[nid].get("children", []):
                walk(ch)

        if root_id:
            walk(root_id)
        if not msgs:  # fallback: time-ordered flatten
            tmp = []
            for n in mapping.values():
                m = n.get("message") or {}
                role = (m.get("author") or {}).get("role")
                parts = (m.get("content") or {}).get("parts") or []
                text = "\n".join(p for p in parts if isinstance(p, str)).strip()
                if role in ("user", "assistant") and text:
                    tmp.append((m.get("create_time") or 0, {"role": role, "text": text}))
            tmp.sort(key=lambda x: x[0])
            msgs = [m for _, m in tmp]
        convs.append({"title": c.get("title") or "Untitled", "date": _epoch_to_iso(c.get("create_time")),
                      "messages": msgs})
    return convs


def parse_claude(data) -> List[dict]:
    convs = []
    items = data if isinstance(data, list) else data.get("conversations", [data])
    for c in items:
        if not isinstance(c, dict):
            continue
        cm = c.get("chat_messages")
        if cm is None and "messages" in c and "mapping" not in c:
            cm = c.get("messages")
        if cm is None:
            continue
        msgs = []
        for m in cm:
            if not isinstance(m, dict):
                continue
            sender = (m.get("sender") or m.get("role") or "").lower()
            role = _ROLE_CANON.get(sender, "assistant" if sender else "user")
            text = m.get("text")
            if not text:
                blocks = m.get("content") or []
                if isinstance(blocks, list):
                    text = "\n".join(b.get("text", "") for b in blocks
                                     if isinstance(b, dict) and b.get("type") in (None, "text"))
                elif isinstance(blocks, str):
                    text = blocks
            text = (text or "").strip()
            if text:
                msgs.append({"role": role, "text": text})
        convs.append({"title": c.get("name") or c.get("title") or "Untitled",
                      "date": c.get("created_at") or "", "messages": msgs})
    return convs


def parse_gemini(data) -> List[dict]:
    """Google Takeout 'My Activity' JSON for Gemini/Bard. Activity records hold the
    prompt text; responses aren't reliably separated, so each record becomes a
    single-message conversation. HTML exports are not parsed (see import report)."""
    convs = []
    items = data if isinstance(data, list) else [data]
    for rec in items:
        if not isinstance(rec, dict):
            continue
        header = (rec.get("header") or "").lower()
        if header and "gemini" not in header and "bard" not in header:
            continue
        title = rec.get("title") or "Gemini activity"
        prompt = title
        for pre in ("Prompted ", "Asked ", "Searched for ", "Prompted: "):
            if prompt.startswith(pre):
                prompt = prompt[len(pre):]
                break
        if not prompt.strip():
            continue
        convs.append({"title": title[:80], "date": rec.get("time") or "",
                      "messages": [{"role": "user", "text": prompt.strip()}]})
    return convs


def parse_generic_text(text: str, title: str) -> List[dict]:
    lines = text.splitlines()
    msgs, cur_role, buf = [], None, []

    def flush():
        if cur_role and buf:
            t = "\n".join(buf).strip()
            if t:
                msgs.append({"role": cur_role, "text": t})

    for line in lines:
        m = SPEAKER_RE.match(line)
        if m:
            flush()
            cur_role = _ROLE_CANON.get(m.group(1).lower(), "user")
            buf = [line[m.end():]]
        else:
            buf.append(line)
    flush()
    if not msgs:  # no speaker labels -> single note-like message
        body = text.strip()
        msgs = [{"role": "note", "text": body}] if body else []
    return [{"title": title, "date": "", "messages": msgs}] if msgs else []


def parse_generic_json(data, title: str) -> List[dict]:
    # route to a known shape if it looks like one
    if isinstance(data, dict) and "mapping" in data:
        return parse_chatgpt(data)
    if isinstance(data, list) and data and isinstance(data[0], dict) and "mapping" in data[0]:
        return parse_chatgpt(data)
    if isinstance(data, (list, dict)):
        probe = data[0] if isinstance(data, list) and data else data
        if isinstance(probe, dict) and ("chat_messages" in probe or probe.get("sender")):
            return parse_claude(data)
    # generic list of {role/sender, text/content}
    seq = data if isinstance(data, list) else data.get("messages") if isinstance(data, dict) else None
    if isinstance(seq, list):
        msgs = []
        for m in seq:
            if not isinstance(m, dict):
                continue
            role = _ROLE_CANON.get((m.get("role") or m.get("sender") or "user").lower(), "user")
            text = m.get("text") or m.get("content") or ""
            if isinstance(text, list):
                text = "\n".join(b.get("text", "") for b in text if isinstance(b, dict))
            text = (text or "").strip()
            if text:
                msgs.append({"role": role, "text": text})
        if msgs:
            return [{"title": title, "date": "", "messages": msgs}]
    return []


def _render_transcript(conv: dict, provider: str) -> str:
    head = [f"Provider: {provider}"]
    if conv.get("date"):
        head.append(f"Date: {conv['date']}")
    head.append(f"Messages: {len(conv['messages'])}")
    lines = [" · ".join(head), ""]
    for m in conv["messages"]:
        lines.append(f"**{m['role']}:**")
        lines.append(m["text"])
        lines.append("")
    return "\n".join(lines).strip()


PROVIDER_PARSERS = {
    "chatgpt": parse_chatgpt,
    "claude": parse_claude,
    "gemini": parse_gemini,
}


def _parse_provider(provider: str, files: List[Tuple[str, bytes]]) -> Tuple[List[dict], List[str]]:
    """Return (conversations, notes/errors). Never raises on bad data."""
    convs: List[dict] = []
    notes: List[str] = []
    for name, raw in files:
        ext = Path(name).suffix.lower()
        if provider == "generic":
            try:
                if ext in (".json",):
                    convs += parse_generic_json(json.loads(raw.decode("utf-8", "replace")), Path(name).stem)
                elif ext in (".html", ".htm"):
                    notes.append(f"{name}: HTML not parsed (export JSON for structured import)")
                else:
                    convs += parse_generic_text(raw.decode("utf-8", "replace"), Path(name).stem)
            except json.JSONDecodeError:
                # treat as plain text fallback
                convs += parse_generic_text(raw.decode("utf-8", "replace"), Path(name).stem)
            except Exception as e:  # defensive: never crash a whole import on one file
                notes.append(f"{name}: skipped ({type(e).__name__})")
            continue
        # provider-specific
        if ext in (".html", ".htm"):
            notes.append(f"{name}: HTML export not supported for {provider}; export JSON instead")
            continue
        if ext != ".json":
            continue
        try:
            data = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            notes.append(f"{name}: not valid JSON; skipped")
            continue
        try:
            parsed = PROVIDER_PARSERS[provider](data)
            if parsed:
                convs += parsed
            else:
                notes.append(f"{name}: no {provider} conversations recognised in this file")
        except Exception as e:
            notes.append(f"{name}: parse error ({type(e).__name__})")
    return convs, notes


def _write_import_report(root: Path, summary: dict) -> str:
    rdir = root / "reports" / "imports"
    rdir.mkdir(parents=True, exist_ok=True)
    write_json(rdir / f"{summary['import_id']}.json", summary)
    lines = [
        f"# Import Report — {summary['import_id']}\n",
        f"Provider: {summary['provider']}\n",
        f"Source: {summary['source']}\n",
        f"Time: {summary['time']}\n",
        f"Status: {summary['status']}\n",
        f"Dry run: {summary['dry_run']}\n",
        f"Conversations: {len(summary['conversations'])}  ·  Messages: {summary['total_messages']}\n",
        f"Raw preserved: {summary.get('raw_preserved') or '(not preserved — dry run)'}\n",
    ]
    if summary["conversations"]:
        lines.append("\n## Conversations\n")
        for c in summary["conversations"]:
            loc = c.get("path") or "(dry run — not written)"
            lines.append(f"- **{c['title']}** — {c['message_count']} msgs"
                         + (f", {c['date']}" if c.get("date") else "") + f"  `{loc}`\n")
    if summary["notes"]:
        lines.append("\n## Notes / skipped\n")
        for n in summary["notes"]:
            lines.append(f"- {n}\n")
    (rdir / f"{summary['import_id']}.md").write_text("".join(lines), encoding="utf-8")
    return str((rdir / f"{summary['import_id']}.md").relative_to(root))


def import_conversations(root: Path, provider: str, path: Path, project: str = "",
                         visibility: str = "private", limit: Optional[int] = None,
                         dry_run: bool = False) -> dict:
    ensure_root(root)
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")
    import_id = _new_import_id()
    files = _collect_input_files(path)
    summary = {
        "import_id": import_id, "provider": provider, "source": str(path),
        "time": now_iso(), "dry_run": dry_run, "status": "ok",
        "conversations": [], "total_messages": 0, "notes": [], "raw_preserved": "",
        "project": project, "visibility": visibility,
    }

    if not dry_run:
        append_ledger(root, "import.started",
                      {"import_id": import_id, "provider": provider, "source": str(path)})

    if not files:
        summary["status"] = "empty"
        summary["notes"].append("No importable files (.json/.md/.txt/.html) found in source.")
        convs, notes = [], []
    else:
        convs, notes = _parse_provider(provider, files)
        summary["notes"].extend(notes)

    if limit is not None:
        convs = convs[:limit]
    if not convs and summary["status"] == "ok":
        summary["status"] = "no_conversations"
        summary["notes"].append(f"Could not recognise any conversations as a {provider} export.")

    if dry_run:
        for c in convs:
            summary["conversations"].append({"title": c["title"], "date": c.get("date", ""),
                                             "message_count": len(c["messages"]), "path": ""})
            summary["total_messages"] += len(c["messages"])
        print(f"[dry-run] {provider}: would import {len(convs)} conversation(s), "
              f"{summary['total_messages']} message(s) from {path}")
        for c in summary["conversations"]:
            print(f"  - {c['title']}  ({c['message_count']} msgs)")
        for n in summary["notes"]:
            print(f"  note: {n}")
        return summary

    # real import: preserve raw, write records, ledger, report
    try:
        summary["raw_preserved"] = _preserve_raw(root, import_id, path)
    except Exception as e:
        summary["notes"].append(f"raw preservation failed: {type(e).__name__}: {e}")

    for c in convs:
        transcript = _render_transcript(c, provider)
        meta = {
            "provider": provider, "import_id": import_id,
            "source_file": summary["raw_preserved"] or str(path),
            "conversation_title": c["title"], "conversation_date": c.get("date", ""),
            "message_count": str(len(c["messages"])),
            "source_hash": sha256_bytes(transcript.encode("utf-8")),
        }
        p = add_memory(root, "conversation", c["title"] or "Untitled", transcript,
                       project=project, visibility=visibility, extra_meta=meta,
                       reindex=False, quiet=True)
        summary["conversations"].append({"title": c["title"], "date": c.get("date", ""),
                                         "message_count": len(c["messages"]),
                                         "path": str(p.relative_to(root))})
        summary["total_messages"] += len(c["messages"])

    rebuild_index(root, force=True)
    if not convs:
        summary["status"] = summary["status"] if summary["status"] != "ok" else "no_conversations"
    summary["report"] = _write_import_report(root, summary)
    append_ledger(root, "import.completed" if convs else "import.failed",
                  {"import_id": import_id, "provider": provider,
                   "conversations": len(convs), "messages": summary["total_messages"],
                   "status": summary["status"], "report": summary["report"]})

    if convs:
        print(f"Imported {len(convs)} {provider} conversation(s), {summary['total_messages']} message(s).")
        print(f"  raw preserved: {summary['raw_preserved']}")
        print(f"  report: {summary['report']}")
    else:
        print(f"No conversations imported from {path} (status: {summary['status']}).")
        print(f"  see report: {summary['report']}")
    for n in summary["notes"]:
        print(f"  note: {n}")
    return summary


def import_report(root: Path, import_id: str = "") -> None:
    ensure_root(root)
    rdir = root / "reports" / "imports"
    if not rdir.exists() or not any(rdir.glob("*.md")):
        print("No import reports yet. Run an import-* command first.")
        return
    reports = sorted(rdir.glob("*.md"), key=lambda p: p.stat().st_mtime)
    if import_id:
        target = rdir / f"{import_id}.md"
        if not target.exists():
            raise SystemExit(f"No import report for id: {import_id}")
        print(target.read_text(encoding="utf-8"))
        return
    # no id: list all, then print the most recent
    print("Imports on record:")
    for j in sorted(rdir.glob("*.json"), key=lambda p: p.stat().st_mtime):
        d = read_json(j, {})
        print(f"  {d.get('import_id')}  {d.get('provider'):8} {d.get('status'):16} "
              f"convs={len(d.get('conversations', []))}  {d.get('time')}")
    print("\nMost recent report:\n")
    print(reports[-1].read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# v0.7 — safety, partitions and shareability
#
# Make it safe to extract only part of the memory. A local policy file
# (CARTRIDGE_POLICY.json) defines blocked terms and the visibilities permitted to
# leave the machine. classify suggests visibility changes; partition reports the
# split; quarantine pulls risky items out of the export flow without deleting;
# safe-pack is pack with strict, leakage-averse defaults.
# --------------------------------------------------------------------------- #

DEFAULT_POLICY = {
    "default_visibility": "private",
    "blocked_terms": ["client secret", "api key", "password", "private key"],
    "allowed_export_visibility": ["public", "shareable", "work-safe"],
    "require_redaction": True,
}
PARTITION_ORDER = ["private", "personal", "work-safe", "shareable", "public", "blocked", "quarantine"]


def policy_path(root: Path) -> Path:
    return root / "CARTRIDGE_POLICY.json"


def load_policy(root: Path) -> dict:
    p = policy_path(root)
    if not p.exists():
        return dict(DEFAULT_POLICY)
    data = read_json(p, {}) or {}
    merged = dict(DEFAULT_POLICY)
    merged.update({k: v for k, v in data.items() if v is not None})
    return merged


def policy_cmd(root: Path, init: bool = False, show: bool = True) -> dict:
    ensure_root(root)
    if init:
        if policy_path(root).exists():
            print(f"Policy already exists: {policy_path(root)}")
        else:
            write_json(policy_path(root), DEFAULT_POLICY)
            append_ledger(root, "policy.created", {"path": str(policy_path(root).relative_to(root))})
            print(f"Wrote default policy: {policy_path(root)}")
    pol = load_policy(root)
    if show:
        print("Effective policy" + (" (defaults — no file)" if not policy_path(root).exists() else "") + ":")
        for k, v in pol.items():
            print(f"  {k}: {v}")
    return pol


def _is_quarantined(meta: dict) -> bool:
    return meta.get("visibility") == "quarantine" or meta.get("status") == "quarantined"


def classify(root: Path, apply: bool = False) -> dict:
    """Scan all memories and SUGGEST visibility changes. Only applies with apply=True.
    Secrets or policy blocked-terms => suggest 'private' (never auto-upgrade to shareable)."""
    ensure_root(root)
    pol = load_policy(root)
    blocked_terms = [t.lower() for t in pol.get("blocked_terms", [])]
    suggestions = []
    for p in iter_source_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        rel = str(p.relative_to(root))
        vis = meta.get("visibility", "private")
        low = (meta.get("title", "") + " " + body).lower()
        reason = None
        if scan_secrets(text):
            reason = "contains secret"
        elif any(bt in low for bt in blocked_terms):
            hit = next(bt for bt in blocked_terms if bt in low)
            reason = f"matches blocked term '{hit}'"
        if reason and vis in SHAREABLE_VIS:
            suggestions.append({"path": rel, "id": meta.get("id", ""), "from": vis,
                                "to": "private", "reason": reason})
        elif reason and vis not in ("private", "blocked", "quarantine"):
            suggestions.append({"path": rel, "id": meta.get("id", ""), "from": vis,
                                "to": "private", "reason": reason})

    if apply:
        for s in suggestions:
            update_doc_meta(root, s["path"], {"visibility": s["to"]})
            append_ledger(root, "classify.applied",
                          {"id": s["id"], "from": s["from"], "to": s["to"], "reason": s["reason"]})
        rebuild_index(root, force=True)
        print(f"classify: applied {len(suggestions)} visibility change(s).")
    else:
        append_ledger(root, "classify.suggested", {"count": len(suggestions)})
        if not suggestions:
            print("classify: no risky shareable memories found. Nothing to suggest.")
        else:
            print(f"classify: {len(suggestions)} suggestion(s) (run with --apply to enact):")
        for s in suggestions:
            print(f"  {s['from']} -> {s['to']}  [{s['reason']}]  {s['path']}")
    return {"suggestions": suggestions, "applied": apply}


def partition(root: Path) -> dict:
    """List how memories split across visibility partitions."""
    ensure_root(root)
    rebuild_index(root)
    buckets: Dict[str, List[dict]] = {k: [] for k in PARTITION_ORDER}
    for p in iter_source_files(root):
        meta, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        rel = str(p.relative_to(root))
        bucket = "quarantine" if _is_quarantined(meta) else meta.get("visibility", "private")
        buckets.setdefault(bucket, []).append({"id": meta.get("id", ""),
                                               "title": meta.get("title", p.stem), "path": rel})
    print("Memory partitions:")
    for k in PARTITION_ORDER:
        items = buckets.get(k, [])
        flag = "  ← exportable" if k in SHAREABLE_VIS else ("  ← never exported" if k in ("blocked", "quarantine") else "")
        print(f"  {k:11} {len(items)}{flag}")
        for it in items:
            print(f"      - {it['title']}  ({it['id']})")
    return {"partitions": {k: buckets.get(k, []) for k in PARTITION_ORDER}}


def quarantine(root: Path, doc_id: str = "", restore: bool = False, list_only: bool = False) -> dict:
    """Move a risky item out of the export flow (non-destructive) or restore it."""
    ensure_root(root)
    if list_only or (not doc_id):
        rebuild_index(root)
        items = []
        for p in iter_source_files(root):
            meta, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            if _is_quarantined(meta):
                items.append({"id": meta.get("id", ""), "title": meta.get("title", p.stem),
                              "path": str(p.relative_to(root))})
        print(f"Quarantined items: {len(items)}")
        for it in items:
            print(f"  - {it['title']}  ({it['id']})  {it['path']}")
        return {"quarantined": items}

    rel = find_doc_by_id(root, doc_id)
    if not rel:
        raise SystemExit(f"Memory not found: {doc_id}")
    meta, _ = parse_frontmatter((root / rel).read_text(encoding="utf-8"))
    if restore:
        prev = meta.get("prev_visibility", "private")
        update_doc_meta(root, rel, {"visibility": prev, "status": "active", "prev_visibility": ""})
        append_ledger(root, "quarantine.restored", {"id": doc_id, "to": prev})
        print(f"Restored {doc_id} to visibility '{prev}'.")
        action = "restored"
    else:
        update_doc_meta(root, rel, {"prev_visibility": meta.get("visibility", "private"),
                                    "visibility": "quarantine", "status": "quarantined"})
        append_ledger(root, "quarantine.moved", {"id": doc_id, "from": meta.get("visibility", "private")})
        print(f"Quarantined {doc_id} (non-destructive; source file retained).")
        action = "quarantined"
    rebuild_index(root, force=True)
    return {"id": doc_id, "action": action}


def safe_pack(root: Path, query: str, target: str, out: Path, no_redact: bool = False,
              allow_blocked: bool = False, **kw) -> dict:
    """pack with strict defaults: never private, never blocked, secret scan mandatory,
    redaction ON unless explicitly disabled, policy enforced."""
    pol = load_policy(root)
    redact = pol.get("require_redaction", True) and not no_redact
    print(f"safe-pack: private excluded, blocked excluded{' (override!)' if allow_blocked else ''}, "
          f"policy enforced, redaction {'ON' if redact else 'OFF'}.")
    return pack_context(
        root, query, target, out,
        include_private=False, include_superseded=False,
        redact=redact, allow_secrets=False,
        allow_blocked=allow_blocked, enforce_policy=True,
        budget=kw.get("budget", ""), max_docs=kw.get("max_docs"),
        max_chars=kw.get("max_chars"),
    )


# --------------------------------------------------------------------------- #
# v0.9 — personal workflow polish
#
# Make the cartridge usable daily without building a full app: a glanceable
# `today`, a quick-capture `inbox`, `promote` to turn a note into a typed memory,
# a `receipt-template` printer, a small `daily-pack`, and a stdlib-only
# `static-site` local HTML dashboard (no web server, no JS framework).
# --------------------------------------------------------------------------- #

RECEIPT_TEMPLATE_TEXT = (
    "# MEMORY_RECEIPT\n\n"
    "## New decisions\n- Short title :: Optional body [project: Name]\n\n"
    "## Corrections\n- What changed and what is now true [ref: <existing-memory-id>]\n\n"
    "## Generated files\n- filename.ext :: what it is\n\n"
    "## Open gaps\n- Something still unresolved\n\n"
    "## Suggested memory updates\n- A non-binding suggestion\n"
)


def receipt_template(root: Optional[Path] = None) -> str:
    print(RECEIPT_TEMPLATE_TEXT)
    return RECEIPT_TEMPLATE_TEXT


def _recent_docs(root: Path, days: int = 7, limit: int = 50) -> List[dict]:
    rebuild_index(root)
    conn = get_db(root)
    rows = conn.execute(
        "SELECT id,kind,title,project,status,created,path FROM documents "
        "ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    cutoff = (dt.datetime.now(UTC) - dt.timedelta(days=days)).isoformat()
    out = []
    for r in rows:
        created = r[5] or ""
        if not created or created >= cutoff:
            out.append({"id": r[0], "kind": r[1], "title": r[2], "project": r[3],
                        "status": r[4], "created": created, "path": r[6]})
    return out


def today(root: Path, days: int = 7) -> dict:
    """Glanceable status: recent memories, open gaps, open corrections, latest packs."""
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)
    recent = _recent_docs(root, days=days, limit=12)
    gaps = conn.execute("SELECT title FROM documents WHERE kind='gap' AND status IN ('open','active') "
                        "ORDER BY created DESC").fetchall()
    corr = conn.execute("SELECT title,id FROM documents WHERE kind='correction' AND status='open' "
                        "ORDER BY created DESC").fetchall()
    inbox_n = conn.execute("SELECT COUNT(*) FROM documents WHERE kind='note' AND status='inbox'").fetchone()[0]
    conn.close()
    packs = sorted((root / "exports").glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]

    print(f"== Today ({now_iso()}) ==\n")
    print(f"Recent memories (last {days}d):")
    for r in recent[:10]:
        print(f"  [{r['kind']}] {r['title']}" + (f"  · {r['project']}" if r['project'] else ""))
    if not recent:
        print("  (none)")
    print(f"\nInbox awaiting review: {inbox_n}" + ("  → run `inbox`" if inbox_n else ""))
    print(f"\nOpen gaps: {len(gaps)}")
    for g in gaps[:8]:
        print(f"  - {g[0]}")
    print(f"\nOpen corrections: {len(corr)}" + ("  → run `resolve`" if corr else ""))
    for cc in corr[:8]:
        print(f"  - {cc[0]}  ({cc[1]})")
    print(f"\nLatest packs:")
    for zp in packs:
        print(f"  - {zp.name}")
    if not packs:
        print("  (none)")
    return {"recent": recent, "open_gaps": [g[0] for g in gaps],
            "open_corrections": [c[0] for c in corr], "inbox": inbox_n,
            "packs": [p.name for p in packs]}


def inbox(root: Path, capture: str = "", project: str = "", list_only: bool = False) -> dict:
    """Quick-capture store. With text, save a note flagged for review (status=inbox).
    Without, list pending inbox items."""
    ensure_root(root)
    if capture:
        title = capture.strip().split("\n", 1)[0][:80]
        p = add_memory(root, "note", title, capture, project=project, visibility="private",
                       extra_meta={"status": "inbox"}, quiet=True)
        meta = parse_frontmatter(p.read_text(encoding="utf-8"))[0]
        append_ledger(root, "inbox.captured", {"id": meta["id"], "path": str(p.relative_to(root))})
        print(f"Captured to inbox: {title}\n  id: {meta['id']}")
        return {"captured": meta["id"]}
    rebuild_index(root)
    conn = get_db(root)
    rows = conn.execute("SELECT id,title,project,created FROM documents "
                        "WHERE kind='note' AND status='inbox' ORDER BY created").fetchall()
    conn.close()
    print(f"Inbox: {len(rows)} item(s) awaiting review")
    for r in rows:
        print(f"  - {r[1]}  ({r[0]})" + (f"  · {r[2]}" if r[2] else ""))
    print("\nPromote one with:  promote --id <id> --to decision|prompt|project|gap")
    return {"inbox": [{"id": r[0], "title": r[1], "project": r[2]} for r in rows]}


def promote(root: Path, doc_id: str, to_kind: str, title: str = "", project: str = "") -> dict:
    """Turn a note/suggestion into a typed memory (decision/prompt/project/gap).
    Non-destructive: the original is marked status=promoted with a link to the new item."""
    ensure_root(root)
    if to_kind not in {"decision", "prompt", "project", "gap", "note"}:
        raise SystemExit("promote --to must be one of: decision, prompt, project, gap, note")
    rebuild_index(root)
    rel = find_doc_by_id(root, doc_id)
    if not rel:
        raise SystemExit(f"Memory not found: {doc_id}")
    meta, body = parse_frontmatter((root / rel).read_text(encoding="utf-8"))
    if meta.get("type") not in ("note", "suggestion"):
        print(f"Note: promoting a '{meta.get('type')}' (usually you promote a note/suggestion).")
    new_title = title or meta.get("title", "Untitled")
    new_proj = project or meta.get("project", "")
    new_path = add_memory(root, to_kind, new_title, body, project=new_proj,
                          visibility=meta.get("visibility", "private"),
                          extra_meta={"promoted_from": doc_id}, quiet=True)
    new_meta = parse_frontmatter(new_path.read_text(encoding="utf-8"))[0]
    update_doc_meta(root, rel, {"status": "promoted", "promoted_to": new_meta["id"]})
    rebuild_index(root, force=True)
    append_ledger(root, "memory.promoted",
                  {"from": doc_id, "to": new_meta["id"], "to_kind": to_kind})
    print(f"Promoted {doc_id} -> {to_kind} {new_meta['id']}")
    print(f"  new: {new_path.relative_to(root)}")
    return {"from": doc_id, "to": new_meta["id"], "to_kind": to_kind}


def daily_pack(root: Path, out: Path, budget: str = "small", include_private: bool = False) -> dict:
    """Small pack of active projects and open decisions/gaps for an LLM check-in."""
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)
    projs = [r[0] for r in conn.execute(
        "SELECT DISTINCT project FROM documents WHERE project!='' ").fetchall()]
    conn.close()
    query = " ".join(projs[:8]) + " decision gap project" if projs else "decision gap project"
    return pack_context(root, query.strip(), "human", out,
                        include_private=include_private, budget=budget)


# ---- static site (stdlib only, no JS framework) ----------------------------

def _html_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


_SITE_CSS = """
:root{--bg:#0f1115;--card:#181b22;--ink:#e6e8ee;--mut:#9aa3b2;--acc:#6ea8fe;--line:#262a33}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{padding:24px 28px;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:18px}header .mut{color:var(--mut);font-size:13px}
.wrap{max-width:960px;margin:0 auto;padding:24px 28px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card h3{margin:0 0 8px;font-size:14px}.tag{display:inline-block;font-size:11px;color:var(--mut);
border:1px solid var(--line);border-radius:6px;padding:1px 7px;margin-right:6px}
.search{width:100%;padding:10px 12px;background:var(--card);border:1px solid var(--line);
border-radius:8px;color:var(--ink);margin-bottom:16px}
.muted{color:var(--mut)}.list li{margin:4px 0}h2{font-size:15px;margin:22px 0 10px;color:var(--mut)}
footer{color:var(--mut);font-size:12px;padding:24px 28px;border-top:1px solid var(--line)}
"""

# search is plain vanilla JS over a static JSON file — no framework, runs from file://
_SITE_SEARCH_JS = """
let DATA=[];
fetch('search.json').then(r=>r.json()).then(d=>{DATA=d.items||[]});
function go(q){q=(q||'').toLowerCase().trim();const out=document.getElementById('results');
if(!q){out.innerHTML='';return;}
const hits=DATA.filter(x=>(x.title+' '+x.project+' '+x.kind).toLowerCase().includes(q)).slice(0,50);
out.innerHTML=hits.map(h=>`<li><span class="tag">${h.kind}</span><a href="${h.href}">${h.title}</a>${h.project?' <span class="muted">· '+h.project+'</span>':''}</li>`).join('')||'<li class="muted">no matches</li>';}
"""


def _site_page(title: str, body_html: str) -> str:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{_html_escape(title)}</title><link rel=stylesheet href='style.css'></head>"
            f"<body><header><h1>AI Memory Cartridge</h1>"
            f"<div class=mut>{_html_escape(title)}</div></header>"
            f"<div class=wrap>{body_html}</div>"
            f"<footer>Generated {now_iso()} · local static site · stdlib only</footer></body></html>")


def static_site(root: Path, include_private: bool = False) -> Path:
    """Generate a local static HTML dashboard under exports/site/. No server, no framework."""
    ensure_root(root)
    rebuild_index(root)
    site = root / "exports" / "site"
    if site.exists():
        shutil.rmtree(site)
    (site / "projects").mkdir(parents=True)
    (site / "decisions").mkdir(parents=True)
    (site / "style.css").write_text(_SITE_CSS, encoding="utf-8")
    (site / "search.js").write_text(_SITE_SEARCH_JS, encoding="utf-8")

    conn = get_db(root)
    vis_filter = "" if include_private else " AND visibility NOT IN ('private','blocked','quarantine')"
    docs = conn.execute(
        f"SELECT id,kind,title,project,status,path,body FROM documents WHERE 1=1{vis_filter}"
    ).fetchall()
    conn.close()

    by_id = {d[0]: d for d in docs}
    projects = sorted({d[3] for d in docs if d[3]})
    decisions = [d for d in docs if d[1] == "decision"]
    excluded = 0
    if not include_private:
        c2 = get_db(root)
        excluded = c2.execute("SELECT COUNT(*) FROM documents WHERE "
                              "visibility IN ('private','blocked','quarantine')").fetchone()[0]
        c2.close()

    search_items = []

    # decision pages
    for d in decisions:
        did, _, title, project, status, path, body = d
        fn = f"decisions/{slugify(did)}.html"
        html = (f"<p><a href='../index.html'>← back</a></p>"
                f"<div class=card><h3>{_html_escape(title)}</h3>"
                f"<p><span class=tag>decision</span>"
                f"{('<span class=tag>'+_html_escape(project)+'</span>') if project else ''}"
                f"<span class=tag>{_html_escape(status)}</span></p>"
                f"<pre style='white-space:pre-wrap'>{_html_escape(body)}</pre>"
                f"<p class=muted>source: {_html_escape(path)}</p></div>")
        (site / fn).write_text(_site_page(title, html), encoding="utf-8")
        search_items.append({"title": title, "project": project, "kind": "decision", "href": fn})

    # project pages
    for proj in projects:
        items = [d for d in docs if d[3] == proj]
        fn = f"projects/{slugify(proj)}.html"
        rows = "".join(
            f"<li><span class=tag>{d[1]}</span>"
            + (f"<a href='../decisions/{slugify(d[0])}.html'>{_html_escape(d[2])}</a>"
               if d[1] == "decision" else _html_escape(d[2]))
            + f" <span class=muted>· {_html_escape(d[4])}</span></li>"
            for d in items)
        html = (f"<p><a href='../index.html'>← back</a></p><h2>{_html_escape(proj)}</h2>"
                f"<ul class=list>{rows}</ul>")
        (site / fn).write_text(_site_page(f"Project · {proj}", html), encoding="utf-8")
        search_items.append({"title": proj, "project": proj, "kind": "project", "href": fn})

    write_json(site / "search.json", {"items": search_items})

    # index
    proj_cards = "".join(
        f"<div class=card><h3><a href='projects/{slugify(p)}.html'>{_html_escape(p)}</a></h3>"
        f"<p class=muted>{sum(1 for d in docs if d[3]==p)} item(s)</p></div>" for p in projects)
    dec_list = "".join(
        f"<li><a href='decisions/{slugify(d[0])}.html'>{_html_escape(d[2])}</a>"
        f"{(' <span class=muted>· '+_html_escape(d[3])+'</span>') if d[3] else ''}</li>"
        for d in decisions if d[4] == "active")
    note = (f"<p class=muted>{excluded} private/blocked item(s) excluded. "
            f"Re-run with --include-private to include them.</p>") if excluded else ""
    body = (f"<input class=search placeholder='Search memories…' oninput='go(this.value)'>"
            f"<ul class=list id=results></ul>"
            f"<h2>Projects</h2><div class=grid>{proj_cards or '<p class=muted>none</p>'}</div>"
            f"<h2>Active decisions</h2><ul class=list>{dec_list or '<li class=muted>none</li>'}</ul>"
            f"{note}<script src='search.js'></script>")
    (site / "index.html").write_text(_site_page("Dashboard", body), encoding="utf-8")

    append_ledger(root, "static_site.generated",
                  {"path": str(site.relative_to(root)), "include_private": include_private,
                   "projects": len(projects), "decisions": len(decisions)})
    print(f"Generated static site: {site / 'index.html'}")
    print(f"  projects: {len(projects)} · decisions: {len(decisions)}"
          + (f" · excluded private/blocked: {excluded}" if excluded else ""))
    return site / "index.html"


# --------------------------------------------------------------------------- #
# v1.0 — backup, restore, migration
#
# Backups are full source-of-truth snapshots (source/ + ledger/ + config +
# policy), not derived indexes — those rebuild. Restore is explicit and refuses
# to clobber a non-empty cartridge unless --force. Migration is explicit and
# reversible: it only stamps the current app version and ensures a cartridge_id,
# never rewriting memory content.
# --------------------------------------------------------------------------- #

BACKUP_INCLUDE = ["source", "ledger", "attachments", "reports"]
BACKUP_FILES = ["CARTRIDGE.json", "CARTRIDGE_POLICY.json", "BOOT.md", "MEMORY_MAP.md"]


def export_backup(root: Path, out: Path) -> Path:
    """Write a portable backup zip of the source of truth (no derived indexes)."""
    ensure_root(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = read_json(root / "CARTRIDGE.json", {}) or {}
    meta = {
        "schema": "ai-memory-cartridge-backup.v1", "created_at": now_iso(),
        "app_version": APP_VERSION,
        "cartridge_id": cartridge_meta(root)["cartridge_id"],
        "cartridge_version": cfg.get("version", APP_VERSION),
        "owner": cfg.get("owner", ""),
    }
    n = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("BACKUP_MANIFEST.json", json.dumps(meta, indent=2))
        for fname in BACKUP_FILES:
            fp = root / fname
            if fp.exists():
                zf.write(fp, fname); n += 1
        for d in BACKUP_INCLUDE:
            base = root / d
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_file():
                    zf.write(p, str(p.relative_to(root))); n += 1
    append_ledger(root, "backup.exported", {"output": str(out), "files": n})
    print(f"Backup written: {out}  ({n} file(s))")
    return out


def import_backup(root: Path, backup: Path, force: bool = False) -> dict:
    """Restore a backup into root. Refuses to overwrite a non-empty cartridge unless --force.
    Derived indexes are rebuilt afterwards, not restored."""
    if not backup.exists():
        raise SystemExit(f"Backup not found: {backup}")
    try:
        zf = zipfile.ZipFile(backup)
    except zipfile.BadZipFile:
        raise SystemExit(f"Not a valid backup zip: {backup}")
    with zf:
        names = zf.namelist()
        if "BACKUP_MANIFEST.json" not in names:
            raise SystemExit("Not a cartridge backup (missing BACKUP_MANIFEST.json).")
        manifest = json.loads(zf.read("BACKUP_MANIFEST.json"))
        existing = (root / "CARTRIDGE.json").exists()
        has_source = (root / "source").exists() and any((root / "source").rglob("*.md"))
        if existing and has_source and not force:
            raise SystemExit(
                f"Target cartridge {root} already has memories. Refusing to overwrite.\n"
                f"Re-run with --force to restore over it (existing files will be replaced).")
        root.mkdir(parents=True, exist_ok=True)
        restored = 0
        for n in names:
            if n == "BACKUP_MANIFEST.json" or n.endswith("/"):
                continue
            target = root / n
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(n))
            restored += 1
    # rebuild derived state from the restored source of truth
    rebuild_index(root, force=True)
    append_ledger(root, "backup.imported",
                  {"backup": str(backup), "files": restored,
                   "from_cartridge": manifest.get("cartridge_id"),
                   "backup_app_version": manifest.get("app_version")})
    print(f"Restored {restored} file(s) from {backup}")
    print(f"  cartridge: {manifest.get('cartridge_id')} (backup made with v{manifest.get('app_version')})")
    print("  rebuilt FTS index. Run `embed` to rebuild the vector index if you use semantic search.")
    return {"restored": restored, "manifest": manifest}


def migrate(root: Path, dry_run: bool = False) -> dict:
    """Explicit, reversible migration: stamp current app version and ensure a
    cartridge_id exists. Never rewrites memory content. Records the prior version."""
    ensure_root(root)
    cfg = read_json(root / "CARTRIDGE.json", {}) or {}
    from_version = cfg.get("version", "unknown")
    changes = []
    if from_version != APP_VERSION:
        changes.append(f"version {from_version} -> {APP_VERSION}")
    if not cfg.get("cartridge_id"):
        changes.append("add cartridge_id")
    if not changes:
        print(f"Already at v{APP_VERSION}; nothing to migrate.")
        return {"migrated": False, "from": from_version}
    if dry_run:
        print(f"DRY RUN — would apply: {', '.join(changes)}")
        return {"migrated": False, "planned": changes, "from": from_version}

    new_cfg = dict(cfg)
    new_cfg["version"] = APP_VERSION
    if not new_cfg.get("cartridge_id"):
        new_cfg["cartridge_id"] = cartridge_meta(root)["cartridge_id"]  # deterministic
    history = new_cfg.get("migrated_from", [])
    if not isinstance(history, list):
        history = [history]
    history.append({"from": from_version, "to": APP_VERSION, "at": now_iso()})
    new_cfg["migrated_from"] = history
    write_json(root / "CARTRIDGE.json", new_cfg)
    append_ledger(root, "cartridge.migrated", {"from": from_version, "to": APP_VERSION})
    print(f"Migrated cartridge: {', '.join(changes)}")
    print("  (reversible: prior version recorded in CARTRIDGE.json 'migrated_from')")
    return {"migrated": True, "from": from_version, "to": APP_VERSION, "changes": changes}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description=f"AI Memory Cartridge v{APP_VERSION}")
    parser.add_argument("--root", default=str(Path.cwd() / DEFAULT_ROOT_NAME), help="Cartridge root folder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Create a new cartridge")
    p.add_argument("--owner", default=os.environ.get("USER", "user"))

    p = sub.add_parser("add", help="Add a memory item")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--title", required=True)
    p.add_argument("--body", default="")
    p.add_argument("--body-file", help="Read body from file")
    p.add_argument("--project", default="")
    p.add_argument("--visibility", default="private", choices=VISIBILITIES)
    p.add_argument("--source-file")

    p = sub.add_parser("ingest", help="Ingest a file or folder")
    p.add_argument("path")
    p.add_argument("--project", default="")
    p.add_argument("--visibility", default="private", choices=VISIBILITIES)
    p.add_argument("--no-split", dest="split", action="store_false", default=True,
                   help="Ingest each file whole instead of splitting markdown by heading")

    sub.add_parser("index", help="Rebuild search index")

    p = sub.add_parser("query", help="Query the cartridge")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-private", action="store_true", default=True)
    p.add_argument("--no-private", dest="include_private", action="store_false")
    p.add_argument("--active-only", action="store_true", help="Exclude superseded memories")
    p.add_argument("--kind", default="", help="Comma-separated kinds to filter (e.g. decision,project)")
    p.add_argument("--project", default="", help="Filter to a single project")
    p.add_argument("--status", default="", help="Filter to a status (active, superseded, open, ...)")
    p.add_argument("--semantic", action="store_true", help="Use the vector index instead of FTS (run `embed` first)")

    p = sub.add_parser("pack", help="Create uploadable context pack")
    p.add_argument("query")
    p.add_argument("--for", dest="target", default="chatgpt",
                   choices=["chatgpt", "claude", "gemini", "deepseek", "codex", "human"])
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--include-private", action="store_true")
    p.add_argument("--include-superseded", action="store_true", help="Also export retired memories")
    p.add_argument("--redact", action="store_true", help="Mask detected secrets in the export")
    p.add_argument("--allow-secrets", action="store_true", help="Export even if secrets are present")
    p.add_argument("--budget", default="", choices=["small", "medium", "large"],
                   help="Size budget preset (default medium)")
    p.add_argument("--max-docs", type=int, default=None, help="Cap number of included documents")
    p.add_argument("--max-chars", type=int, default=None, help="Cap total source characters")
    p.add_argument("--allow-blocked", action="store_true", help="include blocked-visibility items")
    p.add_argument("--enforce-policy", action="store_true", help="apply CARTRIDGE_POLICY export rules")

    p = sub.add_parser("validate-pack", help="Check a pack zip is structurally valid")
    p.add_argument("zip")
    p = sub.add_parser("explain-pack", help="Summarise what a pack zip contains")
    p.add_argument("zip")

    p = sub.add_parser("policy", help="Show or initialise the local export policy")
    p.add_argument("--init", action="store_true", help="write a default CARTRIDGE_POLICY.json")

    p = sub.add_parser("classify", help="Suggest (or apply) visibility changes for risky memories")
    p.add_argument("--apply", action="store_true", help="apply the suggested changes")

    sub.add_parser("partition", help="List how memories split across visibility partitions")

    p = sub.add_parser("quarantine", help="Move a risky item out of the export flow (non-destructive)")
    p.add_argument("--id", default="", help="memory id to quarantine (omit to list quarantined)")
    p.add_argument("--restore", action="store_true", help="restore a quarantined item")
    p.add_argument("--list", action="store_true", help="list quarantined items")

    p = sub.add_parser("safe-pack", help="pack with strict leakage-averse defaults")
    p.add_argument("query")
    p.add_argument("--for", dest="target", default="chatgpt", choices=list(PACK_PROFILES))
    p.add_argument("--out", required=True)
    p.add_argument("--budget", default="", choices=["small", "medium", "large"])
    p.add_argument("--max-docs", type=int, default=None)
    p.add_argument("--max-chars", type=int, default=None)
    p.add_argument("--no-redact", action="store_true", help="disable redaction (not recommended)")
    p.add_argument("--allow-blocked", action="store_true", help="override: include blocked items")

    p = sub.add_parser("absorb", help="Absorb a MEMORY_RECEIPT.md into typed memories")
    p.add_argument("receipt")
    p.add_argument("--dry-run", action="store_true", help="Show what would be absorbed, write nothing")

    sub.add_parser("audit", help="Audit cartridge")
    p = sub.add_parser("heal", help="Repair structural issues and rebuild derived state")
    p.add_argument("--dry-run", action="store_true", help="Show repairs without applying them")
    p.add_argument("--safe", action="store_true", help="Safe automatic fixes only (default behaviour)")
    p.add_argument("--fix-visibility", action="store_true",
                   help="Downgrade shareable docs that contain secrets to private")
    p.add_argument("--write-plan", action="store_true", help="Write a repair plan and exit (no changes)")
    p.add_argument("--apply-plan", default="", help="Apply a previously written repair plan JSON")
    sub.add_parser("status", help="Show cartridge status")
    sub.add_parser("verify-ledger", help="Check the event ledger for corrupt rows")
    sub.add_parser("memory-map", help="Regenerate MEMORY_MAP.md")
    sub.add_parser("repair-plan", help="Write a human-readable repair plan from the current audit")

    p = sub.add_parser("today", help="Glanceable status: recent memories, gaps, corrections, packs")
    p.add_argument("--days", type=int, default=7)

    p = sub.add_parser("inbox", help="Quick-capture a note, or list pending inbox items")
    p.add_argument("text", nargs="?", default="", help="text to capture (omit to list)")
    p.add_argument("--project", default="")

    p = sub.add_parser("promote", help="Turn a note/suggestion into a typed memory")
    p.add_argument("--id", required=True)
    p.add_argument("--to", required=True, choices=["decision", "prompt", "project", "gap", "note"])
    p.add_argument("--title", default="")
    p.add_argument("--project", default="")

    sub.add_parser("receipt-template", help="Print the standard MEMORY_RECEIPT format")

    p = sub.add_parser("daily-pack", help="Small pack of active projects and open decisions")
    p.add_argument("--out", required=True)
    p.add_argument("--budget", default="small", choices=["small", "medium", "large"])
    p.add_argument("--include-private", action="store_true")

    p = sub.add_parser("static-site", help="Generate a local static HTML dashboard (stdlib only)")
    p.add_argument("--include-private", action="store_true")

    p = sub.add_parser("export-backup", help="Write a portable backup zip (source of truth)")
    p.add_argument("--out", required=True)
    p = sub.add_parser("import-backup", help="Restore a cartridge from a backup zip")
    p.add_argument("backup")
    p.add_argument("--force", action="store_true", help="overwrite a non-empty cartridge")
    p = sub.add_parser("migrate", help="Stamp current version / ensure cartridge_id (reversible)")
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("embed", help="Build the vector index (semantic search backend)")
    p.add_argument("--backend", default="tfidf", choices=["tfidf", "st"],
                   help="tfidf = stdlib, offline (default); st = sentence-transformers (local model)")
    p.add_argument("--model", default="all-MiniLM-L6-v2", help="model name for the 'st' backend")

    p = sub.add_parser("resolve", help="Close out corrections that absorb left open")
    p.add_argument("--correction", default="", help="id of the open correction to resolve")
    p.add_argument("--target", default="", help="id of the memory the correction supersedes")
    p.add_argument("--dismiss", action="store_true", help="keep the correction; it supersedes nothing")
    p.add_argument("--auto", action="store_true", help="auto-resolve all open corrections above threshold")
    p.add_argument("--threshold", type=float, default=0.18)
    p.add_argument("--semantic", action="store_true", help="use the vector index for matching")

    def _add_import_parser(name, helptext):
        ip = sub.add_parser(name, help=helptext)
        ip.add_argument("path", help="export zip, folder, or file")
        ip.add_argument("--project", default="", help="attach imported conversations to a project")
        ip.add_argument("--visibility", default="private", choices=VISIBILITIES)
        ip.add_argument("--limit", type=int, default=None, help="cap conversations imported (testing)")
        ip.add_argument("--dry-run", action="store_true", help="show what would be imported; write nothing")
        return ip

    _add_import_parser("import-chatgpt", "Import a ChatGPT export (conversations.json / zip)")
    _add_import_parser("import-claude", "Import a Claude export (conversations.json / zip)")
    _add_import_parser("import-gemini", "Import a Gemini/Bard Google Takeout export (MyActivity.json)")
    _add_import_parser("import-generic", "Import generic transcript file(s): .md/.txt/.json")

    p = sub.add_parser("import-report", help="Show import report(s) written by import-* commands")
    p.add_argument("--import-id", default="", help="show a specific import; default lists all + most recent")

    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()

    if args.cmd == "init":
        init_cartridge(root, args.owner)
    elif args.cmd == "add":
        body = args.body
        if args.body_file:
            body = Path(args.body_file).read_text(encoding="utf-8", errors="replace")
        add_memory(root, args.kind, args.title, body, args.project, args.visibility,
                   Path(args.source_file).expanduser() if args.source_file else None)
    elif args.cmd == "ingest":
        ingest_path(root, Path(args.path).expanduser(), args.project, args.visibility, split=args.split)
    elif args.cmd == "index":
        ensure_root(root)
        rebuilt = rebuild_index(root, force=True)
        append_ledger(root, "index.rebuilt", {})
        print("Index rebuilt." if rebuilt else "Index already current.")
    elif args.cmd == "query":
        kinds = [k.strip() for k in args.kind.split(",") if k.strip()] or None
        if args.semantic:
            results = semantic_search(root, args.query, k=args.limit, kinds=kinds,
                                      active_only=args.active_only, project=args.project)
        else:
            results = query_memory(
                root, args.query, args.limit, args.include_private,
                active_only=args.active_only, kinds=kinds,
                project=args.project, status=args.status)
        print_query_results(results)
    elif args.cmd == "embed":
        info = build_vector_index(root, args.backend, args.model)
        print(f"Vector index built: backend={info['backend']} dim={info['dim']} vectors={info['count']}")
    elif args.cmd == "resolve":
        resolve(root, correction=args.correction, target=args.target, dismiss=args.dismiss,
                auto=args.auto, threshold=args.threshold, semantic=args.semantic)
    elif args.cmd in ("import-chatgpt", "import-claude", "import-gemini", "import-generic"):
        provider = args.cmd.split("-", 1)[1]
        import_conversations(root, provider, Path(args.path).expanduser(),
                             project=args.project, visibility=args.visibility,
                             limit=args.limit, dry_run=args.dry_run)
    elif args.cmd == "import-report":
        import_report(root, import_id=args.import_id)
    elif args.cmd == "pack":
        pack_context(root, args.query, args.target, Path(args.out).expanduser().resolve(),
                     args.limit, args.include_private, args.include_superseded,
                     args.redact, args.allow_secrets,
                     budget=args.budget, max_docs=args.max_docs, max_chars=args.max_chars,
                     allow_blocked=args.allow_blocked, enforce_policy=args.enforce_policy)
    elif args.cmd == "validate-pack":
        res = validate_pack(Path(args.zip).expanduser())
        raise SystemExit(0 if res["ok"] else 1)
    elif args.cmd == "explain-pack":
        explain_pack(Path(args.zip).expanduser())
    elif args.cmd == "policy":
        policy_cmd(root, init=args.init)
    elif args.cmd == "classify":
        classify(root, apply=args.apply)
    elif args.cmd == "partition":
        partition(root)
    elif args.cmd == "quarantine":
        quarantine(root, doc_id=args.id, restore=args.restore, list_only=args.list)
    elif args.cmd == "safe-pack":
        safe_pack(root, args.query, args.target, Path(args.out).expanduser().resolve(),
                  no_redact=args.no_redact, allow_blocked=args.allow_blocked,
                  budget=args.budget, max_docs=args.max_docs, max_chars=args.max_chars)
    elif args.cmd == "absorb":
        absorb_receipt(root, Path(args.receipt).expanduser(), dry_run=args.dry_run)
    elif args.cmd == "audit":
        report = audit(root)
        print(f"Audit complete. Issues: {report['summary']['issues']}")
        print(root / "reports" / "AUDIT_REPORT.md")
    elif args.cmd == "heal":
        heal_safe(root, dry_run=args.dry_run, fix_visibility=args.fix_visibility,
                  write_plan=args.write_plan,
                  apply_plan=Path(args.apply_plan).expanduser() if args.apply_plan else None,
                  safe=args.safe)
    elif args.cmd == "verify-ledger":
        verify_ledger(root)
    elif args.cmd == "memory-map":
        memory_map(root)
    elif args.cmd == "repair-plan":
        write_repair_plan(root)
    elif args.cmd == "today":
        today(root, days=args.days)
    elif args.cmd == "inbox":
        inbox(root, capture=args.text, project=args.project)
    elif args.cmd == "promote":
        promote(root, args.id, args.to, title=args.title, project=args.project)
    elif args.cmd == "receipt-template":
        receipt_template(root)
    elif args.cmd == "daily-pack":
        daily_pack(root, Path(args.out).expanduser().resolve(),
                   budget=args.budget, include_private=args.include_private)
    elif args.cmd == "static-site":
        static_site(root, include_private=args.include_private)
    elif args.cmd == "export-backup":
        export_backup(root, Path(args.out).expanduser().resolve())
    elif args.cmd == "import-backup":
        import_backup(root, Path(args.backup).expanduser().resolve(), force=args.force)
    elif args.cmd == "migrate":
        migrate(root, dry_run=args.dry_run)
    elif args.cmd == "status":
        status(root)


if __name__ == "__main__":
    main()
