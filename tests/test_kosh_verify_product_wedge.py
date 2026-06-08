from __future__ import annotations

from pathlib import Path

from llm_kosh.verify import KoshVerify, seed_incident_cartridge


def test_kosh_verify_incident_demo_surfaces_project_native_signals(tmp_path: Path) -> None:
    kv = seed_incident_cartridge(tmp_path)
    report = kv.verify(
        "Why did checkout fail and what evidence contradicts the explanation?",
        temporal_context="2026-05-01T13:30:00+00:00",
        depth=5,
        dialectic=True,
    )
    assert report.status in {"reopened_for_non_convergent_review", "survived_opposition", "challenged", "needs_evidence"}
    assert report.primary_answer is not None
    assert report.paths
    assert report.inferred_not_discovered, "compressed A -> C shortcut should be labelled inferred, not discovered"
    assert report.missing_evidence, "opposition should ask falsification / missing-evidence questions"
    assert any("memory" in fact["content"].lower() for fact in report.facts)


def test_kosh_verify_no_evidence_abstains(tmp_path: Path) -> None:
    kv = seed_incident_cartridge(tmp_path)
    report = kv.verify(
        "What happened to the moon cheese inventory?",
        temporal_context="2026-05-01T13:30:00+00:00",
        depth=3,
        dialectic=True,
    )
    assert report.abstain is True
    assert report.status == "no_evidence"
    assert report.primary_answer is None


def test_kosh_verify_export_report(tmp_path: Path) -> None:
    kv = seed_incident_cartridge(tmp_path / "cart")
    report = kv.verify("Why did checkout fail?", temporal_context="2026-05-01T13:30:00+00:00")
    out = kv.export_report(report, tmp_path / "out" / "report.json")
    assert out.exists()
    assert "Kosh Verify" in out.read_text(encoding="utf-8")
