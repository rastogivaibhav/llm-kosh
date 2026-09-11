"""Deterministic acceptance checks for the public Kosh Verify surface.

This is intentionally not a benchmark. It proves a small set of behavioral
contracts against synthetic local evidence without network calls or an LLM.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from llm_kosh.verify import KoshVerify, seed_incident_cartridge


QUESTION = "Why did checkout fail and what evidence contradicts the explanation?"
WHEN = "2026-05-01T13:30:00+00:00"


def _check(name: str, condition: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(condition), "detail": detail}


def run() -> dict:
    checks: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="llm-kosh-verify-acceptance-") as tmp:
        root = Path(tmp) / "incident"
        verifier = seed_incident_cartridge(root)
        report = verifier.verify(
            QUESTION,
            temporal_context=WHEN,
            depth=5,
            dialectic=True,
        )

        checks.extend(
            [
                _check(
                    "grounded report does not abstain",
                    not report.abstain,
                    f"status={report.status}",
                ),
                _check(
                    "grounded report has a primary answer",
                    bool(report.primary_answer.strip()),
                ),
                _check(
                    "causal paths are surfaced",
                    bool(report.paths),
                    f"paths={len(report.paths)}",
                ),
                _check(
                    "inferred-not-discovered relationships are explicit",
                    bool(report.inferred_not_discovered),
                    f"relationships={len(report.inferred_not_discovered)}",
                ),
                _check(
                    "missing evidence is explicit",
                    bool(report.missing_evidence),
                    f"gaps={len(report.missing_evidence)}",
                ),
                _check(
                    "structured report serializes as JSON",
                    isinstance(json.loads(report.to_json()), dict),
                ),
                _check(
                    "provenance explanation is non-empty",
                    bool(verifier.explain_provenance(report).strip()),
                ),
            ]
        )

        empty_root = Path(tmp) / "empty"
        empty_root.mkdir(parents=True, exist_ok=True)
        empty_report = KoshVerify(empty_root).verify(
            "What caused an incident that is not in this cartridge?",
            dialectic=True,
        )
        checks.append(
            _check(
                "no-evidence query abstains",
                empty_report.abstain,
                f"status={empty_report.status}",
            )
        )

    passed = sum(1 for check in checks if check["passed"])
    result = {
        "suite": "kosh-verify-acceptance",
        "passed": passed,
        "total": len(checks),
        "ok": passed == len(checks),
        "checks": checks,
        "note": "Synthetic deterministic acceptance checks; not a comparative benchmark.",
    }
    return result


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
