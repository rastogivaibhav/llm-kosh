import os
import uuid
import json
import re
from pathlib import Path
from typing import Dict, Any, List

from llm_kosh.core.utils import read_json, write_json, now_iso, slugify
from llm_kosh.core.memory import ensure_root
from llm_kosh.engine.healing import parse_receipt

def ensure_review_dir(root: Path) -> Path:
    d = root / "reports" / "receipt_reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _generate_review_report(root: Path, receipt_path: Path) -> Dict[str, Any]:
    text = receipt_path.read_text(encoding="utf-8")
    sections = parse_receipt(text)
    
    decisions = sections.get("decision", [])
    corrections = sections.get("correction", [])
    files = sections.get("file", [])
    gaps = sections.get("gap", [])
    suggestions = sections.get("suggestion", [])
    
    high_impact = []
    missing_projects = []
    unknown_refs = []
    
    for c in corrections:
        if not c.get("ref"):
            unknown_refs.append(c["title"])
        elif "delete" in c["body"].lower() or "remove" in c["body"].lower():
            high_impact.append(f"Correction on {c['ref']} mentions deletion.")
            
    for d in decisions:
        if not d.get("project"):
            missing_projects.append(d["title"])
            
    possible_prompt_injection = []
    for sect, items in sections.items():
        for i in items:
            if "<script>" in i["body"] or "IGNORE ALL PREVIOUS INSTRUCTIONS" in i["body"].upper():
                possible_prompt_injection.append(f"Suspicious payload in {sect}: {i['title']}")

    report = {
        "review_id": f"rev_{uuid.uuid4().hex[:8]}",
        "receipt_path": str(receipt_path.resolve()),
        "created_at": now_iso(),
        "trust_state": "pending",
        "stats": {
            "decisions_found": len(decisions),
            "corrections_found": len(corrections),
            "generated_files": len(files),
            "open_gaps": len(gaps),
            "suggestions": len(suggestions),
        },
        "analysis": {
            "missing_projects": missing_projects,
            "unknown_refs": unknown_refs,
            "likely_target_matches": len(unknown_refs) == 0,
            "high_impact_changes": high_impact,
            "possible_prompt_injection": possible_prompt_injection
        }
    }
    return report

def review_receipt(root: Path, receipt_path: Path) -> str:
    ensure_root(root)
    rev_dir = ensure_review_dir(root)
    report = _generate_review_report(root, receipt_path)
    
    rid = report["review_id"]
    write_json(rev_dir / f"{rid}.json", report)
    
    md = [
        f"# Receipt Review: {rid}",
        f"**Source:** {receipt_path.name}",
        f"**Created:** {report['created_at']}",
        f"**Status:** {report['trust_state']}",
        "",
        "## Statistics",
        f"- Decisions: {report['stats']['decisions_found']}",
        f"- Corrections: {report['stats']['corrections_found']}",
        f"- Generated Files: {report['stats']['generated_files']}",
        f"- Open Gaps: {report['stats']['open_gaps']}",
        f"- Suggestions: {report['stats']['suggestions']}",
        "",
        "## Analysis",
    ]
    
    if report["analysis"]["possible_prompt_injection"]:
        md.append("### ⚠️ Security Warnings")
        for w in report["analysis"]["possible_prompt_injection"]:
            md.append(f"- {w}")
            
    if report["analysis"]["high_impact_changes"]:
        md.append("### ⚠️ High Impact Changes")
        for w in report["analysis"]["high_impact_changes"]:
            md.append(f"- {w}")
            
    if report["analysis"]["missing_projects"]:
        md.append("### Missing Projects")
        for m in report["analysis"]["missing_projects"]:
            md.append(f"- {m}")
            
    if report["analysis"]["unknown_refs"]:
        md.append("### Unknown References")
        for u in report["analysis"]["unknown_refs"]:
            md.append(f"- {u}")
            
    md_path = rev_dir / f"{rid}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    
    return rid

def validate_receipt(root: Path, receipt_path: Path):
    ensure_root(root)
    print(f"Validating {receipt_path.name}...")
    report = _generate_review_report(root, receipt_path)
    print("Stats:")
    for k, v in report["stats"].items():
        print(f"  {k}: {v}")
    
    warns = report["analysis"]["possible_prompt_injection"] + report["analysis"]["high_impact_changes"]
    if warns:
        print("Warnings:")
        for w in warns:
            print(f"  ! {w}")
    else:
        print("No critical warnings.")
        
def receipt_diff(root: Path, receipt_path: Path):
    ensure_root(root)
    from llm_kosh.engine.healing import absorb_receipt
    print(f"Diff for {receipt_path.name}:")
    absorb_receipt(root, receipt_path, dry_run=True)

def trust_receipt(root: Path, review_id: str, state: str):
    ensure_root(root)
    rev_dir = ensure_review_dir(root)
    jpath = rev_dir / f"{review_id}.json"
    if not jpath.exists():
        raise FileNotFoundError(f"Review {review_id} not found.")
        
    report = read_json(jpath)
    report["trust_state"] = state
    write_json(jpath, report)
    
    mdpath = rev_dir / f"{review_id}.md"
    if mdpath.exists():
        text = mdpath.read_text(encoding="utf-8")
        text = re.sub(r"\*\*Status:\*\* .*", f"**Status:** {state}", text)
        mdpath.write_text(text, encoding="utf-8")
        
    print(f"Review {review_id} updated to '{state}'.")

def list_receipts(root: Path):
    ensure_root(root)
    rev_dir = ensure_review_dir(root)
    count = 0
    for jpath in rev_dir.glob("*.json"):
        report = read_json(jpath)
        print(f"[{report['trust_state'].upper()}] {report['review_id']} - {Path(report['receipt_path']).name}")
        count += 1
    if count == 0:
        print("No receipt reviews found.")
        
def show_receipt(root: Path, review_id: str):
    ensure_root(root)
    mdpath = ensure_review_dir(root) / f"{review_id}.md"
    if mdpath.exists():
        print(mdpath.read_text(encoding="utf-8"))
    else:
        print(f"Review {review_id} not found.")
