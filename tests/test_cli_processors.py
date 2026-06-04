import pytest
from pathlib import Path
from llm_kosh.core.memory import init_cartridge
from llm_kosh.processors.core import get_builtin_processors, get_all_processors

@pytest.fixture
def processor_workspace(temp_workspace):
    root = Path(temp_workspace)
    init_cartridge(root, "tester")
    return root

def test_processor_list(processor_workspace):
    processors = get_all_processors(processor_workspace)
    assert len(processors) >= 6
    names = [p.name for p in processors]
    assert "decision_processor" in names
    assert "receipt_processor" in names

def test_processor_suggest(processor_workspace):
    from llm_kosh.engine.intake import intake_scan
    
    root = processor_workspace
    test_file = root / "inbox" / "decision-xyz.md"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("decision body", encoding="utf-8")
    
    records = intake_scan(root)
    assert len(records) == 1
    record = records[0]
    
    from llm_kosh.processors.core import get_processor_by_name, write_proposal
    p = get_processor_by_name(root, "decision_processor")
    assert p is not None
    
    if p.inspect(record, test_file):
        batch = p.generate_proposal(record, test_file)
        assert len(batch.proposals) == 1
        assert batch.proposals[0].proposed_kind == "decision"
        assert batch.proposals[0].title == "decision-xyz"
        assert batch.proposals[0].body == "decision body"
        
        path = write_proposal(root, batch)
        assert path.exists()

def test_processor_apply(processor_workspace):
    from llm_kosh.processors.core import ProposalRecord, ProposalBatch, write_proposal
    from llm_kosh.engine.intake import processor_apply
    from llm_kosh.core.utils import read_json
    
    root = processor_workspace
    rec = ProposalRecord(
        proposal_id="prop_test_123",
        source_intake_id="intake_test",
        source_type="file",
        source_path="none",
        processor="test_proc",
        action="create",
        proposed_kind="note",
        title="Test Title",
        body="Test Body"
    )
    batch = ProposalBatch(
        batch_id="batch_test_123",
        intake_id="intake_test",
        processor="test_proc",
        proposals=[rec]
    )
    
    write_proposal(root, batch)
    res = processor_apply(root, "batch_test_123")
    
    assert res["added"] == 1
    
    # Verify memory
    db_path = root / "indexes" / "memory.sqlite"
    assert db_path.exists()
