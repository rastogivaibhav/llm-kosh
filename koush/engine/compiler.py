import json
import hashlib
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from koush.core.constants import APP_VERSION
from koush.core.utils import (
    now_iso, read_json, write_json, slugify, append_ledger, parse_frontmatter
)
from koush.core.memory import ensure_root
from koush.engine.safety import redact_text, scan_secrets, load_policy


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
                          "koush_id", "koush_version"]


def cartridge_meta(root: Path) -> dict:
    cfg = read_json(root / "KOUSH.json", {}) or {}
    cid = cfg.get("koush_id")
    if not cid:
        seed = (cfg.get("owner", "") + "|" + cfg.get("created_at", "")).encode("utf-8")
        cid = "cart_" + hashlib.sha256(seed).hexdigest()[:12]
    return {"koush_id": cid, "koush_version": cfg.get("version", APP_VERSION),
            "owner": cfg.get("owner", "")}

def _provider_context(profile: str, query: str, decisions: List[dict], projects: List[dict], n: int) -> Tuple[str, str]:
    fname = PROVIDER_FILE.get(profile, "CONTEXT.md")
    dlist = "\n".join(f"- {d['title']}" for d in decisions[:12]) or "- (none in this pack)"
    if profile == "deepseek":
        body = (f"CARTRIDGE CONTEXT (deepseek)\nQUERY: {query}\nITEMS: {n}\n"
                f"READ 01_BOOT.md FIRST, THEN 02..12 IN ORDER.\n"
                f"DECISIONS:\n{dlist}\n"
                f"DO NOT ASSUME ANYTHING NOT IN 04_MATCHED_MEMORY.md OR 05_DECISIONS.md.\n"
                f"RETURN A MEMORY_RECEIPT AT THE END (SEE 12_MEMORY_RECEIPT_TEMPLATE.md).\n")
        return fname, body
    if profile == "codex":
        plist = "\n".join(f"- {p['title']}" for p in projects[:12]) or "- (none in this pack)"
        body = (f"# Codex Context\n\nTask query: {query}\n\n"
                f"This pack is a code/engineering context extract. Prioritise project and "
                f"decision records below; treat them as binding constraints on any code you write.\n\n"
                f"## Projects in scope\n{plist}\n\n## Active engineering decisions\n{dlist}\n\n"
                f"Read 01_BOOT.md, then 03_TASK_CONTEXT.md and 05_DECISIONS.md. Do not invent APIs, "
                f"services, or files not present in 04_MATCHED_MEMORY.md / 08_GENERATED_FILES.md. "
                f"Return a MEMORY_RECEIPT at the end.\n")
        return fname, body
    if profile == "human":
        body = (f"# Handover Note\n\nYou're picking up work related to: **{query}**.\n\n"
                f"This pack is a snapshot of the relevant memory: {n} item(s), including the "
                f"decisions listed below. Start with 02_CONTEXT_BRIEF.md and 03_TASK_CONTEXT.md "
                f"for framing, then 05_DECISIONS.md for what's already settled and "
                f"06_OPEN_GAPS.md / 09_DO_NOT_ASSUME.md for what isn't. The full source for every "
                f"item is under source-files/ and mapped in 10_SOURCE_MAP.json.\n\n"
                f"## Decisions already made\n{dlist}\n")
        return fname, body
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
    from koush.engine.search import query_memory, read_doc
    ensure_root(root)
    profile = target if target in PACK_PROFILES else "chatgpt"
    b_docs, b_chars = BUDGETS.get(budget, BUDGETS["medium"])
    eff_max_docs = max_docs if max_docs is not None else (b_docs if budget else limit)
    eff_max_chars = max_chars if max_chars is not None else b_chars

    matches = query_memory(root, query, limit=eff_max_docs,
                           include_private=include_private,
                           active_only=not include_superseded)

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

    _pack_dropped = dropped 

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

    open_gaps = query_memory(root, query or "gap", limit=20, include_private=include_private,
                             kinds=["gap"])
    open_gaps = [g for g in open_gaps if g["status"] in ("open", "active")]
    open_corr = [c for c in query_memory(root, query or "correction", limit=20,
                                         include_private=include_private, kinds=["correction"])
                 if c["status"] == "open"]

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
        f"**Cartridge:** {meta['koush_id']} (v{meta['koush_version']})\n\n"
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
        "koush_id": meta["koush_id"], "koush_version": meta["koush_version"],
        "query": query, "matches": source_map,
    })

    manifest = {
        "schema": "ai-memory-context-pack.v1", "created_at": now_iso(),
        "target": profile, "query": query,
        "koush_id": meta["koush_id"], "koush_version": meta["koush_version"],
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
        "koush_id": meta["koush_id"],
    })
    print(f"Created context pack: {out}")
    print(f"  profile: {profile} · matched: {len(matches)} · included: {manifest['docs_selected']}"
          + (f" · omitted(budget): {omitted}" if omitted else ""))
    print(f"  chars: {chars_used}/{eff_max_chars} · size: {pack_size} bytes"
          + (f" · redactions: {redactions}" if redactions else ""))
    return manifest


def validate_pack(zip_path: Path) -> dict:
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
    print(f"  cartridge      : {man.get('koush_id')} (v{man.get('koush_version')})")
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
