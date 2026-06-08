import json
from pathlib import Path
from typing import Dict, Set

class ReceiptDAG:
    def __init__(self, root: Path):
        self.root = root
        self.superseded_by: Dict[str, str] = {}  # maps old_id -> new_id
        self.supersedes: Dict[str, Set[str]] = {}  # maps new_id -> set of old_ids
        self.quarantined: Set[str] = set()
        self.rebuild()

    def rebuild(self):
        self.superseded_by.clear()
        self.supersedes.clear()
        self.quarantined.clear()

        events_file = self.root / "ledger" / "events.jsonl"
        if not events_file.exists():
            return

        with events_file.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    evt = json.loads(line)
                    event_type = evt.get("event")
                    if event_type == "memory.superseded":
                        old_id = evt.get("old_id")
                        new_id = evt.get("new_id")
                        if old_id and new_id:
                            self.superseded_by[old_id] = new_id
                            if new_id not in self.supersedes:
                                self.supersedes[new_id] = set()
                            self.supersedes[new_id].add(old_id)
                    elif event_type == "intake.quarantined":
                        intake_id = evt.get("intake_id")
                        if intake_id:
                            self.quarantined.add(intake_id)
                except Exception:
                    pass

    def is_superseded(self, memory_id: str) -> bool:
        return memory_id in self.superseded_by

    def get_boolean_admissibility(self, memory_id: str, status_from_meta: str = "") -> float:
        if status_from_meta == "superseded":
            return 0.0
        if self.is_superseded(memory_id):
            return 0.0
        return 1.0
