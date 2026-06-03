import json
import re
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from koush.core.constants import SHAREABLE_VIS
from koush.core.utils import now_iso, read_json, write_json, append_ledger, parse_frontmatter
from koush.core.memory import (
    add_memory, update_doc_meta, find_doc_by_id, supersede, ensure_root
)
from koush.engine.search import (
    rebuild_index, best_match, get_db, corpus_fingerprint, iter_source_files, top_matches
)
from koush.engine.safety import scan_secrets

RECEIPT_SECTIONS = {
    "new decisions": "decision",
    "corrections": "correction",
    "generated files": "file",
    "open gaps": "gap",
    "suggested memory updates": "suggestion",
}

_TAG_RE = re.compile(r"\[(?P<key>[a-zA-Z_]+)\s*:\s*(?P<val>[^\]]+)\]")

def _parse_bullet(line: str) -> dict:
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
            if bullet["title"] in {"...", "(untitled)", ""} and not bullet["body"].strip("."):
                continue
            sections[current].append(bullet)
    return sections

def absorb_receipt(root: Path, receipt_path: Path, dry_run: bool = False, review_id: str = None) -> dict:
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

    receipt_title = f"Receipt {receipt_path.stem}"
    receipt_doc = add_memory(root, "receipt", receipt_title, text, project="",
                             visibility="private", reindex=False, quiet=True)
    receipt_meta, _ = parse_frontmatter(receipt_doc.read_text(encoding="utf-8"))
    receipt_id = receipt_meta["id"]

    for it in parsed["decision"]:
        add_memory(root, "decision", it["title"], it["body"], project=it["project"],
                   visibility="private", extra_meta={"source_receipt": receipt_id},
                   reindex=False, quiet=True)
        summary["decisions"] += 1
        summary["actions"].append(f"decision: {it['title']}")

    rebuild_index(root, force=True)
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
        "source": str(receipt_path), "receipt_id": receipt_id, "review_id": review_id,
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

    if correction and target:
        if not supersede(root, target, correction, reason="manual resolve"):
            raise SystemExit(f"Target not found: {target}")
        update_doc_meta(root, _correction_rel(correction), {"status": "active", "resolved": "manual"})
        rebuild_index(root, force=True)
        append_ledger(root, "correction.resolved", {"correction": correction, "target": target, "mode": "manual"})
        print(f"Resolved: {correction} now supersedes {target}.")
        result["applied"] = 1
        return result

    if correction and dismiss:
        update_doc_meta(root, _correction_rel(correction), {"status": "active", "resolved": "dismissed"})
        rebuild_index(root, force=True)
        append_ledger(root, "correction.resolved", {"correction": correction, "mode": "dismissed"})
        print(f"Dismissed: {correction} kept as a standalone memory (supersedes nothing).")
        result["dismissed"] = 1
        return result

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
        print(f"Auto-resolve: {result['applied']} applied, {result['still_open']} still open.")
        return result

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
    return result

