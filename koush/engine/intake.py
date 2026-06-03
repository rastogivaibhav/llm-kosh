import uuid
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from koush.core.utils import now_iso, sha256_file, write_json, read_json, append_ledger
from koush.core.memory import ensure_root
from koush.engine.healing import absorb_receipt, parse_receipt
from koush.engine.safety import load_policy

def ensure_intake_dirs(root: Path):
    for d in ["intake/pending", "intake/reviewed", "intake/applied", "intake/rejected", "intake/quarantined", "reports/intake"]:
        (root / d).mkdir(parents=True, exist_ok=True)

def _move_record(root: Path, intake_id: str, new_status: str):
    record, current_path = _find_record(root, intake_id)
    if not record:
        raise ValueError(f"Intake record {intake_id} not found.")
    record["status"] = new_status
    new_path = root / "intake" / new_status / current_path.name
    write_json(new_path, record)
    current_path.unlink()
    return record

def _find_record(root: Path, intake_id: str) -> tuple[Optional[dict], Optional[Path]]:
    for status in ["pending", "validated", "reviewed", "applied", "rejected", "quarantined"]:
        d = root / "intake" / status
        if not d.exists(): continue
        for p in d.glob("*.json"):
            record = read_json(p)
            if record.get("intake_id") == intake_id:
                return record, p
    return None, None

def intake_scan(root: Path) -> List[dict]:
    ensure_root(root)
    ensure_intake_dirs(root)
    new_records = []
    
    # Places to scan
    scan_targets = [
        (root / "receipts", "receipt"),
        (root / "source" / "receipts", "receipt"),
        (root / "inbox", "generic_file"),
        (root / "attachments" / "imports", "importer"),
    ]
    
    # Collect existing hashes to avoid duplicates
    existing_hashes = set()
    for status in ["pending", "validated", "reviewed", "applied", "rejected", "quarantined"]:
        d = root / "intake" / status
        if d.exists():
            for p in d.glob("*.json"):
                existing_hashes.add(read_json(p).get("raw_hash"))
                
    for search_dir, processor in scan_targets:
        if not search_dir.exists(): continue
        for p in search_dir.rglob("*"):
            if not p.is_file(): continue
            if "processed" in p.parts: continue
            
            # Special case for receipts check
            if processor == "receipt" and not p.name.endswith(".md"): continue
            
            hash_val = sha256_file(p)
            if hash_val in existing_hashes: continue
            
            intake_id = f"intake_{uuid.uuid4().hex[:12]}"
            record = {
                "schema": "koush.intake.v1",
                "intake_id": intake_id,
                "source_type": processor,
                "source_path": str(p.relative_to(root)),
                "raw_hash": hash_val,
                "received_at": now_iso(),
                "status": "pending",
                "trust_level": "untrusted",
                "project": "",
                "visibility": "private",
                "processor": processor,
                "summary": "",
                "ledger_event": ""
            }
            write_json(root / "intake" / "pending" / f"{intake_id}.json", record)
            append_ledger(root, "intake.scanned", {"intake_id": intake_id, "source_path": record["source_path"]})
            existing_hashes.add(hash_val)
            new_records.append(record)
    
    return new_records

def intake_list(root: Path) -> List[dict]:
    ensure_root(root)
    ensure_intake_dirs(root)
    records = []
    for status in ["pending", "validated", "reviewed", "applied", "rejected", "quarantined"]:
        d = root / "intake" / status
        if d.exists():
            for p in d.glob("*.json"):
                records.append(read_json(p))
    return sorted(records, key=lambda x: x.get("received_at", ""), reverse=True)

def intake_show(root: Path, intake_id: str) -> Optional[dict]:
    record, _ = _find_record(root, intake_id)
    return record

def intake_validate(root: Path, intake_id: str) -> bool:
    record, p = _find_record(root, intake_id)
    if not record: return False
    
    src = root / record["source_path"]
    if not src.exists():
        raise FileNotFoundError(f"Source file {src} not found.")
        
    if record["processor"] == "receipt":
        try:
            text = src.read_text(encoding="utf-8")
            parsed = parse_receipt(text)
            if any(len(v) > 0 for v in parsed.values()):
                _move_record(root, intake_id, "validated")
                return True
            else:
                return False
        except Exception:
            return False
    return True

def intake_review(root: Path, intake_id: str) -> Path:
    ensure_intake_dirs(root)
    record, _ = _find_record(root, intake_id)
    if not record:
        raise ValueError("Intake not found.")
    
    src = root / record["source_path"]
    report_path = root / "reports" / "intake" / f"REVIEW_{intake_id}.md"
    
    report = f"# Intake Review: {intake_id}\n\n"
    report += f"- Source: `{record['source_path']}`\n"
    report += f"- Processor: `{record['processor']}`\n\n"
    
    if record["processor"] == "receipt":
        try:
            parsed = parse_receipt(src.read_text(encoding="utf-8"))
            for k, v in parsed.items():
                if v:
                    report += f"## {k.title()}\n"
                    for item in v:
                        report += f"- {item['title']}\n"
            record = _move_record(root, intake_id, "reviewed")
        except Exception as e:
            report += f"**Error parsing receipt:** {e}"
            
    report_path.write_text(report, encoding="utf-8")
    append_ledger(root, "intake.reviewed", {"intake_id": intake_id, "report": str(report_path.relative_to(root))})
    return report_path

def intake_apply(root: Path, intake_id: str) -> dict:
    record, _ = _find_record(root, intake_id)
    if not record:
        raise ValueError("Intake not found")
        
    src = root / record["source_path"]
    if not src.exists():
        raise FileNotFoundError("Source file is missing.")
        
    res = {}
    if record["processor"] == "receipt":
        res = absorb_receipt(root, src, dry_run=False)
        # Avoid creating duplicate receipts in receipts/processed by tracking that it was applied.
    else:
        # Other types aren't fully mapped to CLI here unless requested
        res = {"status": f"skipped processor {record['processor']}"}
        
    _move_record(root, intake_id, "applied")
    append_ledger(root, "intake.applied", {"intake_id": intake_id, "source_path": record["source_path"]})
    return res

def intake_reject(root: Path, intake_id: str):
    _move_record(root, intake_id, "rejected")
    append_ledger(root, "intake.rejected", {"intake_id": intake_id})

def intake_quarantine(root: Path, intake_id: str):
    record = _move_record(root, intake_id, "quarantined")
    src = root / record["source_path"]
    if src.exists():
        dest = root / "quarantine" / f"{intake_id}_{src.name}"
        shutil.move(str(src), str(dest))
    append_ledger(root, "intake.quarantined", {"intake_id": intake_id})

def intake_status(root: Path) -> dict:
    ensure_intake_dirs(root)
    counts = {"pending": 0, "validated": 0, "reviewed": 0, "applied": 0, "rejected": 0, "quarantined": 0}
    for status in counts.keys():
        d = root / "intake" / status
        if d.exists():
            counts[status] = len(list(d.glob("*.json")))
    return counts

def processor_apply(root: Path, batch_id: str) -> dict:
    from koush.core.memory import add_memory
    from koush.core.utils import read_json, append_ledger
    from koush.engine.search import rebuild_index
    
    ensure_root(root)
    prop_path = root / "intake" / "proposals" / f"{batch_id}.json"
    if not prop_path.exists():
        raise ValueError(f"ProposalBatch {batch_id} not found.")
        
    batch = read_json(prop_path)
    added = 0
    superseded = 0
    
    for rec in batch.get("proposals", []):
        if rec.get("action") == "create":
            add_memory(
                root=root,
                kind=rec.get("proposed_kind", "note"),
                title=rec.get("title", "Untitled"),
                body=rec.get("body", ""),
                project=rec.get("project", ""),
                visibility=rec.get("visibility", "private"),
                extra_meta={"source_proposal": rec.get("proposal_id")},
                reindex=False,
                quiet=True
            )
            added += 1
        elif rec.get("action") == "supersede":
            add_memory(
                root=root,
                kind=rec.get("proposed_kind", "correction"),
                title=rec.get("title", "Untitled"),
                body=rec.get("body", ""),
                project=rec.get("project", ""),
                visibility=rec.get("visibility", "private"),
                extra_meta={"source_proposal": rec.get("proposal_id"), "supersedes": rec.get("supersedes", "")},
                reindex=False,
                quiet=True
            )
            superseded += 1
        
    rebuild_index(root, force=True)
    append_ledger(root, "processor.batch_applied", {"batch_id": batch_id})
    return {"added": added, "superseded": superseded}
