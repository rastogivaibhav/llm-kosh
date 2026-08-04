import json
import sqlite3
import struct
import zipfile

import pytest

from llm_kosh.company_brain.artifacts import (
    ReferenceChangedError,
    ReferenceError,
    inspect_artifact,
    path_from_locator,
)
from llm_kosh.company_brain.context import compile_context
from llm_kosh.company_brain.models import (
    ContextRequest,
    EvidenceInput,
    EvidenceReference,
    MemoryInput,
    Principal,
)
from llm_kosh.company_brain.retrieval import search_memories
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.core.profile import set_cartridge_mode


def _reference(store, path, *, artifact_type="plain_text", native_id="local-source"):
    return store.put_evidence(EvidenceInput(
        source_type="local_file",
        source_locator=str(path),
        source_native_id=native_id,
        storage_mode="reference",
        artifact_type=artifact_type,
        mime_type="text/plain",
    ))


def test_reference_mode_stores_no_source_copy_and_detects_change(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Original local evidence", encoding="utf-8")
    store = CompanyBrainStore(tmp_path / "cartridge")
    evidence_id = _reference(store, source)
    principal = Principal("reader")

    assert store.read_evidence(evidence_id, principal) == b"Original local evidence"
    assert not store.blob_dir.exists()
    health = store.health()
    assert health["references"] == 1
    assert health["reference_source_bytes"] == len(b"Original local evidence")
    assert health["copied_source_bytes"] == 0
    assert health["reference_copy_amplification"] == 0.0

    source.write_text("Changed local evidence", encoding="utf-8")
    inspection = store.inspect_evidence(evidence_id, principal, strong=True)
    assert inspection["availability"]["status"] == "changed"
    with pytest.raises(ReferenceChangedError):
        store.read_evidence(evidence_id, principal)


def test_context_can_cite_fresh_reference_evidence_before_memory_promotion(tmp_path):
    source = tmp_path / "release-plan.md"
    source.write_text(
        "Release plan: Windows signing must complete before public launch.",
        encoding="utf-8",
    )
    store = CompanyBrainStore(tmp_path / "cartridge")
    evidence_id = store.register_local_file(source)["evidence_id"]

    context = compile_context(store, ContextRequest(
        task="What is required before the public launch?",
        principal=Principal("reader"),
        token_budget=512,
    ))

    assert context["selected_items"] == 0
    assert context["selected_evidence"] == 1
    assert context["direct_evidence"][0]["evidence_id"] == evidence_id
    assert "Windows signing" in context["direct_evidence"][0]["quote"]
    assert context["artifact_attachments"][0]["storage_mode"] == "reference"
    assert not store.blob_dir.exists()


def test_same_directory_rename_is_reported_as_moved_not_trusted_implicitly(tmp_path):
    source = tmp_path / "before.txt"
    source.write_text("Stable evidence", encoding="utf-8")
    store = CompanyBrainStore(tmp_path / "cartridge")
    evidence_id = _reference(store, source)
    renamed = tmp_path / "after.txt"
    source.rename(renamed)
    inspection = store.inspect_evidence(evidence_id, Principal("reader"), strong=True)
    assert inspection["availability"]["status"] in {"moved", "unavailable"}
    # A discovered candidate must be explicitly re-registered before it can be read.
    with pytest.raises(ReferenceError):
        store.read_evidence(evidence_id, Principal("reader"))


def test_reference_resolver_rejects_network_and_non_file_schemes():
    with pytest.raises(ReferenceError, match="local files"):
        path_from_locator("https://example.com/report.html")
    with pytest.raises(ReferenceError, match="UNC"):
        path_from_locator(r"\\server\share\report.xlsx")


def test_snapshot_is_explicit_and_content_addressed(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Evidence that may be snapshotted", encoding="utf-8")
    store = CompanyBrainStore(tmp_path / "cartridge")
    reference_id = _reference(store, source)
    snapshot_id = store.materialize_snapshot(reference_id, Principal("reader"))

    assert snapshot_id != reference_id
    snapshot = store.inspect_evidence(snapshot_id, Principal("reader"), strong=True)
    assert snapshot["storage_mode"] == "snapshot"
    assert snapshot["availability"]["status"] == "available"
    assert store.health()["snapshot_bytes"] == source.stat().st_size


def test_evaluation_reports_zero_reference_copy_amplification(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("Reference-only evidence", encoding="utf-8")
    store = CompanyBrainStore(tmp_path / "cartridge")
    _reference(store, source)
    evaluation = store.evaluate()
    assert evaluation["passed"] is True
    assert evaluation["checks"]["reference_mode_copied_bytes_zero"] is True
    assert evaluation["metrics"]["reference_mode_copied_bytes"] == 0
    assert evaluation["metrics"]["reference_source_bytes"] == source.stat().st_size


def test_segments_round_trip_native_locator_into_multimodal_context(tmp_path):
    source = tmp_path / "runbook.html"
    source.write_text(
        "<main><h1>Deployment</h1><p>Production deploys require two reviewers.</p></main>",
        encoding="utf-8",
    )
    store = CompanyBrainStore(tmp_path / "cartridge")
    evidence_id = _reference(store, source, artifact_type="html")
    principal = Principal("reader")
    segmented = store.inspect_and_segment(evidence_id, principal, max_text=2_000)
    assert segmented["segment_ids"]
    segment_id = segmented["segment_ids"][-1]
    segment = store.segments_for_evidence(evidence_id, principal)[-1]
    assert segment["native_locator"]["heading"] == "Deployment"

    memory_id = store.add_memory(MemoryInput(
        memory_type="constraint",
        title="Production deployment review requirement",
        statement="Production deployments require approval from two reviewers.",
        lifecycle="active",
        source_native_id="deployment-review-rule",
        evidence=[EvidenceReference(
            evidence_id=evidence_id,
            segment_id=segment_id,
            quote="Production deploys require two reviewers.",
        )],
    ))
    context = compile_context(store, ContextRequest(
        task="Explain production deployment approval",
        principal=principal,
        token_budget=512,
    ))
    assert context["constraints"][0]["memory_id"] == memory_id
    attachment = context["artifact_attachments"][0]
    assert attachment["artifact_type"] == "html"
    assert attachment["native_locator"]["heading"] == "Deployment"
    assert attachment["availability"]["status"] == "available"


def test_segment_cannot_be_attached_to_different_evidence(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("First source text", encoding="utf-8")
    second.write_text("Second source text", encoding="utf-8")
    store = CompanyBrainStore(tmp_path / "cartridge")
    first_id = _reference(store, first, native_id="first")
    second_id = _reference(store, second, native_id="second")
    segment_id = store.inspect_and_segment(first_id, Principal("reader"))["segment_ids"][0]
    with pytest.raises(ValueError, match="does not belong"):
        store.add_memory(MemoryInput(
            memory_type="fact",
            title="Invalid cross-source citation",
            statement="This memory deliberately cites a mismatched segment.",
            evidence=[EvidenceReference(evidence_id=second_id, segment_id=segment_id)],
        ))


def test_changed_reference_is_excluded_from_retrieval(tmp_path):
    source = tmp_path / "decision.txt"
    source.write_text("Use PostgreSQL for the audit database.", encoding="utf-8")
    store = CompanyBrainStore(tmp_path / "cartridge")
    evidence_id = _reference(store, source)
    store.add_memory(MemoryInput(
        memory_type="decision",
        title="Use PostgreSQL for audit storage",
        statement="PostgreSQL is the approved database for audit storage.",
        lifecycle="active",
        source_native_id="audit-storage-decision",
        evidence=[EvidenceReference(evidence_id=evidence_id)],
    ))
    assert search_memories(store, "PostgreSQL audit", Principal("reader"))
    source.write_text("Use SQLite for the audit database instead.", encoding="utf-8")
    assert search_memories(store, "PostgreSQL audit", Principal("reader")) == []


def test_text_csv_html_and_image_adapters_use_native_coordinates(tmp_path):
    text_path = tmp_path / "notes.txt"
    text_path.write_text("one\ntwo\nthree\nfour", encoding="utf-8")
    text = inspect_artifact(text_path, native_locator={"lines": [2, 3]})
    assert text["segments"][0]["text"] == "two\nthree"

    csv_path = tmp_path / "metrics.csv"
    csv_path.write_text("month,revenue\nJan,10\nFeb,20\n", encoding="utf-8")
    csv_result = inspect_artifact(csv_path, native_locator={"rows": [2, 3]})
    assert csv_result["segments"][0]["native_locator"] == {"rows": [2, 3]}
    assert "Feb,20" in csv_result["segments"][0]["text"]

    html_path = tmp_path / "page.html"
    html_path.write_text("<h2>Policy</h2><p>Keep evidence local.</p>", encoding="utf-8")
    html = inspect_artifact(html_path)
    assert any(segment["native_locator"]["heading"] == "Policy" for segment in html["segments"])

    png_path = tmp_path / "screen.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 640, 480) + b"\x00" * 8)
    image = inspect_artifact(png_path, native_locator={"region": [0.1, 0.2, 0.5, 0.5]})
    assert image["metadata"] == {"width": 640, "height": 480}
    assert image["segments"][0]["native_locator"]["region"] == [0.1, 0.2, 0.5, 0.5]


def test_docx_and_xlsx_adapters_return_precise_ranges(tmp_path):
    docx_path = tmp_path / "policy.docx"
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>First paragraph</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body></w:document>""",
        )
    docx = inspect_artifact(docx_path, native_locator={"paragraphs": [2, 2]})
    assert docx["segments"][0]["text"] == "Second paragraph"
    assert docx["segments"][0]["native_locator"] == {"paragraphs": [2, 2]}

    xlsx_path = tmp_path / "metrics.xlsx"
    with zipfile.ZipFile(xlsx_path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Revenue" sheetId="1" r:id="rId1"/></sheets></workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="worksheet"/></Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><v>100</v></c><c r="B1"><f>A1*2</f><v>200</v></c></row></sheetData></worksheet>""",
        )
    workbook = inspect_artifact(
        xlsx_path, native_locator={"sheet": "Revenue", "range": "A1:B1"}
    )
    assert workbook["segments"][0]["native_locator"] == {"sheet": "Revenue", "range": "A1:B1"}
    assert "B1\t=A1*2 -> 200" in workbook["segments"][0]["text"]


def test_schema_v1_is_upgraded_additively(tmp_path):
    store = CompanyBrainStore(tmp_path)
    store.brain_dir.mkdir(parents=True)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            """CREATE TABLE evidence(
            evidence_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,source_type TEXT NOT NULL,
            source_locator TEXT NOT NULL,source_native_id TEXT NOT NULL,content_hash TEXT NOT NULL,
            mime_type TEXT NOT NULL,byte_length INTEGER NOT NULL,observed_at TEXT NOT NULL,
            source_modified_at TEXT NOT NULL,classification TEXT NOT NULL,access_policy_json TEXT NOT NULL,
            retention_policy_id TEXT NOT NULL,ingestion_run_id TEXT NOT NULL,
            supersedes_evidence_id TEXT NOT NULL,blob_path TEXT NOT NULL,created_at TEXT NOT NULL,
            UNIQUE(tenant_id,source_type,source_native_id,content_hash))"""
        )
    store.initialize()
    with store.read_connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(evidence)")}
        version = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
    assert {"storage_mode", "artifact_type", "source_identity_json"}.issubset(columns)
    assert version == "3"


def test_cli_register_and_remember_file_are_reference_first(tmp_path, runner):
    cartridge = tmp_path / "cartridge"
    source = tmp_path / "requirements.html"
    source.write_text("<p>Customer exports require approval.</p>", encoding="utf-8")
    runner("init", workspace=cartridge)

    code, output, _ = runner(
        "brain", "register", str(source), "--artifact-type", "html",
        workspace=cartridge,
    )
    assert code == 0
    registered = json.loads(output)
    assert registered["copied_source_bytes"] == 0

    code, output, _ = runner(
        "brain", "remember",
        "--type", "constraint",
        "--title", "Customer export approval",
        "--statement", "Customer data exports require explicit approval.",
        "--evidence-file", str(source),
        workspace=cartridge,
    )
    assert code == 0
    assert json.loads(output)["lifecycle"] == "candidate"
    assert not (cartridge / "evidence" / "blobs").exists()


@pytest.mark.asyncio
async def test_mcp_artifact_register_inspect_and_snapshot_are_explicit(tmp_path):
    from llm_kosh.core.memory import init_cartridge
    from llm_kosh.mcp_server import mcp, start_server

    source = tmp_path / "screen.txt"
    source.write_text("Visible source", encoding="utf-8")
    cartridge = tmp_path / "cartridge"
    init_cartridge(cartridge, "MCP test")
    set_cartridge_mode(cartridge, "company_brain")
    start_server(
        cartridge, stdio=False, http=False,
        allow_write=True, allow_mutate=False, allow_private=False,
    )
    registered_raw = await mcp.call_tool("company_artifact_register", {
        "file_path": str(source), "artifact_type": "plain_text",
    })
    registered_text = registered_raw[0].text if isinstance(registered_raw, list) else str(registered_raw)
    evidence_id = json.loads(registered_text)["evidence_id"]
    assert not (cartridge / "evidence" / "blobs").exists()

    inspected_raw = await mcp.call_tool("company_artifact_inspect", {
        "evidence_id": evidence_id,
        "native_locator_json": json.dumps({"lines": [1, 1]}),
    })
    inspected_text = inspected_raw[0].text if isinstance(inspected_raw, list) else str(inspected_raw)
    assert json.loads(inspected_text)["inspection"]["segments"][0]["text"] == "Visible source"

    snapshot_raw = await mcp.call_tool("company_artifact_snapshot", {
        "evidence_id": evidence_id,
    })
    snapshot_text = snapshot_raw[0].text if isinstance(snapshot_raw, list) else str(snapshot_raw)
    assert json.loads(snapshot_text)["storage_mode"] == "snapshot"
    assert (cartridge / "evidence" / "blobs").exists()
