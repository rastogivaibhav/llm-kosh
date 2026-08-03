
from llm_kosh.core.constants import *
from llm_kosh.core.utils import *
from llm_kosh.core.memory import *
from llm_kosh.engine.search import *
from llm_kosh.engine.search import _vmeta, _fts_query
from llm_kosh.engine.safety import *
from llm_kosh.engine.compiler import *
from llm_kosh.engine.healing import absorb_receipt, resolve

import os, re, json, uuid, shutil, zipfile, sqlite3, argparse, datetime as dt
from datetime import timezone

UTC = timezone.utc
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

FOLDER_TO_KIND = {
    "projects": "project", "decisions": "decision", "prompts": "prompt",
    "notes": "note", "generated-files": "file", "intake": "file", "conversations": "conversation",
    "receipts": "receipt", "corrections": "correction", "gaps": "gap",
    "suggestions": "suggestion",
}



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
    """Verify every ledger row parses, and verify the tamper-evident hash chain.

    Rows written by v2.1.1+ carry `prev`/`row_hash`; each is recomputed and
    checked against its predecessor. Legacy rows (no hash fields) are counted
    separately and still considered valid for backward compatibility.
    """
    from llm_kosh.core.utils import row_hash as _row_hash, GENESIS_HASH
    ensure_root(root)
    path = root / "ledger" / "events.jsonl"
    good, bad_lines, legacy = 0, [], 0
    chain_breaks: list = []
    expected_prev = GENESIS_HASH
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
                    continue
            except json.JSONDecodeError:
                bad_lines.append(i)
                continue
            if "row_hash" not in row:
                legacy += 1
                continue
            if _row_hash(row) != row["row_hash"]:
                chain_breaks.append({"line": i, "type": "row_hash_mismatch"})
            elif row.get("prev") != expected_prev and expected_prev != GENESIS_HASH:
                chain_breaks.append({"line": i, "type": "broken_link",
                                     "expected_prev": expected_prev, "got": row.get("prev")})
            expected_prev = row["row_hash"]
    result = {"good_rows": good, "bad_rows": len(bad_lines), "bad_lines": bad_lines,
              "legacy_rows": legacy, "chained_rows": good - legacy - len(bad_lines),
              "chain_breaks": chain_breaks, "chain_intact": not chain_breaks}
    if not quiet:
        print(f"Ledger: {good} valid row(s), {len(bad_lines)} bad row(s).")
        chained = result["chained_rows"]
        if chained > 0 or legacy > 0:
            status = "INTACT" if not chain_breaks else f"BROKEN ({len(chain_breaks)} break(s))"
            print(f"  Hash chain: {status} — {chained} chained, {legacy} legacy row(s).")
        if chain_breaks:
            for b in chain_breaks[:10]:
                print(f"    line {b['line']}: {b['type']}")
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
            cfg = read_json(root / "LLM_KOSH.json", {})
            (root / "BOOT.md").write_text(boot_text(cfg.get("owner", "")), encoding="utf-8")

    if dry_run:
        print(f"DRY RUN — {len(repairs)} repair(s) would be applied:")
        for r in repairs:
            print(f"  - {r}")
        return {"repairs": repairs, "applied": False}

    rebuild_index(root, force=True)
    vmeta_cache = _vmeta(root)
    if vmeta_cache:  # keep an existing vector index fresh
        build_vector_index(root, backend=vmeta_cache["backend"], model=vmeta_cache.get("model") or "all-MiniLM-L6-v2")
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
    if not root.exists():
        print(f"LlmKosh v{APP_VERSION}: {root}")
        print("Cartridge status: not initialized")
        return
    index = inspect_index(root)
    counts = index["by_kind"]
    total = index["documents"]
    superseded = index["superseded"]
    ledger_path = root / "ledger" / "events.jsonl"
    events = sum(1 for _ in ledger_path.open("r", encoding="utf-8")) if ledger_path.exists() else 0
    print(f"LlmKosh v{APP_VERSION}: {root}")
    print(f"Source documents: {index['source_documents']}")
    print(f"Indexed documents: {total}  (superseded: {superseded})")
    if not index["healthy"]:
        print(f"Index status: unhealthy ({index['error'] or 'integrity check failed'}); run `llm-kosh index`")
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
    from llm_kosh.core.utils import parse_frontmatter
    hashes = set()
    active_dir = root / "active"
    if active_dir.exists():
        for f in active_dir.rglob("*.md"):
            try:
                meta, _ = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
                if "source_hash" in meta:
                    hashes.add(meta["source_hash"])
            except Exception:
                pass
    return hashes

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

PARTITION_ORDER = ["private", "personal", "work-safe", "shareable", "public", "blocked", "quarantine"]

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



BACKUP_INCLUDE = ["source", "ledger", "attachments", "reports"]

BACKUP_FILES = ["LLM_KOSH.json", "LLM_KOSH_POLICY.json", "BOOT.md", "MEMORY_MAP.md"]

def export_backup(root: Path, out: Path) -> Path:
    """Write a portable backup zip of the source of truth (no derived indexes)."""
    ensure_root(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = read_json(root / "LLM_KOSH.json", {}) or {}
    meta = {
        "schema": "koush-backup.v1", "created_at": now_iso(),
        "app_version": APP_VERSION,
        "koush_id": cartridge_meta(root)["koush_id"],
        "koush_version": cfg.get("version", APP_VERSION),
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
        existing = (root / "LLM_KOSH.json").exists()
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
                   "from_cartridge": manifest.get("koush_id"),
                   "backup_app_version": manifest.get("app_version")})
    print(f"Restored {restored} file(s) from {backup}")
    print(f"  cartridge: {manifest.get('koush_id')} (backup made with v{manifest.get('app_version')})")
    print("  rebuilt FTS index. Run `embed` to rebuild the vector index if you use semantic search.")
    return {"restored": restored, "manifest": manifest}

def migrate(root: Path, dry_run: bool = False) -> dict:
    """Explicit, reversible migration: stamp current app version and ensure a
    koush_id exists. Never rewrites memory content. Records the prior version."""
    ensure_root(root)
    cfg = read_json(root / "LLM_KOSH.json", {}) or {}
    from_version = cfg.get("version", "unknown")
    changes = []
    if from_version != APP_VERSION:
        changes.append(f"version {from_version} -> {APP_VERSION}")
    if not cfg.get("koush_id"):
        changes.append("add koush_id")
    if not changes:
        print(f"Already at v{APP_VERSION}; nothing to migrate.")
        return {"migrated": False, "from": from_version}
    if dry_run:
        print(f"DRY RUN — would apply: {', '.join(changes)}")
        return {"migrated": False, "planned": changes, "from": from_version}

    new_cfg = dict(cfg)
    new_cfg["version"] = APP_VERSION
    if not new_cfg.get("koush_id"):
        new_cfg["koush_id"] = cartridge_meta(root)["koush_id"]  # deterministic
    history = new_cfg.get("migrated_from", [])
    if not isinstance(history, list):
        history = [history]
    history.append({"from": from_version, "to": APP_VERSION, "at": now_iso()})
    new_cfg["migrated_from"] = history
    write_json(root / "LLM_KOSH.json", new_cfg)
    append_ledger(root, "cartridge.migrated", {"from": from_version, "to": APP_VERSION})
    print(f"Migrated cartridge: {', '.join(changes)}")
    print("  (reversible: prior version recorded in LLM_KOSH.json 'migrated_from')")
    return {"migrated": True, "from": from_version, "to": APP_VERSION, "changes": changes}
