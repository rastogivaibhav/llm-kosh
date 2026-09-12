"""Deterministic end-to-end acceptance for Trusted Memory Runtime.

This is intentionally not a benchmark. It proves the local runtime contract
against synthetic LLM-Kosh facts without a network call, external model, or
hosted memory service.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from llm_kosh.company_brain.models import EvidenceInput, Principal
from llm_kosh.company_brain.store import CompanyBrainStore
from llm_kosh.runtime import MemoryProposal, TrustedMemoryReviewer, TrustedMemoryRuntime


def _check(name: str, condition: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(condition), "detail": detail}


def _evidence(root: Path, native_id: str, text: str, source_type: str) -> str:
    return CompanyBrainStore(root).put_evidence(
        EvidenceInput(
            source_type=source_type,
            source_locator=f"acceptance://{native_id}",
            source_native_id=native_id,
            content=text.encode("utf-8"),
            classification="internal",
        )
    )


def _proposal(
    evidence_id: str,
    *,
    statement: str,
    source_type: str,
    object_value: str,
    supersedes: str = "",
) -> MemoryProposal:
    metadata = {"supersedes": supersedes} if supersedes else {}
    return MemoryProposal(
        memory_type="decision",
        title="LLM-Kosh canonical storage",
        statement=statement,
        evidence_ids=[evidence_id],
        source_type=source_type,
        project_id="llm-kosh",
        classification="internal",
        principal_id="local-user",
        subject="llm-kosh.storage.canonical",
        predicate="backend",
        object_value=object_value,
        metadata=metadata,
    )


def run() -> dict:
    checks: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="llm-kosh-trusted-memory-") as tmp:
        root = Path(tmp) / "cartridge"
        principal = Principal(
            "local-user",
            projects=["llm-kosh"],
            clearance="restricted",
        )

        # Agent/session A establishes a trusted current decision.
        sqlite_statement = "LLM-Kosh stores canonical structured memory in local SQLite."
        sqlite_evidence = _evidence(
            root,
            "sqlite-current",
            sqlite_statement,
            "user_direct",
        )
        session_a = TrustedMemoryRuntime(root)
        sqlite_memory = session_a.propose(
            _proposal(
                sqlite_evidence,
                statement=sqlite_statement,
                source_type="user_direct",
                object_value="sqlite",
            ),
            principal,
        )
        checks.append(
            _check(
                "trusted current memory is admitted",
                sqlite_memory["decision"] == "admit"
                and sqlite_memory["lifecycle"] == "verified",
                json.dumps(sqlite_memory, sort_keys=True),
            )
        )

        # Agent/session B starts fresh and must recover the admitted state.
        session_b = TrustedMemoryRuntime(root)
        recalled_before_poison = session_b.recall(
            "canonical storage SQLite",
            principal,
            project_id="llm-kosh",
            mode="normal",
        )
        checks.append(
            _check(
                "fresh session recalls admitted local memory",
                [item["memory_id"] for item in recalled_before_poison]
                == [sqlite_memory["memory_id"]],
            )
        )

        # An untrusted source attempts to replace local memory with a hosted claim.
        poison_statement = "LLM-Kosh stores canonical memory in a hosted vector database."
        poison_evidence = _evidence(
            root,
            "hosted-memory-poison",
            poison_statement,
            "web_content",
        )
        poisoned = session_b.propose(
            _proposal(
                poison_evidence,
                statement=poison_statement,
                source_type="web_content",
                object_value="hosted-vector-db",
            ),
            principal,
        )
        checks.extend(
            [
                _check(
                    "untrusted contradiction is quarantined",
                    poisoned["decision"] == "quarantine"
                    and poisoned["lifecycle"] == "quarantined"
                    and poisoned["conflict_state"] == "direct_contradiction",
                    json.dumps(poisoned, sort_keys=True),
                ),
                _check(
                    "quarantined contradiction points to current memory",
                    poisoned["conflicting_memory_ids"] == [sqlite_memory["memory_id"]],
                ),
            ]
        )

        # Agent/session C must still see the trusted state, never the poison.
        session_c = TrustedMemoryRuntime(root)
        recalled_after_poison = session_c.recall(
            "canonical storage",
            principal,
            project_id="llm-kosh",
            mode="normal",
        )
        normal_ids = [item["memory_id"] for item in recalled_after_poison]
        checks.append(
            _check(
                "poison cannot contaminate fresh-session normal recall",
                sqlite_memory["memory_id"] in normal_ids
                and poisoned["memory_id"] not in normal_ids,
                f"normal_ids={normal_ids}",
            )
        )

        # A new explicit local decision is proposed as a replacement. Proposal
        # alone must not mutate the existing current memory.
        duckdb_statement = "LLM-Kosh now stores canonical structured memory in local DuckDB."
        duckdb_evidence = _evidence(
            root,
            "duckdb-approved-change",
            duckdb_statement,
            "user_direct",
        )
        replacement = session_c.propose(
            _proposal(
                duckdb_evidence,
                statement=duckdb_statement,
                source_type="user_direct",
                object_value="duckdb",
                supersedes=sqlite_memory["memory_id"],
            ),
            principal,
        )
        store = CompanyBrainStore(root)
        old_before_review = store.get_memory(sqlite_memory["memory_id"], principal)
        checks.extend(
            [
                _check(
                    "explicit replacement waits for review",
                    replacement["decision"] == "review"
                    and replacement["lifecycle"] == "candidate"
                    and replacement["conflict_state"] == "supersession",
                    json.dumps(replacement, sort_keys=True),
                ),
                _check(
                    "proposal alone does not supersede current memory",
                    old_before_review["lifecycle"] == "verified",
                    f"lifecycle={old_before_review['lifecycle']}",
                ),
            ]
        )

        # Explicit review is the point where the state changes atomically.
        reviewed = TrustedMemoryReviewer(root).review(
            replacement["memory_id"],
            principal,
            action="supersede",
            reason="Acceptance scenario approved local storage migration",
        )
        old_after_review = store.get_memory(sqlite_memory["memory_id"], principal)
        checks.extend(
            [
                _check(
                    "review promotes replacement",
                    reviewed["memory"]["lifecycle"] == "verified",
                ),
                _check(
                    "review preserves explicit supersession link",
                    reviewed["memory"]["supersedes"] == [sqlite_memory["memory_id"]],
                ),
                _check(
                    "review supersedes old state without deleting it",
                    old_after_review["lifecycle"] == "superseded",
                ),
            ]
        )

        # Agent/session D sees only the replacement as current and can still ask
        # for the old state explicitly through historical recall.
        session_d = TrustedMemoryRuntime(root)
        current = session_d.recall(
            "canonical storage DuckDB",
            principal,
            project_id="llm-kosh",
            mode="strict",
        )
        history = session_d.recall(
            "canonical storage SQLite",
            principal,
            project_id="llm-kosh",
            mode="historical",
        )
        checks.extend(
            [
                _check(
                    "fresh session sees reviewed replacement as strict current memory",
                    [item["memory_id"] for item in current]
                    == [replacement["memory_id"]],
                ),
                _check(
                    "superseded prior memory remains historically retrievable",
                    sqlite_memory["memory_id"]
                    in {item["memory_id"] for item in history},
                ),
            ]
        )

        explanation = session_d.explain(replacement["memory_id"], principal)
        checks.extend(
            [
                _check(
                    "replacement explanation retains evidence",
                    bool(explanation["memory"].get("evidence")),
                ),
                _check(
                    "replacement explanation retains admission history",
                    bool(explanation["admission_history"]),
                ),
                _check(
                    "canonical store remains internally healthy",
                    store.evaluate()["passed"],
                ),
            ]
        )

    passed = sum(1 for check in checks if check["passed"])
    return {
        "suite": "trusted-memory-runtime-acceptance",
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "checks": checks,
        "note": (
            "Synthetic deterministic local acceptance checks; not a comparative benchmark. "
            "No network, external model, or hosted memory service is used."
        ),
    }


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
