import uuid
import json
from typing import Dict, Any
from pathlib import Path
from koush.processors.core import ProcessorBase, ProposalRecord, ProposalBatch

class Processor(ProcessorBase):
    name = "conversation_processor"
    description = "Parses conversation logs (JSON) into memory proposals"

    def inspect(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> bool:
        if file_path.suffix == ".json" and "conversation" in file_path.name.lower():
            return True
        return False

    def generate_proposal(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> ProposalBatch:
        try:
            content = json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
            title = content.get("title", file_path.stem)
            body = json.dumps(content, indent=2)
        except Exception:
            title = file_path.stem
            body = "Failed to parse conversation json."
            
        intake_id = intake_record_or_file.get("intake_id") if isinstance(intake_record_or_file, dict) else None
        source_type = intake_record_or_file.get("source_type", "file") if isinstance(intake_record_or_file, dict) else "file"
        
        rec = ProposalRecord(
            proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
            source_intake_id=intake_id,
            source_type=source_type,
            source_path=str(file_path),
            processor=self.name,
            action="create",
            proposed_kind="note",
            title=title,
            body=body,
            project="conversations"
        )
        return ProposalBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:12]}",
            intake_id=intake_id,
            processor=self.name,
            proposals=[rec]
        )