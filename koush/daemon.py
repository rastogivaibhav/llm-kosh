import time
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from koush.engine.healing import absorb_receipt, resolve
from koush.core.memory import ensure_root

class ReceiptHandler(FileSystemEventHandler):
    def __init__(self, root: Path):
        self.root = root
        self._processing = set()

    def process_file(self, path: Path):
        if not path.exists():
            return
        if path in self._processing:
            return
        
        # Guard against temporary files or system lockups
        self._processing.add(path)
        try:
            # We wait a moment in case the writer is still flushing the file
            time.sleep(0.5)
            
            # Read first line to verify it's not completely empty or locked
            try:
                content = path.read_text(encoding="utf-8", errors="replace").strip()
                if not content:
                    return  # Still writing or empty
            except Exception:
                return  # File might be temporarily locked
            
            print(f"\n[Daemon] Detected memory receipt: {path.name}")
            
            # Absorb receipt
            absorb_receipt(self.root, path, dry_run=False)
            
            # Auto-resolve corrections using local-first search
            resolve(self.root, auto=True, threshold=0.18, semantic=False)
            
            # Move to processed directory
            processed_dir = self.root / "receipts" / "processed"
            processed_dir.mkdir(exist_ok=True)
            dest = processed_dir / path.name
            if dest.exists():
                # Avoid name collisions in archive
                dest = processed_dir / f"{path.stem}_{int(time.time())}{path.suffix}"
            
            shutil.move(str(path), str(dest))
            print(f"[Daemon] Successfully absorbed and archived receipt: {path.name} -> receipts/processed/{dest.name}")
        except Exception as e:
            print(f"[Daemon] Failed to absorb receipt {path.name}: {e}")
        finally:
            self._processing.discard(path)

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".md" and "MEMORY_RECEIPT" in path.name:
            # Skip archiving subdirectory
            if "processed" in path.parts:
                return
            self.process_file(path)

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == ".md" and "MEMORY_RECEIPT" in path.name:
            if "processed" in path.parts:
                return
            self.process_file(path)

def watch_command(root: Path):
    ensure_root(root)
    receipts_dir = root / "receipts"
    receipts_dir.mkdir(exist_ok=True)
    processed_dir = receipts_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
    
    event_handler = ReceiptHandler(root)
    observer = Observer()
    observer.schedule(event_handler, str(receipts_dir), recursive=False)
    observer.start()
    print(f"Watching {receipts_dir} for MEMORY_RECEIPTs...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
