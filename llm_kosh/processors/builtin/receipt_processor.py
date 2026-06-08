import uuid
from typing import Dict, Any
from pathlib import Path
from llm_kosh.processors.core import ProcessorBase, ProposalRecord, ProposalBatch
from llm_kosh.engine.healing import parse_receipt

class Processor(ProcessorBase):
    name = "receipt_processor"
    description = "Parses MEMORY_RECEIPT.md files into proposals"

    def inspect(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> bool:
        if file_path.name.endswith(".md") and "receipt" in file_path.name.lower():
            return True
        return False

    def generate_proposal(self, intake_record_or_file: Dict[str, Any], file_path: Path) -> ProposalBatch:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_receipt(content)
        
        intake_id = intake_record_or_file.get("intake_id") if isinstance(intake_record_or_file, dict) else None
        source_type = intake_record_or_file.get("source_type", "file") if isinstance(intake_record_or_file, dict) else "file"
        
        proposals = []
        for it in parsed.get("decision", []):
            proposals.append(ProposalRecord(
                proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                source_intake_id=intake_id, source_type=source_type, source_path=str(file_path),
                processor=self.name, action="create", proposed_kind="decision",
                title=it["title"], body=it["body"], project=it.get("project", "")
            ))
            
        for it in parsed.get("correction", []):
            proposals.append(ProposalRecord(
                proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                source_intake_id=intake_id, source_type=source_type, source_path=str(file_path),
                processor=self.name, action="supersede", proposed_kind="correction",
                title=it["title"], body=it["body"], project=it.get("project", ""), supersedes=it.get("ref", "")
            ))
            
        for it in parsed.get("file", []):
            proposals.append(ProposalRecord(
                proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                source_intake_id=intake_id, source_type=source_type, source_path=str(file_path),
                processor=self.name, action="create", proposed_kind="file",
                title=it["title"], body=it["body"], project=it.get("project", "")
            ))

        for it in parsed.get("gap", []):
            proposals.append(ProposalRecord(
                proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                source_intake_id=intake_id, source_type=source_type, source_path=str(file_path),
                processor=self.name, action="create", proposed_kind="gap",
                title=it["title"], body=it["body"], project=it.get("project", "")
            ))

        for it in parsed.get("suggestion", []):
            proposals.append(ProposalRecord(
                proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
                source_intake_id=intake_id, source_type=source_type, source_path=str(file_path),
                processor=self.name, action="create", proposed_kind="suggestion",
                title=it["title"], body=it["body"], project=it.get("project", "")
            ))

        return ProposalBatch(
            batch_id=f"batch_{uuid.uuid4().hex[:12]}",
            intake_id=intake_id,
            processor=self.name,
            proposals=proposals
        )