import shutil
import uuid
from pathlib import Path
from typing import Dict, Optional

from koush.core.constants import APP_VERSION, KINDS
from koush.core.utils import (
    now_iso, slugify, ensure_root, source_dir_for_kind, 
    sha256_file, frontmatter, parse_frontmatter, append_ledger, 
    write_json, read_json, atomic_write_text
)
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
        "schema": "koush.v0",
        "version": APP_VERSION,
        "koush_id": "cart_" + uuid.uuid4().hex[:12],
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
    write_json(root / "KOUSH.json", config)

    (root / "BOOT.md").write_text(boot_text(owner), encoding="utf-8")

    from koush.engine.search import rebuild_index
    append_ledger(root, "cartridge.initialized", {"root": str(root), "owner": owner})
    rebuild_index(root, force=True)
    print(f"Initialized Koush v{APP_VERSION} at: {root}")


def boot_text(owner: str = "") -> str:
    who = f"\nThis cartridge was created for: **{owner}**.\n" if owner else ""
    return f"""# Koush Boot Instructions

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
    atomic_write_text(path, content, encoding="utf-8")
    append_ledger(root, f"{kind}.created", {
        "id": item_id, "path": str(path.relative_to(root)), "hash": sha256_file(path),
        **({"source_receipt": meta["source_receipt"]} if meta.get("source_receipt") else {}),
    })
    from koush.engine.search import rebuild_index
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
    atomic_write_text(path, content, encoding="utf-8")
    return meta


def find_doc_by_id(root: Path, doc_id: str) -> Optional[str]:
    from koush.engine.search import iter_source_files
    for p in iter_source_files(root):
        meta, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        if meta.get("id") == doc_id:
            return str(p.relative_to(root))
    return None


def supersede(root: Path, old_id: str, new_id: str, reason: str = "") -> bool:
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


def read_doc(root: Path, rel_path: str) -> str:
    return (root / rel_path).read_text(encoding="utf-8", errors="replace")
