from __future__ import annotations

import json

import pytest

from llm_kosh.runtime import (
    AdmissionAssessment,
    AdmissionDecision,
    AdmissionPolicy,
    Authority,
    ConflictState,
    MemoryProposal,
    RetrievalMode,
    RiskTier,
    load_admission_policy,
)


def test_memory_proposal_requires_evidence() -> None:
    with pytest.raises(ValueError, match="evidence_id"):
        MemoryProposal(
            memory_type="decision",
            title="Messaging platform",
            statement="Atlas uses Google Pub/Sub for project messaging.",
            evidence_ids=[],
            source_type="repository",
        )


def test_structured_claim_must_be_complete() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        MemoryProposal(
            memory_type="decision",
            title="Messaging platform",
            statement="Atlas uses Google Pub/Sub for project messaging.",
            evidence_ids=["ev_1"],
            source_type="repository",
            subject="project:atlas.messaging",
            predicate="implementation",
        )


def test_proposal_normalizes_fields_and_serializes() -> None:
    proposal = MemoryProposal(
        memory_type=" Decision ",
        title=" Messaging platform ",
        statement="Atlas uses Google Pub/Sub for project messaging.",
        evidence_ids=[" ev_1 "],
        source_type=" Repository ",
        subject=" project:atlas.messaging ",
        predicate=" implementation ",
        object_value=" pubsub ",
    )
    assert proposal.memory_type == "decision"
    assert proposal.source_type == "repository"
    assert proposal.evidence_ids == ["ev_1"]
    assert proposal.has_structured_claim is True
    assert proposal.to_dict()["subject"] == "project:atlas.messaging"


def test_assessment_is_json_safe() -> None:
    assessment = AdmissionAssessment(
        proposal_id="proposal_1",
        decision=AdmissionDecision.QUARANTINE,
        authority=Authority.UNTRUSTED,
        risk_tier=RiskTier.HIGH,
        conflict_state=ConflictState.DIRECT_CONTRADICTION,
        evidence_strength=0.4,
        reasons=["conflicts with stronger active memory"],
        conflicting_memory_ids=["mem_1"],
    )
    encoded = json.dumps(assessment.to_dict())
    assert '"decision": "quarantine"' in encoded
    assert assessment.to_dict()["conflict_state"] == "direct_contradiction"


def test_retrieval_modes_are_explicit() -> None:
    assert {mode.value for mode in RetrievalMode} == {
        "normal", "strict", "historical", "candidate"
    }


def test_default_authority_and_admission_matrix() -> None:
    policy = AdmissionPolicy()
    assert policy.authority_for("user_direct") is Authority.AUTHORITATIVE
    assert policy.authority_for("repository") is Authority.TRUSTED
    assert policy.authority_for("web_content") is Authority.UNTRUSTED
    assert policy.authority_for("made_up_source") is Authority.UNKNOWN

    assert policy.decision_for(Authority.AUTHORITATIVE, RiskTier.LOW) is AdmissionDecision.ADMIT
    assert policy.decision_for(Authority.AUTHORITATIVE, RiskTier.HIGH) is AdmissionDecision.REVIEW
    assert policy.decision_for(Authority.TRUSTED, RiskTier.MEDIUM) is AdmissionDecision.REVIEW
    assert policy.decision_for(Authority.UNTRUSTED, RiskTier.CRITICAL) is AdmissionDecision.REJECT


def test_policy_can_disable_low_risk_auto_admission() -> None:
    policy = AdmissionPolicy(auto_admit_low_risk=False)
    assert policy.decision_for(Authority.TRUSTED, RiskTier.LOW) is AdmissionDecision.REVIEW


def test_policy_overrides_from_existing_cartridge_policy(tmp_path) -> None:
    (tmp_path / "CARTRIDGE_POLICY.json").write_text(
        json.dumps(
            {
                "mcp": {"read_only_default": True},
                "trusted_memory": {
                    "auto_admit_low_risk": False,
                    "sources": {"tool_result": "trusted"},
                    "matrix": {"trusted": {"medium": "admit"}},
                },
            }
        ),
        encoding="utf-8",
    )
    policy = load_admission_policy(tmp_path)
    assert policy.authority_for("tool_result") is Authority.TRUSTED
    assert policy.decision_for(Authority.TRUSTED, RiskTier.MEDIUM) is AdmissionDecision.ADMIT
    assert policy.decision_for(Authority.TRUSTED, RiskTier.LOW) is AdmissionDecision.REVIEW


def test_missing_policy_file_uses_conservative_defaults(tmp_path) -> None:
    policy = load_admission_policy(tmp_path)
    assert policy.enabled is True
    assert policy.default_mode is AdmissionDecision.REVIEW
    assert policy.decision_for(Authority.UNKNOWN, RiskTier.MEDIUM) is AdmissionDecision.QUARANTINE
