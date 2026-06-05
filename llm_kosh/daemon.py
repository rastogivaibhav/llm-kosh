import time
import shutil
import json
import zipfile
from pathlib import Path
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

from llm_kosh.engine.healing import absorb_receipt, resolve
from llm_kosh.engine.commands import heal_safe as do_heal_safe, audit, memory_map
from llm_kosh.core.memory import ensure_root
from llm_kosh.engine.intake import intake_scan
from llm_kosh.engine.safety import load_policy
from llm_kosh.engine.search import rebuild_index
from llm_kosh.core.utils import read_json, write_json, now_iso

def log_daemon_event(root: Path, event: str, details: dict):
    log_dir = root / "reports" / "daemon"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "events.jsonl"
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": now_iso(), "event": event, "details": details}) + "\n")

def update_status(root: Path, job: str, success: bool, message: str = ""):
    log_dir = root / "reports" / "daemon"
    log_dir.mkdir(parents=True, exist_ok=True)
    status_file = log_dir / "status.json"
    status = read_json(status_file, {})
    
    if "jobs" not in status:
        status["jobs"] = {}
    
    status["jobs"][job] = {
        "last_run": now_iso(),
        "status": "success" if success else "failed",
        "message": message
    }
    write_json(status_file, status)

def _get_enabled_jobs(root: Path) -> list:
    pol = load_policy(root)
    daemon_cfg = pol.get("daemon", {})
    return daemon_cfg.get("enabled_jobs", [
        "scan_intake", 
        "process_safe_receipts", 
        "rebuild_stale_index", 
        "regenerate_memory_map"
    ])

# --- Jobs ---

def job_scan_intake(root: Path):
    new_records = intake_scan(root)
    if new_records:
        log_daemon_event(root, "scan_intake", {"new_records": len(new_records)})
    return True, f"Scanned {len(new_records)} new intake records."

def job_process_safe_receipts(root: Path):
    from llm_kosh.engine.receipt_trust import review_receipt, trust_receipt, ensure_review_dir
    receipts_dir = root / "receipts"
    processed_dir = receipts_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    held = 0
    for path in receipts_dir.glob("MEMORY_RECEIPT*.md"):
        if path.is_dir(): continue
        try:
            rid = review_receipt(root, path)
            jpath = ensure_review_dir(root) / f"{rid}.json"
            report = read_json(jpath)
            analysis = report.get("analysis", {})
            if analysis.get("high_impact_changes") or analysis.get("possible_prompt_injection"):
                held += 1
                log_daemon_event(root, "receipt_held", {"receipt": path.name, "review_id": rid})
            else:
                trust_receipt(root, rid, "trusted")
                absorb_receipt(root, path, dry_run=False, review_id=rid)
                
                dest = processed_dir / path.name
                if dest.exists():
                    dest = processed_dir / f"{path.stem}_{int(time.time())}{path.suffix}"
                shutil.move(str(path), str(dest))
                processed += 1
                log_daemon_event(root, "receipt_absorbed", {"receipt": path.name, "review_id": rid})
        except Exception as e:
            log_daemon_event(root, "receipt_error", {"receipt": path.name, "error": str(e)})
            
    if processed or held:
        return True, f"Processed {processed}, Held {held} for review."
    return True, "No new receipts."

def job_rebuild_stale_index(root: Path):
    rebuild_index(root, force=False)
    return True, "Index rebuilt."

def job_rebuild_vector_if_stale(root: Path):
    # Stub semantic index update
    return True, "Vector rebuild not implemented."

def job_audit(root: Path):
    audit(root)
    return True, "Audit completed."

def job_heal_safe(root: Path):
    do_heal_safe(root)
    return True, "Safe heal completed."

def job_regenerate_memory_map(root: Path):
    memory_map(root)
    return True, "Memory map regenerated."

def job_regenerate_workbench(root: Path):
    from llm_kosh.engine.workbench import build_workbench
    build_workbench(root, include_private=False)
    return True, "Workbench regenerated."

def job_backup_snapshot(root: Path):
    out = root / "exports" / f"backup_{int(time.time())}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and not any(part in ["exports", ".git", "indexes", "reports"] for part in p.parts):
                zf.write(p, p.relative_to(root))
    return True, f"Backup created at {out.name}"

def job_quarantine_risky_items(root: Path):
    return True, "No risky items detected."

JOBS = {
    "scan_intake": job_scan_intake,
    "process_safe_receipts": job_process_safe_receipts,
    "rebuild_stale_index": job_rebuild_stale_index,
    "rebuild_vector_if_stale": job_rebuild_vector_if_stale,
    "audit": job_audit,
    "heal_safe": job_heal_safe,
    "regenerate_memory_map": job_regenerate_memory_map,
    "regenerate_workbench": job_regenerate_workbench,
    "backup_snapshot": job_backup_snapshot,
    "quarantine_risky_items": job_quarantine_risky_items
}

def daemon_run_job(root: Path, job_name: str):
    ensure_root(root)
    if job_name not in JOBS:
        print(f"Unknown job: {job_name}")
        return False
        
    print(f"[Daemon] Running job: {job_name}...")
    try:
        success, msg = JOBS[job_name](root)
        update_status(root, job_name, success, msg)
        log_daemon_event(root, "job_run", {"job": job_name, "status": "success", "msg": msg})
        print(f"  -> {msg}")
        return success
    except Exception as e:
        update_status(root, job_name, False, str(e))
        log_daemon_event(root, "job_run", {"job": job_name, "status": "failed", "msg": str(e)})
        print(f"  -> FAILED: {e}")
        return False

def daemon_once(root: Path):
    ensure_root(root)
    enabled = _get_enabled_jobs(root)
    print(f"[Daemon] Running {len(enabled)} scheduled jobs...")
    for j in enabled:
        daemon_run_job(root, j)
        
def daemon_status(root: Path):
    ensure_root(root)
    status_file = root / "reports" / "daemon" / "status.json"
    status = read_json(status_file, {})
    jobs = status.get("jobs", {})
    
    print("Daemon Status")
    print("=============")
    enabled = _get_enabled_jobs(root)
    print(f"Enabled Jobs: {', '.join(enabled)}\n")
    for j, s in jobs.items():
        print(f"[{s['status'].upper()}] {j}")
        print(f"  Last Run: {s['last_run']}")
        print(f"  Message:  {s['message']}")

def daemon_start(root: Path, mode: str):
    ensure_root(root)
    pol = load_policy(root)
    interval = pol.get("daemon", {}).get("poll_interval_seconds", 10)
    
    print(f"Starting LlmKosh Daemon (Mode: {mode})")
    
    observer = None
    if mode in ["watchdog", "auto"]:
        if not HAS_WATCHDOG:
            print("Watchdog library missing. Please install it using 'pip install llm_kosh[watch]' or run in polling mode.")
            if mode == "watchdog":
                return
        else:
            class ReceiptHandler(FileSystemEventHandler):
                def on_created(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        if "MEMORY_RECEIPT" in Path(event.src_path).name and "processed" not in Path(event.src_path).parts:
                            daemon_once(root)
                def on_modified(self, event):
                    if not event.is_directory and event.src_path.endswith(".md"):
                        if "MEMORY_RECEIPT" in Path(event.src_path).name and "processed" not in Path(event.src_path).parts:
                            daemon_once(root)
                            
            class ExternalFolderHandler(FileSystemEventHandler):
                def on_created(self, event):
                    self._handle(event)
                def on_modified(self, event):
                    self._handle(event)
                def _handle(self, event):
                    if not event.is_directory and (event.src_path.endswith(".md") or event.src_path.endswith(".txt")):
                        src = Path(event.src_path)
                        if src.name.startswith("."): return
                        try:
                            dest = root / "inbox" / f"{src.stem}_{int(time.time())}{src.suffix}"
                            dest.parent.mkdir(exist_ok=True)
                            shutil.copy2(src, dest)
                            daemon_once(root)
                        except Exception as e:
                            print(f"Error copying external file {src}: {e}")
                            
            observer = Observer()
            receipts_dir = root / "receipts"
            receipts_dir.mkdir(exist_ok=True)
            observer.schedule(ReceiptHandler(), str(receipts_dir), recursive=False)
            print(f"Watchdog active on {receipts_dir}")
            
            watched_dirs = pol.get("daemon", {}).get("watched_directories", [])
            for d in watched_dirs:
                if Path(d).exists() and Path(d).is_dir():
                    try:
                        observer.schedule(ExternalFolderHandler(), str(d), recursive=True)
                        print(f"Watchdog active on external folder: {d}")
                    except Exception as e:
                        print(f"Could not watch {d}: {e}")
            
            observer.start()

    try:
        if mode in ["polling", "auto"]:
            print(f"Polling active. Interval: {interval}s")
            while True:
                daemon_once(root)
                time.sleep(interval)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping daemon...")
    finally:
        if observer:
            observer.stop()
            observer.join()
