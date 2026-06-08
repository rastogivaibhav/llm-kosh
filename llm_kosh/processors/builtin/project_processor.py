import uuid
from typing import Dict, Any
from pathlib import Path
from llm_kosh.processors.core import ProcessorBase, ProposalRecord, ProposalBatch

class Processor(ProcessorBase):
    name = "project_processor"
    description = "Extracts project memories from intake items"

    def inspect(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> bool:
        if file_path.suffix == ".md" and "project" in file_path.name.lower():
            return True
        return False

    def generate_proposal(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> ProposalBatch:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        intake_id = intake_record_or_file.get("intake_id") if isinstance(intake_record_or_file, dict) else None
        source_type = intake_record_or_file.get("source_type", "file") if isinstance(intake_record_or_file, dict) else "file"
        
        rec = ProposalRecord(
            proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
            source_intake_id=intake_id,
            source_type=source_type,
            source_path=str(file_path),
            processor=self.name,
            action="create",
            proposed_kind="project",
            title=file_path.stem,
            body=content,
            project=""
        )
        return ProposalBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:12]}",
            intake_id=intake_id,
            processor=self.name,
            proposals=[rec]
        )