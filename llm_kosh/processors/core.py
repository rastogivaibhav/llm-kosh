import importlib
import importlib.util
import uuid
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict, dataclass, field

from llm_kosh.core.utils import write_json

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
        return asdict(self)

@dataclass
class ProposalBatch:
    batch_id: str
    intake_id: Optional[str]
    processor: str
    proposals: List[ProposalRecord] = field(default_factory=list)

    def to_dict(self):
        return {"schema": "llm_kosh.proposal_batch.v1", **asdict(self)}

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


class FilenameProcessor(ProcessorBase):
    """Declarative processor for the built-in filename conventions."""

    def __init__(self, name: str, description: str, *, keyword: str = "", suffix: str = ".md",
                 kind: str = "note", project: str = "", title_prefix: str = "",
                 source_type: str = "", content_format: str = "text") -> None:
        self.name = name
        self.description = description
        self.keyword = keyword
        self.suffix = suffix
        self.kind = kind
        self.project = project
        self.title_prefix = title_prefix
        self.source_type = source_type
        self.content_format = content_format

    def inspect(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> bool:
        if self.source_type:
            return (intake_record_or_file.get("source_type") == self.source_type
                    if isinstance(intake_record_or_file, dict) else True)
        return file_path.suffix.lower() == self.suffix and self.keyword in file_path.name.lower()

    def generate_proposal(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> ProposalBatch:
        intake = intake_record_or_file if isinstance(intake_record_or_file, dict) else {}
        intake_id = intake.get("intake_id")
        source_type = intake.get("source_type", "file")
        content = file_path.read_text(encoding="utf-8", errors="replace")

        if self.content_format == "receipt":
            from llm_kosh.engine.healing import parse_receipt
            proposals = []
            parsed = parse_receipt(content)
            for section, action in (
                ("decision", "create"), ("correction", "supersede"), ("file", "create"),
                ("gap", "create"), ("suggestion", "create"),
            ):
                for item in parsed.get(section, []):
                    proposals.append(ProposalRecord(
                        proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                        source_intake_id=intake_id,
                        source_type=source_type,
                        source_path=str(file_path),
                        processor=self.name,
                        action=action,
                        proposed_kind=section,
                        title=item["title"],
                        body=item["body"],
                        project=item.get("project", ""),
                        supersedes=item.get("ref", "") if section == "correction" else "",
                    ))
        else:
            title = f"{self.title_prefix}{file_path.stem}"
            body = content
            if self.content_format == "json":
                try:
                    parsed = json.loads(content)
                    title = parsed.get("title", file_path.stem)
                    body = json.dumps(parsed, indent=2)
                except Exception:
                    title, body = file_path.stem, "Failed to parse conversation json."
            proposals = [ProposalRecord(
                proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                source_intake_id=intake_id,
                source_type=source_type,
                source_path=str(file_path),
                processor=self.name,
                action="create",
                proposed_kind=self.kind,
                title=title,
                body=body,
                project=self.project,
            )]

        return ProposalBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:12]}",
            intake_id=intake_id,
            processor=self.name,
            proposals=proposals,
        )


BUILTIN_PROCESSOR_RULES = (
    dict(name="conversation_processor", description="Parses conversation logs (JSON) into memory proposals",
         keyword="conversation", suffix=".json", project="conversations", content_format="json"),
    dict(name="decision_processor", description="Extracts decision memories from intake items",
         keyword="decision", kind="decision"),
    dict(name="gap_processor", description="Extracts open knowledge gaps from intake items",
         keyword="gap", kind="gap"),
    dict(name="generated_file_processor", description="Fallback processor for generic text files",
         source_type="generic_file"),
    dict(name="handover_processor", description="Parses agent handover documents into project context",
         keyword="handover", project="handovers", title_prefix="Handover: "),
    dict(name="project_processor", description="Extracts project memories from intake items",
         keyword="project", kind="project"),
    dict(name="prompt_processor", description="Extracts prompt memories from intake items",
         keyword="prompt", kind="prompt"),
    dict(name="receipt_processor", description="Parses MEMORY_RECEIPT.md files into proposals",
         keyword="receipt", content_format="receipt"),
    dict(name="safety_processor", description="Detects safety issues or security policies in intake items",
         keyword="safety", kind="decision", project="security", title_prefix="Safety Policy: "),
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
    return [FilenameProcessor(**rule) for rule in BUILTIN_PROCESSOR_RULES]

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
