import math
import re
import sqlite3
import uuid
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from koush.core.utils import (
    now_iso, read_json, write_json, parse_frontmatter, sha256_file, append_ledger
)
from koush.core.memory import ensure_root
import struct
try:
    import sqlite_vec
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False

def _serialize_vec(v: List[float]) -> bytes:
    return struct.pack(f"{len(v)}f", *v)

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
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def corpus_fingerprint(root: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    for p in iter_source_files(root):
        h.update(str(p.relative_to(root)).encode("utf-8"))
        st = p.stat()
        h.update(f"{st.st_size}:{st.st_mtime}".encode("utf-8"))
    return h.hexdigest()


def rebuild_index(root: Path, force: bool = False) -> bool:
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "indexes" / "index_state.json"
    db_path = root / "indexes" / "memory.sqlite"
    fp = corpus_fingerprint(root)
    if not force and db_path.exists():
        prev = read_json(state_path, {})
        if prev.get("fingerprint") == fp:
            return False

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
        CREATE INDEX IF NOT EXISTS idx_docs_project ON documents(project);
        CREATE INDEX IF NOT EXISTS idx_docs_kind ON documents(kind);
        CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_docs_visibility ON documents(visibility);
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
        if query.strip():
            rows = conn.execute(
                f"""SELECT {cols} FROM documents d
                    WHERE lower(ifnull(d.title,'')||' '||ifnull(d.body,'')||' '||ifnull(d.project,'')||' '||ifnull(d.kind,'')) LIKE lower(?){where_extra}
                    LIMIT ?""",
                (f"%{query}%", *params, pool),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT {cols} FROM documents d WHERE 1=1 {where_extra} LIMIT ?""",
                (*params, pool),
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
    
    use_sqlite_vec = False
    if HAS_SQLITE_VEC and not isinstance(emb, TfidfEmbedder):
        try:
            vc.enable_load_extension(True)
            sqlite_vec.load(vc)
            vc.enable_load_extension(False)
            use_sqlite_vec = True
        except (AttributeError, sqlite3.OperationalError, Exception):
            use_sqlite_vec = False
            
    if use_sqlite_vec:
        vc.executescript(
            "CREATE TABLE vectors(id TEXT PRIMARY KEY, kind TEXT, status TEXT, vec TEXT);"
            f"CREATE VIRTUAL TABLE vec_docs USING vec0(embedding float[{dim}]);"
            "CREATE TABLE vmeta(backend TEXT, model TEXT, dim INT, idf TEXT, built_at TEXT, count INT);"
        )
        for r, v in zip(rows, vecs):
            cur = vc.execute("INSERT INTO vectors (id, kind, status, vec) VALUES (?,?,?,?)", 
                             (r[0], r[1], r[2], None))
            vc.execute("INSERT INTO vec_docs(rowid, embedding) VALUES (?,?)",
                       (cur.lastrowid, _serialize_vec(v)))
    else:
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
        raise SystemExit("No vector index yet. Build one:  koush_cli.py --root <root> embed")
    if meta["backend"] == "tfidf":
        emb = TfidfEmbedder()
        emb.idf = json.loads(meta["idf"] or "{}")
        qv = emb.embed(query)
    else:
        qv = get_embedder("st", meta["model"] or "all-MiniLM-L6-v2").embed(query)

    vc = sqlite3.connect(str(root / VECTOR_DB))
    
    use_sqlite_vec = False
    if HAS_SQLITE_VEC and meta["backend"] != "tfidf":
        try:
            vc.enable_load_extension(True)
            sqlite_vec.load(vc)
            vc.enable_load_extension(False)
            use_sqlite_vec = True
        except (AttributeError, sqlite3.OperationalError, Exception):
            use_sqlite_vec = False
            
    if use_sqlite_vec:
        clauses = []
        params = []
        if active_only:
            clauses.append("v.status = 'active'")
        if kinds:
            clauses.append("v.kind IN (" + ",".join("?" for _ in kinds) + ")")
            params.extend(kinds)
            
        where = " AND ".join(clauses)
        if where:
            where = f" AND {where}"
            
        query_sql = f"""
            SELECT v.id, v.kind, v.status, 1.0 - vec_distance_cosine(d.embedding, ?) as score
            FROM vec_docs d
            JOIN vectors v ON v.rowid = d.rowid
            WHERE d.embedding MATCH ? AND k = {k * 10} {where}
            ORDER BY score DESC
        """
        vrows = vc.execute(query_sql, (_serialize_vec(qv), _serialize_vec(qv), *params)).fetchall()
        vc.close()
        
        scored = []
        for rid, kind, status, score in vrows:
            if score > 0:
                scored.append((score, rid, kind, status))
        scored = scored[:k]
    else:
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
