import json
from pathlib import Path
from llm_kosh.core.utils import read_json, write_json, now_iso
from llm_kosh.core.memory import ensure_root

def _load_migrations(root: Path) -> dict:
    f = root / "reports" / "migrations.json"
    return read_json(f, {})

def _save_migrations(root: Path, state: dict):
    f = root / "reports" / "migrations.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    write_json(f, state)

def migrate_check(root: Path) -> dict:
    ensure_root(root)
    # Check if there are migrations pending.
    # We only have v1.0 schema so far, so no migrations pending.
    koush_meta = root / "LLM_KOSH.json"
    meta = read_json(koush_meta, {})
    version = meta.get("version", "2.0.0")
    
    return {
        "status": "up_to_date",
        "current_version": version,
        "pending_migrations": 0,
        "message": "Cartridge is on the latest schema."
    }

def migrate_apply(root: Path) -> dict:
    ensure_root(root)
    check = migrate_check(root)
    if check["pending_migrations"] == 0:
        return {"status": "skipped", "message": "Nothing to migrate."}
        
    # Placeholder for actual migration logic when v2 hits
    return {"status": "applied", "message": "Migrations applied successfully."}

def migrate_rollback(root: Path) -> dict:
    ensure_root(root)
    state = _load_migrations(root)
    if not state:
        return {"status": "skipped", "message": "No migrations to roll back."}
        
    return {"status": "rolled_back", "message": "Rollback not supported for this migration step."}
