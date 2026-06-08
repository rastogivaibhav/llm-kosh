import importlib
import importlib.util
import os
import sys
import uuid
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

@dataclass
class ProposalRecord:
    proposal_id: str
    source_intake_id: Optional[str]
    source_type: str
    source_path: str
    processor: str
    action: str  # create, supersede, update_metadata, classify, quarantine, link, ignore
    
    proposed_kind: str = "note"
    title: str = ""
    body: str = ""
    project: str = ""
    visibility: str = "private"
    target_ids: List[str] = field(default_factory=list)
    supersedes: str = ""
    
    confidence: float = 1.0
    requires_review: bool = False
    evidence: str = ""
    safety: Dict[str, Any] = field(default_factory=dict)
    apply_plan: Dict[str, Any] = field(default_factory=dict)
    review_state: str = "pending"

    def to_dict(self):
        return {
            "proposal_id": self.proposal_id,
            "source_intake_id": self.source_intake_id,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "processor": self.processor,
            "action": self.action,
            "proposed_kind": self.proposed_kind,
            "title": self.title,
            "body": self.body,
            "project": self.project,
            "visibility": self.visibility,
            "target_ids": self.target_ids,
            "supersedes": self.supersedes,
            "confidence": self.confidence,
            "requires_review": self.requires_review,
            "evidence": self.evidence,
            "safety": self.safety,
            "apply_plan": self.apply_plan,
            "review_state": self.review_state
        }

@dataclass
class ProposalBatch:
    batch_id: str
    intake_id: Optional[str]
    processor: str
    proposals: List[ProposalRecord] = field(default_factory=list)

    def to_dict(self):
        return {
            "schema": "llm_kosh.proposal_batch.v1",
            "batch_id": self.batch_id,
            "intake_id": self.intake_id,
            "processor": self.processor,
            "proposals": [p.to_dict() for p in self.proposals]
        }

from llm_kosh.core.utils import write_json, read_json

class ProcessorBase:
    name: str = "base_processor"
    description: str = "Base processor"
    
    def inspect(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> bool:
        """Return True if this processor can process the item"""
        return False
        
    def generate_proposal(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> ProposalBatch:
        """Generate a memory proposal batch"""
        intake_id = intake_record_or_file.get("intake_id") if isinstance(intake_record_or_file, dict) else None
        source_type = intake_record_or_file.get("source_type", "file") if isinstance(intake_record_or_file, dict) else "file"
        
        rec = ProposalRecord(
            proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
            source_intake_id=intake_id,
            source_type=source_type,
            source_path=str(file_path),
            processor=self.name,
            action="ignore",
            proposed_kind="note",
            title=file_path.stem,
            body="",
            project="",
            visibility="private"
        )
        
        return ProposalBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:12]}",
            intake_id=intake_id,
            processor=self.name,
            proposals=[rec]
        )

def _load_processors_from_dir(d: Path) -> List[ProcessorBase]:
    processors = []
    if not d.exists():
        return processors
    for p in d.glob("*.py"):
        if p.name == "__init__.py":
            continue
        mod_name = p.stem
        spec = importlib.util.spec_from_file_location(mod_name, str(p))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "Processor"):
                processors.append(mod.Processor())
    return processors

def get_builtin_processors() -> List[ProcessorBase]:
    base_dir = Path(__file__).parent / "builtin"
    return _load_processors_from_dir(base_dir)

def get_user_processors(root: Path) -> List[ProcessorBase]:
    user_dir = root / "processors" / "user"
    return _load_processors_from_dir(user_dir)

def get_all_processors(root: Path) -> List[ProcessorBase]:
    return get_builtin_processors() + get_user_processors(root)

def get_processor_by_name(root: Path, name: str) -> Optional[ProcessorBase]:
    for p in get_all_processors(root):
        if p.name == name:
            return p
    return None

def write_proposal(root: Path, batch: ProposalBatch) -> Path:
    dest = root / "intake" / "proposals" / f"{batch.batch_id}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, batch.to_dict())
    return dest
