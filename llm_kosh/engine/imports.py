import json
import shutil
import hashlib
from pathlib import Path
from typing import List, Dict, Any

from llm_kosh.core.utils import read_json, write_json, now_iso
from llm_kosh.core.memory import ensure_root, add_memory, find_doc_by_id, update_doc_meta
import uuid

def _new_id():
    return uuid.uuid4().hex[:8]

def _compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
    else:
        for p in sorted(path.rglob("*")):
            if p.is_file():
                h.update(p.read_bytes())
    return h.hexdigest()

def _load_transactions(root: Path) -> dict:
    f = root / "reports" / "imports.json"
    return read_json(f, {})

def _save_transactions(root: Path, txs: dict):
    f = root / "reports" / "imports.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    write_json(f, txs)

def import_detect(path: Path) -> str:
    if not path.exists():
        return "unknown"
    
    # Simple heuristic
    if path.is_file() and path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if "title" in first and "mapping" in first:
                    return "chatgpt"
                if "uuid" in first and "chat_messages" in first:
                    return "claude"
        except:
            pass
    # Maybe gemini? (We'll assume generic if it fails detection)
    return "generic"

def _parse_chatgpt(path: Path) -> List[Dict]:
    convos = []
    data = json.loads(path.read_text(encoding="utf-8"))
    for item in data:
        c = {
            "provider": "chatgpt",
            "conversation_id": item.get("id", _new_id()),
            "title": item.get("title", "ChatGPT Conversation"),
            "created_at": str(item.get("create_time", "")),
            "messages": [],
            "source_hash": ""
        }
        mapping = item.get("mapping", {})
        for node in mapping.values():
            msg = node.get("message")
            if msg and msg.get("author", {}).get("role"):
                text = ""
                parts = msg.get("content", {}).get("parts", [])
                for p in parts:
                    if isinstance(p, str): text += p
                if text:
                    c["messages"].append({
                        "role": msg["author"]["role"],
                        "text": text,
                        "time": str(msg.get("create_time", ""))
                    })
        convos.append(c)
    return convos

def _parse_generic(path: Path) -> List[Dict]:
    return [{
        "provider": "generic",
        "conversation_id": _new_id(),
        "title": path.name,
        "created_at": now_iso(),
        "messages": [{"role": "system", "text": path.read_text(encoding="utf-8", errors="replace"), "time": now_iso()}],
        "source_hash": ""
    }]

def _parse_conversations(provider: str, path: Path) -> List[Dict]:
    if provider == "chatgpt":
        return _parse_chatgpt(path)
    return _parse_generic(path)

def import_preview(root: Path, path: Path) -> dict:
    ensure_root(root)
    provider = import_detect(path)
    if provider == "unknown":
        return {"status": "error", "message": "Unknown or missing file"}
        
    convos = []
    if path.is_dir():
        for p in path.rglob("*"):
            if p.is_file():
                try: convos.extend(_parse_conversations(import_detect(p), p))
                except: pass
    else:
        convos = _parse_conversations(provider, path)
        
    msg_count = sum(len(c["messages"]) for c in convos)
    return {
        "status": "ok",
        "provider": provider,
        "conversations_found": len(convos),
        "messages_found": msg_count,
        "source_hash": _compute_hash(path)
    }

def import_apply(root: Path, path: Path) -> dict:
    ensure_root(root)
    preview = import_preview(root, path)
    if preview["status"] != "ok":
        return preview
        
    txs = _load_transactions(root)
    shash = preview["source_hash"]
    
    # Deduplication
    for iid, tx in txs.items():
        if tx.get("source_hash") == shash and tx.get("status") == "applied":
            return {"status": "skipped", "message": "Duplicate source_hash already imported", "import_id": iid}
            
    import_id = f"import_{_new_id()}"
    
    # Archive raw
    archive_dir = root / "attachments" / "imports" / import_id
    archive_dir.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        shutil.copy2(path, archive_dir / path.name)
    else:
        shutil.copytree(path, archive_dir / path.name)
        
    # Create records
    convos = []
    if path.is_file():
        convos = _parse_conversations(preview["provider"], path)
    else:
        for p in path.rglob("*"):
            if p.is_file():
                try: convos.extend(_parse_conversations(import_detect(p), p))
                except: pass
                
    record_ids = []
    for c in convos:
        c["source_hash"] = shash
        body = json.dumps(c, indent=2)
        sfile = root / "attachments" / "imports" / import_id / path.name
        # Add a dummy file at sfile to prevent add_memory from throwing FileNotFoundError
        sfile.parent.mkdir(parents=True, exist_ok=True)
        if not sfile.exists():
            sfile.touch()
        rid_path = add_memory(root, kind="conversation", title=c["title"], body=body, project="", visibility="private", source_file=sfile)
        record_ids.append(str(rid_path.relative_to(root).as_posix()))
        
    txs[import_id] = {
        "import_id": import_id,
        "source_hash": shash,
        "source_path": str(path),
        "provider": preview["provider"],
        "status": "applied",
        "timestamp": now_iso(),
        "record_ids": record_ids,
        "stats": {
            "conversations": len(convos),
            "messages": preview["messages_found"]
        }
    }
    _save_transactions(root, txs)
    
    return txs[import_id]

def import_rollback(root: Path, import_id: str) -> dict:
    ensure_root(root)
    txs = _load_transactions(root)
    if import_id not in txs:
        return {"status": "error", "message": "Import ID not found"}
        
    tx = txs[import_id]
    if tx["status"] == "rolled_back":
        return {"status": "skipped", "message": "Already rolled back"}
        
    rolled = 0
    for rel_path in tx.get("record_ids", []):
        try:
            update_doc_meta(root, rel_path, {"status": "superseded"})
            rolled += 1
        except Exception:
            pass
            
    tx["status"] = "rolled_back"
    tx["rollback_time"] = now_iso()
    _save_transactions(root, txs)
    
    return {"status": "ok", "message": f"Rolled back {rolled} records"}

def import_list(root: Path) -> dict:
    return _load_transactions(root)

def import_show(root: Path, import_id: str) -> dict:
    return _load_transactions(root).get(import_id, {})

def import_report(root: Path, import_id: str) -> str:
    tx = import_show(root, import_id)
    if not tx: return "Not found"
    
    lines = [f"# Import Report: {import_id}", f"- Status: {tx.get('status')}"]
    lines.append(f"- Provider: {tx.get('provider')}")
    lines.append(f"- Source: {tx.get('source_path')}")
    stats = tx.get("stats", {})
    lines.append(f"- Conversations: {stats.get('conversations')}")
    lines.append(f"- Messages: {stats.get('messages')}")
    lines.append(f"- Records created: {len(tx.get('record_ids', []))}")
    return "\n".join(lines)
