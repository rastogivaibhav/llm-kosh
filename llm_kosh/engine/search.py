import math
import re
import sqlite3
import uuid
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from llm_kosh.core.utils import (
    now_iso, read_json, write_json, parse_frontmatter, sha256_file, append_ledger
)
from llm_kosh.core.memory import ensure_root
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
          created TEXT, supersedes TEXT, superseded_by TEXT, source_receipt TEXT,
          M_sal REAL
        );
        CREATE INDEX IF NOT EXISTS idx_docs_project ON documents(project);
        CREATE INDEX IF NOT EXISTS idx_docs_kind ON documents(kind);
        CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_docs_visibility ON documents(visibility);
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
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
            "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, meta.get("type") or "note", meta.get("title") or path.stem,
             meta.get("project", ""), meta.get("visibility", "private"),
             meta.get("status", "active"), str(path.relative_to(root)), body,
             sha256_file(path), meta.get("created", ""), meta.get("supersedes", ""),
             meta.get("superseded_by", ""), meta.get("source_receipt", ""),
             float(meta.get("M_sal") or meta.get("salience") or 1.0)),
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


def _parse_time(iso_str: str) -> float:
    if not iso_str:
        return 0.0
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0

def extract_procedural_features(text: str) -> str:
    if not text:
        return "procedural"
    code_blocks = re.findall(r"```[a-zA-Z0-9]*\n(.*?)```", text, re.DOTALL)
    code_text = " ".join(code_blocks)
    funcs = re.findall(r"(?:def|function|class|import|const|let|var)\s+([a-zA-Z0-9_]+)", text)
    assignments = re.findall(r"([a-zA-Z0-9_]+)\s*=", text)
    features = funcs + assignments
    feature_text = " ".join(features)
    combined = (code_text + " " + feature_text).strip()
    return combined if combined else "procedural"

def _load_candidate_embeddings(root: Path, item_ids: List[str]) -> Tuple[dict, dict]:
    vdb = root / VECTOR_DB
    if not vdb.exists():
        return {}, {}
    conn = sqlite3.connect(str(vdb))
    try:
        res = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vec_docs_sem'").fetchone()
        if res:
            rows_sem = conn.execute(
                """SELECT v.id, d.embedding FROM vec_docs_sem d
                   JOIN vectors v ON v.rowid = d.rowid
                   WHERE v.id IN (""" + ",".join("?" for _ in item_ids) + ")",
                item_ids
            ).fetchall()
            rows_proc = conn.execute(
                """SELECT v.id, d.embedding FROM vec_docs_proc d
                   JOIN vectors v ON v.rowid = d.rowid
                   WHERE v.id IN (""" + ",".join("?" for _ in item_ids) + ")",
                item_ids
            ).fetchall()
            import struct
            embeddings_sem = {}
            embeddings_proc = {}
            for row in rows_sem:
                k, v = row[0], row[1]
                if isinstance(v, bytes):
                    dim = len(v) // 4
                    embeddings_sem[k] = list(struct.unpack(f"{dim}f", v))
                else:
                    embeddings_sem[k] = v
            for row in rows_proc:
                k, v = row[0], row[1]
                if isinstance(v, bytes):
                    dim = len(v) // 4
                    embeddings_proc[k] = list(struct.unpack(f"{dim}f", v))
                else:
                    embeddings_proc[k] = v
            return embeddings_sem, embeddings_proc
        else:
            rows = conn.execute(
                "SELECT id, vec_sem, vec_proc FROM vectors WHERE id IN (" + ",".join("?" for _ in item_ids) + ")",
                item_ids
            ).fetchall()
            import json
            embeddings_sem = {}
            embeddings_proc = {}
            for r in rows:
                embeddings_sem[r[0]] = json.loads(r[1]) if r[1] else None
                embeddings_proc[r[0]] = json.loads(r[2]) if r[2] else None
            return embeddings_sem, embeddings_proc
    except Exception:
        return {}, {}
    finally:
        conn.close()

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
            "d.supersedes,d.superseded_by,d.source_receipt,d.created,d.M_sal")
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
            
    proj_rows = conn.execute("SELECT project, count(*) FROM documents GROUP BY project").fetchall()
    project_counts = {row[0].lower() if row[0] else "": row[1] for row in proj_rows}
    conn.close()

    items = [{
        "id": r[0], "kind": r[1], "title": r[2], "project": r[3], "visibility": r[4],
        "status": r[5], "path": r[6], "body": r[7], "snippet": make_snippet(r[7] or "", query),
        "supersedes": r[8], "superseded_by": r[9], "source_receipt": r[10], "created": r[11],
        "t": _parse_time(r[11]), "M_sal": float(r[12] if r[12] is not None else 1.0)
    } for r in rows]

    if rerank and items and query.strip():
        meta = _vmeta(root)
        embeddings_sem = {}
        embeddings_proc = {}
        qv_sem = None
        qv_proc = None
        if meta:
            try:
                is_tfidf = (meta["backend"] == "tfidf") or (meta["backend"].startswith("plugin:") and not meta["model"])
                if is_tfidf:
                    emb = TfidfEmbedder()
                    emb.idf = json.loads(meta["idf"] or "{}")
                    qv_sem_sparse = emb.embed(query)
                    qv_proc_sparse = emb.embed(extract_procedural_features(query))
                    vocab = sorted(emb.idf.keys())
                    qv_sem = [float(qv_sem_sparse.get(term, 0.0)) for term in vocab]
                    qv_proc = [float(qv_proc_sparse.get(term, 0.0)) for term in vocab]
                else:
                    emb = get_embedder("st", meta["model"] or "all-MiniLM-L6-v2")
                    qv_sem_sparse = emb.embed(query)
                    qv_proc_sparse = emb.embed(extract_procedural_features(query))
                    qv_sem = [float(qv_sem_sparse[str(i)]) for i in range(len(qv_sem_sparse))]
                    qv_proc = [float(qv_proc_sparse[str(i)]) for i in range(len(qv_proc_sparse))]
                embeddings_sem, embeddings_proc = _load_candidate_embeddings(root, [it["id"] for it in items])
            except Exception:
                qv_sem = None
                qv_proc = None
        
        if qv_sem is None or qv_proc is None:
            corpus_sem = [tokenize(_doc_text(it)) for it in items]
            corpus_proc = [tokenize(extract_procedural_features(it["body"])) for it in items]
            idf = _build_idf(corpus_sem + corpus_proc + [tokenize(query)])
            vocab = sorted(idf.keys())
            
            def to_dense(sparse_dict, vocabulary):
                return [float(sparse_dict.get(term, 0.0)) for term in vocabulary]
                
            qv_sem = to_dense(_vec(tokenize(query), idf), vocab)
            qv_proc = to_dense(_vec(tokenize(extract_procedural_features(query)), idf), vocab)
            for it, toks_sem, toks_proc in zip(items, corpus_sem, corpus_proc):
                it["embedding_sem"] = to_dense(_vec(toks_sem, idf), vocab)
                it["embedding_proc"] = to_dense(_vec(toks_proc, idf), vocab)
        else:
            for it in items:
                val_sem = embeddings_sem.get(it["id"])
                val_proc = embeddings_proc.get(it["id"])
                if isinstance(val_sem, dict):
                    try:
                        vocab = sorted(json.loads(meta.get("idf", "{}")).keys())
                        val_sem = [float(val_sem.get(term, 0.0)) for term in vocab]
                    except Exception:
                        val_sem = [0.0] * len(qv_sem)
                if isinstance(val_proc, dict):
                    try:
                        vocab = sorted(json.loads(meta.get("idf", "{}")).keys())
                        val_proc = [float(val_proc.get(term, 0.0)) for term in vocab]
                    except Exception:
                        val_proc = [0.0] * len(qv_proc)
                if not val_sem:
                    val_sem = [0.0] * len(qv_sem)
                if not val_proc:
                    val_proc = [0.0] * len(qv_proc)
                it["embedding_sem"] = val_sem
                it["embedding_proc"] = val_proc

        from llm_kosh.engine.receipt_dag import ReceiptDAG
        from llm_kosh.engine.tensor_fusion import retrieve_memory_tensor
        import time
        
        dag = ReceiptDAG(root)
        cfg = read_json(root / "LLM_KOSH.json", {}) or {}
        retrieval_weights = cfg.get("retrieval_weights", {})
        task_context = {
            "beta_sem": float(retrieval_weights.get("beta_sem", 0.7)),
            "beta_proc": float(retrieval_weights.get("beta_proc", 0.3)),
            "alpha": float(retrieval_weights.get("alpha", 0.02)),
            "gamma": float(retrieval_weights.get("gamma", 0.5)),
            "tau": float(retrieval_weights.get("tau", 0.5)),
            "radiance_threshold": float(retrieval_weights.get("radiance_threshold", 0.1)),
            "radiance_window": float(retrieval_weights.get("radiance_window", 60.0)),
            "radiance_fraction": float(retrieval_weights.get("radiance_fraction", 0.3)),
            "sequence_coherence_bonus": float(retrieval_weights.get("sequence_coherence_bonus", 0.2))
        }
        
        items = retrieve_memory_tensor(
            query_vector_sem=qv_sem,
            query_vector_proc=qv_proc,
            query_time=time.time(),
            candidates=items,
            task_context=task_context,
            dag=dag,
            project_counts=project_counts
        )
    else:
        for it in items:
            it["score"] = None

    for it in items:
        it.pop("body", None)
        it.pop("embedding_sem", None)
        it.pop("embedding_proc", None)
        
    final_results = items[:limit]
    if final_results:
        import time
        valid_times = [(r, float(r.get("t", 0.0) or r.get("created_t", 0.0) or 0.0)) for r in final_results]
        valid_times = [x for x in valid_times if x[1] > 0]
        if len(valid_times) > 1:
            valid_times.sort(key=lambda x: x[1])  # Oldest to newest
            
            def format_time_diff(t_val):
                diff = time.time() - t_val
                if diff < 60: return f"{int(diff)} seconds ago"
                if diff < 3600: return f"{int(diff/60)} minutes ago"
                if diff < 86400: return f"{int(diff/3600)} hours ago"
                return f"{int(diff/86400)} days ago"
                
            timeline_str = " -> ".join([f"'{x[0]['title']}' ({format_time_diff(x[1])})" for x in valid_times])
            final_results[0]["snippet"] = f"[CHRONOLOGICAL TIMELINE: {timeline_str}] " + final_results[0].get("snippet", "")
            
    return final_results


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

def _any_cosine(a, b) -> float:
    if isinstance(a, dict) and isinstance(b, dict):
        return _cosine(a, b)
    if isinstance(a, dict):
        try:
            a = [float(a[str(i)]) for i in range(len(a))]
        except KeyError:
            keys = sorted(a.keys())
            a = [float(a[k]) for k in keys]
    if isinstance(b, dict):
        try:
            b = [float(b[str(i)]) for i in range(len(b))]
        except KeyError:
            keys = sorted(b.keys())
            b = [float(b[k]) for k in keys]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0

def build_vector_index(root: Path, backend: str = "tfidf", model: str = "all-MiniLM-L6-v2") -> dict:
    ensure_root(root)
    rebuild_index(root)
    conn = get_db(root)
    rows = conn.execute("SELECT id,kind,status,title,body FROM documents").fetchall()
    conn.close()
    
    texts_sem = [_doc_text({"title": r[3], "body": r[4]}) for r in rows]
    texts_proc = [extract_procedural_features(r[4]) for r in rows]
    
    emb = get_embedder(backend, model)
    idf_json = ""
    if isinstance(emb, TfidfEmbedder):
        emb.fit(texts_sem + texts_proc)
        idf_json = json.dumps(emb.idf)
        
    vecs_sem = emb.embed_many(texts_sem) if rows else []
    vecs_proc = emb.embed_many(texts_proc) if rows else []
    dim = len(emb.idf) if isinstance(emb, TfidfEmbedder) else (len(vecs_sem[0]) if vecs_sem else 0)

    from llm_kosh.core.plugins import PluginManager
    vs_plugin = PluginManager.get_vector_store_plugin(root)
    if vs_plugin:
        vdb = root / VECTOR_DB
        if vdb.exists():
            vdb.unlink()
        vc = sqlite3.connect(str(vdb))
        vc.executescript(
            "CREATE TABLE vmeta(backend TEXT, model TEXT, dim INT, idf TEXT, built_at TEXT, count INT);"
        )
        vc.execute("INSERT INTO vmeta VALUES (?,?,?,?,?,?)",
                   (f"plugin:{type(vs_plugin).__name__}", getattr(emb, "model_name", ""),
                    dim, idf_json, now_iso(), len(rows)))
        vc.commit()
        vc.close()
        
        ids = [r[0] for r in rows]
        kinds = [r[1] for r in rows]
        statuses = [r[2] for r in rows]
        
        def to_list(v):
            if isinstance(v, dict):
                try:
                    return [float(v[str(i)]) for i in range(len(v))]
                except KeyError:
                    keys = sorted(v.keys())
                    return [float(v[k]) for k in keys]
            return list(v)

        vecs_sem_list = [to_list(v) for v in vecs_sem]
        vecs_proc_list = [to_list(v) for v in vecs_proc]
        
        vs_plugin.initialize(root, dim, getattr(emb, "name", backend), getattr(emb, "model_name", ""), json.loads(idf_json) if idf_json else {})
        vs_plugin.add_vectors(ids, kinds, statuses, vecs_sem_list, vecs_proc_list)
        append_ledger(root, "vector_index.built", {"backend": f"plugin:{type(vs_plugin).__name__}", "dim": dim, "count": len(rows)})
        return {"backend": f"plugin:{type(vs_plugin).__name__}", "dim": dim, "count": len(rows)}

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
            "CREATE TABLE vectors(id TEXT PRIMARY KEY, kind TEXT, status TEXT, vec_sem TEXT, vec_proc TEXT);"
            f"CREATE VIRTUAL TABLE vec_docs_sem USING vec0(embedding float[{dim}]);"
            f"CREATE VIRTUAL TABLE vec_docs_proc USING vec0(embedding float[{dim}]);"
            "CREATE TABLE vmeta(backend TEXT, model TEXT, dim INT, idf TEXT, built_at TEXT, count INT);"
        )
        for r, v_sem, v_proc in zip(rows, vecs_sem, vecs_proc):
            cur = vc.execute("INSERT INTO vectors (id, kind, status, vec_sem, vec_proc) VALUES (?,?,?,?,?)", 
                             (r[0], r[1], r[2], None, None))
            rowid = cur.lastrowid
            vc.execute("INSERT INTO vec_docs_sem(rowid, embedding) VALUES (?,?)",
                       (rowid, _serialize_vec(v_sem)))
            vc.execute("INSERT INTO vec_docs_proc(rowid, embedding) VALUES (?,?)",
                       (rowid, _serialize_vec(v_proc)))
    else:
        vc.executescript(
            "CREATE TABLE vectors(id TEXT PRIMARY KEY, kind TEXT, status TEXT, vec_sem TEXT, vec_proc TEXT);"
            "CREATE TABLE vmeta(backend TEXT, model TEXT, dim INT, idf TEXT, built_at TEXT, count INT);"
        )
        for r, v_sem, v_proc in zip(rows, vecs_sem, vecs_proc):
            vc.execute("INSERT OR REPLACE INTO vectors VALUES (?,?,?,?,?)",
                       (r[0], r[1], r[2], json.dumps(v_sem), json.dumps(v_proc)))
                       
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
        raise SystemExit("No vector index yet. Build one:  llm_kosh_cli.py --root <root> embed")
        
    cfg = read_json(root / "LLM_KOSH.json", {}) or {}
    retrieval_weights = cfg.get("retrieval_weights", {})
    beta_sem = float(retrieval_weights.get("beta_sem", 0.7))
    beta_proc = float(retrieval_weights.get("beta_proc", 0.3))

    is_tfidf = (meta["backend"] == "tfidf") or (meta["backend"].startswith("plugin:") and not meta["model"])
    if is_tfidf:
        emb = TfidfEmbedder()
        emb.idf = json.loads(meta["idf"] or "{}")
        qv_sem_sparse = emb.embed(query)
        qv_proc_sparse = emb.embed(extract_procedural_features(query))
        vocab = sorted(emb.idf.keys())
        qv_sem = [float(qv_sem_sparse.get(term, 0.0)) for term in vocab]
        qv_proc = [float(qv_proc_sparse.get(term, 0.0)) for term in vocab]
    else:
        emb = get_embedder("st", meta["model"] or "all-MiniLM-L6-v2")
        qv_sem_sparse = emb.embed(query)
        qv_proc_sparse = emb.embed(extract_procedural_features(query))
        qv_sem = [float(qv_sem_sparse[str(i)]) for i in range(len(qv_sem_sparse))]
        qv_proc = [float(qv_proc_sparse[str(i)]) for i in range(len(qv_proc_sparse))]

    from llm_kosh.core.plugins import PluginManager
    vs_plugin = PluginManager.get_vector_store_plugin(root)
    if vs_plugin:
        def to_list(v):
            if isinstance(v, dict):
                try:
                    return [float(v[str(i)]) for i in range(len(v))]
                except KeyError:
                    keys = sorted(v.keys())
                    return [float(v[k]) for k in keys]
            return list(v)
            
        qv_sem_list = to_list(qv_sem)
        qv_proc_list = to_list(qv_proc)
        
        plugin_res = vs_plugin.search(qv_sem_list, qv_proc_list, k, kinds=kinds, active_only=active_only)
        scored = []
        conn = get_db(root)
        for s, rid in plugin_res:
            row = conn.execute("SELECT kind, status FROM documents WHERE id=?", (rid,)).fetchone()
            if row:
                scored.append((s, rid, row[0], row[1]))
        conn.close()
        scored.sort(reverse=True)
        scored = scored[:k]
    else:
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
                
            k_search = max(k * 5, 25)
            query_sql_sem = f"""
                SELECT v.id, v.kind, v.status, 1.0 - vec_distance_cosine(d.embedding, ?) as score
                FROM vec_docs_sem d
                JOIN vectors v ON v.rowid = d.rowid
                WHERE d.embedding MATCH ? AND k = {k_search} {where}
            """
            query_sql_proc = f"""
                SELECT v.id, v.kind, v.status, 1.0 - vec_distance_cosine(d.embedding, ?) as score
                FROM vec_docs_proc d
                JOIN vectors v ON v.rowid = d.rowid
                WHERE d.embedding MATCH ? AND k = {k_search} {where}
            """
            vrows_sem = vc.execute(query_sql_sem, (_serialize_vec(qv_sem), _serialize_vec(qv_sem), *params)).fetchall()
            vrows_proc = vc.execute(query_sql_proc, (_serialize_vec(qv_proc), _serialize_vec(qv_proc), *params)).fetchall()
            
            all_ids = list(set([r[0] for r in vrows_sem] + [r[0] for r in vrows_proc]))
            vc.close()
            
            embeddings_sem, embeddings_proc = _load_candidate_embeddings(root, all_ids)
            scored = []
            
            id_info = {}
            for r in vrows_sem:
                id_info[r[0]] = (r[1], r[2])
            for r in vrows_proc:
                id_info[r[0]] = (r[1], r[2])
                
            for rid in all_ids:
                kind, status = id_info[rid]
                val_sem = embeddings_sem.get(rid)
                val_proc = embeddings_proc.get(rid)
                if not val_sem:
                    val_sem = [0.0] * len(qv_sem)
                if not val_proc:
                    val_proc = [0.0] * len(qv_proc)
                    
                cos_sem = _any_cosine(qv_sem, val_sem)
                cos_proc = _any_cosine(qv_proc, val_proc)
                s = beta_sem * cos_sem + beta_proc * cos_proc
                if s > 0:
                    scored.append((s, rid, kind, status))
            scored.sort(reverse=True)
            scored = scored[:k]
        else:
            vrows = vc.execute("SELECT id,kind,status,vec_sem,vec_proc FROM vectors").fetchall()
            vc.close()
            scored = []
            for rid, kind, status, vec_sem, vec_proc in vrows:
                if active_only and status != "active":
                    continue
                if kinds and kind not in kinds:
                    continue
                
                val_sem = json.loads(vec_sem) if vec_sem else None
                val_proc = json.loads(vec_proc) if vec_proc else None
                if isinstance(val_sem, dict):
                    try:
                        vocab = sorted(json.loads(meta.get("idf", "{}")).keys())
                        val_sem = {term: float(val_sem.get(term, 0.0)) for term in vocab}
                    except Exception:
                        val_sem = {}
                if isinstance(val_proc, dict):
                    try:
                        vocab = sorted(json.loads(meta.get("idf", "{}")).keys())
                        val_proc = {term: float(val_proc.get(term, 0.0)) for term in vocab}
                    except Exception:
                        val_proc = {}
                if not val_sem:
                    val_sem = {}
                if not val_proc:
                    val_proc = {}
                    
                cos_sem = _any_cosine(qv_sem, val_sem)
                cos_proc = _any_cosine(qv_proc, val_proc)
                s = beta_sem * cos_sem + beta_proc * cos_proc
                if s > 0:
                    scored.append((s, rid, kind, status))
            scored.sort(reverse=True)
            scored = scored[:k]

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

def get_memory_map(root):
    from llm_kosh.engine.search import rebuild_index, get_db
    rebuild_index(root)
    conn = get_db(root)
    projects = {}
    rows = conn.execute("SELECT project, kind, COUNT(*) FROM documents WHERE status='active' AND project != '' GROUP BY project, kind").fetchall()
    for proj, kind, count in rows:
        if proj not in projects:
            projects[proj] = {}
        projects[proj][kind] = count
    
    orphans = {}
    rows_orphans = conn.execute("SELECT kind, COUNT(*) FROM documents WHERE status='active' AND (project IS NULL OR project = '') GROUP BY kind").fetchall()
    for kind, count in rows_orphans:
        orphans[kind] = count
    
    conn.close()
    return {
        "projects": projects,
        "unassigned": orphans
    }

def get_project_context(root, project_name: str):
    from llm_kosh.engine.search import rebuild_index, get_db
    rebuild_index(root)
    conn = get_db(root)
    out = []
    rows = conn.execute(
        "SELECT id, kind, title, visibility, status, path, body, supersedes, superseded_by, source_receipt "
        "FROM documents WHERE status='active' AND LOWER(project) = LOWER(?)", 
        (project_name,)
    ).fetchall()
    for d in rows:
        out.append({
            "id": d[0], "kind": d[1], "title": d[2], "visibility": d[3],
            "status": d[4], "path": d[5], "body": d[6], 
            "supersedes": d[7], "superseded_by": d[8], "source_receipt": d[9]
        })
    conn.close()
    return out

def list_open_corrections(root):
    from llm_kosh.engine.search import rebuild_index, get_db
    rebuild_index(root)
    conn = get_db(root)
    out = []
    rows = conn.execute(
        "SELECT id, title, path, body, supersedes "
        "FROM documents WHERE kind='correction' AND status='open'"
    ).fetchall()
    for d in rows:
        out.append({
            "id": d[0], "title": d[1], "path": d[2], "body": d[3], "supersedes": d[4]
        })
    conn.close()
    return out

def daemon_status(root) -> str:
    pid_file = root / 'indexes' / 'daemon.pid'
    if not pid_file.exists():
        return 'Daemon is NOT running.'
    try:
        import psutil
        pid = int(pid_file.read_text(encoding='utf-8').strip())
        if psutil.pid_exists(pid):
            return f'Daemon IS running (PID: {pid}).'
    except Exception:
        pass
    return 'Daemon is NOT running (stale PID file).'
