import json
import sqlite3

import pytest

from llm_kosh.company_brain.context import compile_context
from llm_kosh.company_brain.models import ContextRequest, EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.company_brain.understanding import normalize_jsonl, understand_evidence


def _registered_jsonl(tmp_path, store):
    source = tmp_path / "session.jsonl"
    records = [
        {
            "id": "1", "session_id": "chat-1", "role": "user",
            "timestamp": "2026-08-01T09:00:00Z", "project": "audit",
            "content": "Build a JSONL audit event parser for the company brain.",
        },
        {
            "id": "2", "session_id": "chat-1", "role": "assistant",
            "timestamp": "2026-08-01T09:05:00Z", "project": "audit",
            "content": "We decided to use streaming JSONL because source files can be large.",
        },
        {
            "id": "3", "session_id": "chat-1", "type": "file_change",
            "timestamp": "2026-08-01T09:20:00Z", "project": "audit",
            "summary": "Implemented the parser with bounded line reads.",
        },
        {
            "id": "4", "session_id": "chat-1", "role": "assistant",
            "timestamp": "2026-08-01T09:30:00Z", "project": "audit",
            "content": "Implementation completed and all parser tests passed.",
        },
        {
            "id": "5", "session_id": "chat-1", "role": "user",
            "timestamp": "2026-08-01T11:00:00Z", "project": "billing",
            "content": "Investigate the billing export failure.",
        },
        {
            "id": "6", "session_id": "chat-1", "role": "assistant",
            "timestamp": "2026-08-01T11:05:00Z", "project": "billing",
            "content": "The investigation is blocked; we must wait for an authorized export.",
        },
    ]
    source.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    evidence_id = store.put_evidence(EvidenceInput(
        source_type="local_file",
        source_locator=str(source),
        source_native_id=str(source),
        storage_mode="reference",
        artifact_type="structured_data",
        classification="internal",
    ))
    return evidence_id


def _count(store, table):
    with store.read_connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_understanding_dry_run_has_no_pipeline_writes(tmp_path):
    store = CompanyBrainStore(tmp_path / "brain-root")
    evidence_id = _registered_jsonl(tmp_path, store)
    principal = Principal("tester", clearance="internal")

    report = understand_evidence(store, evidence_id, principal, dry_run=True)

    assert report["metrics"]["events"] == 6
    assert report["metrics"]["sessions"] == 1
    assert report["metrics"]["episodes"] == 2
    assert report["metrics"]["candidate_memories"] >= 3
    assert report["checkpoint_advanced"] is False
    for table in (
        "sessions", "normalized_events", "episodes", "memories",
        "extraction_runs", "connector_checkpoints",
    ):
        assert _count(store, table) == 0


def test_understanding_persists_reference_linked_graph_idempotently(tmp_path):
    store = CompanyBrainStore(tmp_path / "brain-root")
    evidence_id = _registered_jsonl(tmp_path, store)
    principal = Principal("tester", clearance="internal")

    first = understand_evidence(store, evidence_id, principal)
    second = understand_evidence(store, evidence_id, principal)

    assert first["run_id"] == second["run_id"]
    assert _count(store, "sessions") == 1
    assert _count(store, "normalized_events") == 6
    assert _count(store, "episodes") == 2
    assert _count(store, "memories") == first["metrics"]["candidate_memories"]
    assert _count(store, "episode_memories") == first["metrics"]["candidate_memories"]
    assert _count(store, "extraction_runs") == 1
    checkpoint = store.get_checkpoint("session-jsonl", evidence_id)
    assert checkpoint["last_line"] == 6

    episodes = store.list_episodes(principal)
    assert {episode["status"] for episode in episodes} == {"completed", "blocked"}
    billing = next(episode for episode in episodes if episode["project_id"] == "billing")
    expanded = store.get_episode(billing["episode_id"], principal)
    assert len(expanded["events"]) == 2
    assert expanded["memory_links"]


def test_normalizer_skips_malformed_and_redacts_secret_values(tmp_path):
    store = CompanyBrainStore(tmp_path / "brain-root")
    source = tmp_path / "mixed.jsonl"
    source.write_text(
        '{"id":"1","role":"user","content":"password: do-not-store build parser"}\n'
        '{"id":"2","role":"system","content":"private system instruction"}\n'
        '{"id":"3","type":"tool_result","output":"private output; tests passed"}\n'
        'not json\n',
        encoding="utf-8",
    )
    evidence_id = store.put_evidence(EvidenceInput(
        source_type="local_file", source_locator=str(source),
        source_native_id=str(source), storage_mode="reference",
        artifact_type="structured_data", classification="internal",
    ))
    normalized = normalize_jsonl(
        store, evidence_id, Principal("tester", clearance="internal"),
    )
    assert normalized["metrics"]["malformed_lines"] == 1
    assert "do-not-store" not in normalized["events"][0]["summary"]
    assert "[REDACTED]" in normalized["events"][0]["summary"]
    assert normalized["events"][1]["summary"].startswith("System instruction event")
    assert "private system instruction" not in normalized["events"][1]["summary"]
    assert normalized["events"][2]["summary"].startswith("Tool result: success reported")
    assert "private output" not in normalized["events"][2]["summary"]


def test_context_includes_bounded_observed_episode_narratives(tmp_path):
    store = CompanyBrainStore(tmp_path / "brain-root")
    evidence_id = _registered_jsonl(tmp_path, store)
    principal = Principal("tester", clearance="internal")
    understand_evidence(store, evidence_id, principal)

    pack = compile_context(store, ContextRequest(
        task="Explain the JSONL audit parser work",
        principal=principal,
        project_id="audit",
        token_budget=512,
    ))

    assert pack["episode_context"]
    assert pack["episode_context"][0]["authority"] == "observed_activity"
    assert pack["episode_context"][0]["evidence_refs"] == [evidence_id]
    assert pack["estimated_tokens"] <= pack["token_budget"]
    denied = Principal("limited", clearance="public")
    assert store.search_episodes("audit parser", denied) == []


def test_normalizer_bounds_overlong_lines_and_continues(tmp_path):
    store = CompanyBrainStore(tmp_path / "brain-root")
    source = tmp_path / "overlong.jsonl"
    source.write_text(
        '{"content":"' + ("x" * 1_048_576) + '"}\n'
        '{"id":"ok","role":"user","content":"Build a bounded reader"}\n',
        encoding="utf-8",
    )
    evidence_id = store.put_evidence(EvidenceInput(
        source_type="local_file", source_locator=str(source),
        source_native_id=str(source), storage_mode="reference",
        artifact_type="structured_data", classification="internal",
    ))
    normalized = normalize_jsonl(
        store, evidence_id, Principal("tester", clearance="internal"),
    )
    assert normalized["metrics"]["overlong_lines"] == 1
    assert normalized["metrics"]["events"] == 1
    assert normalized["events"][0]["source_native_id"].endswith(":ok")


def test_v2_episode_table_is_upgraded_before_native_index_creation(tmp_path):
    store = CompanyBrainStore(tmp_path / "brain-root")
    store.brain_dir.mkdir(parents=True)
    with sqlite3.connect(store.db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE episodes (
                episode_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                title TEXT NOT NULL,
                goal TEXT NOT NULL,
                project_id TEXT NOT NULL,
                participants_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                status TEXT NOT NULL,
                outcome_summary TEXT NOT NULL,
                session_ids_json TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                confidence REAL NOT NULL,
                classification TEXT NOT NULL,
                access_policy_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO episodes VALUES(
                'ep_old','local','Old useful episode','Preserve this goal','legacy','[]',
                '2026-01-01','2026-01-01','partial','','[]','[]',0.5,
                'internal','{}','2026-01-01','2026-01-01'
            );
            """
        )

    store.initialize()

    with store.read_connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
        old = conn.execute("SELECT * FROM episodes WHERE episode_id='ep_old'").fetchone()
        version = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
    assert {"phase_summary_json", "boundary_signals_json", "source_native_id"} <= columns
    assert old["goal"] == "Preserve this goal"
    assert version == "3"


def test_cli_runs_understanding_graph_and_queries_episodes(tmp_path, runner):
    cartridge = tmp_path / "cartridge"
    source_store = CompanyBrainStore(cartridge)
    source = tmp_path / "cli-session.jsonl"
    source.write_text(
        json.dumps({
            "id": "1", "session_id": "cli-1", "role": "user",
            "content": "Build the invoice parser", "project": "billing",
        }) + "\n" + json.dumps({
            "id": "2", "session_id": "cli-1", "role": "assistant",
            "content": "The invoice parser implementation completed and tests passed.",
            "project": "billing",
        }),
        encoding="utf-8",
    )
    runner("init", workspace=cartridge)
    code, output, _ = runner(
        "brain", "register", str(source), "--artifact-type", "structured_data",
        workspace=cartridge,
    )
    assert code == 0
    evidence_id = json.loads(output)["evidence_id"]

    code, output, _ = runner(
        "brain", "understand", evidence_id, "--dry-run", workspace=cartridge,
    )
    assert code == 0
    assert json.loads(output)["checkpoint_advanced"] is False
    code, output, _ = runner(
        "brain", "understand", evidence_id, workspace=cartridge,
    )
    assert code == 0
    assert json.loads(output)["metrics"]["episodes"] == 1
    code, output, _ = runner(
        "brain", "episodes", "--query", "invoice parser", workspace=cartridge,
    )
    assert code == 0
    assert json.loads(output)[0]["project_id"] == "billing"
    assert source_store.health()["episodes"] == 1


@pytest.mark.asyncio
async def test_mcp_exposes_understanding_and_episode_reads(tmp_path):
    from llm_kosh.core.memory import init_cartridge
    from llm_kosh.core.profile import set_cartridge_mode
    from llm_kosh.mcp_server import mcp, start_server

    cartridge = tmp_path / "cartridge"
    source = tmp_path / "mcp-session.jsonl"
    source.write_text(json.dumps({
        "id": "1", "session_id": "mcp-1", "role": "user",
        "content": "Plan to update the release process", "project": "release",
    }), encoding="utf-8")
    init_cartridge(cartridge, "MCP understanding test")
    set_cartridge_mode(cartridge, "company_brain")
    start_server(
        cartridge, stdio=False, http=False,
        allow_write=True, allow_mutate=False, allow_private=False,
    )
    registered_raw = await mcp.call_tool("company_artifact_register", {
        "file_path": str(source), "artifact_type": "structured_data",
    })
    registered_text = registered_raw[0].text if isinstance(registered_raw, list) else str(registered_raw)
    evidence_id = json.loads(registered_text)["evidence_id"]
    understood_raw = await mcp.call_tool("company_session_understand", {
        "evidence_id": evidence_id,
    })
    understood_text = understood_raw[0].text if isinstance(understood_raw, list) else str(understood_raw)
    assert json.loads(understood_text)["metrics"]["sessions"] == 1
    episodes_raw = await mcp.call_tool("company_episodes_search", {
        "query": "release process",
    })
    episodes_text = episodes_raw[0].text if isinstance(episodes_raw, list) else str(episodes_raw)
    assert json.loads(episodes_text)[0]["project_id"] == "release"
