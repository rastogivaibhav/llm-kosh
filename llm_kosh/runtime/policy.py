"""Deterministic policy for trusted-memory admission.

Policy is deliberately model-free. It may be overridden through the existing
CARTRIDGE_POLICY.json file under the ``trusted_memory`` section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from llm_kosh.core.utils import read_json

from .models import AdmissionDecision, Authority, MemorySource, RiskTier


POLICY_VERSION = "trusted-memory-v1"


_DEFAULT_SOURCE_AUTHORITIES: Dict[str, Authority] = {
    MemorySource.USER_DIRECT.value: Authority.AUTHORITATIVE,
    MemorySource.LOCAL_FILE.value: Authority.TRUSTED,
    MemorySource.REPOSITORY.value: Authority.TRUSTED,
    MemorySource.TOOL_RESULT.value: Authority.CONTEXTUAL,
    MemorySource.AGENT_OBSERVATION.value: Authority.CONTEXTUAL,
    MemorySource.SESSION_TRANSCRIPT.value: Authority.CONTEXTUAL,
    MemorySource.IMPORTED_DOCUMENT.value: Authority.CONTEXTUAL,
    MemorySource.WEB_CONTENT.value: Authority.UNTRUSTED,
    MemorySource.AGENT_INFERENCE.value: Authority.CONTEXTUAL,
    MemorySource.UNKNOWN.value: Authority.UNKNOWN,
}


_DEFAULT_MATRIX: Dict[Authority, Dict[RiskTier, AdmissionDecision]] = {
    Authority.AUTHORITATIVE: {
        RiskTier.LOW: AdmissionDecision.ADMIT,
        RiskTier.MEDIUM: AdmissionDecision.ADMIT,
        RiskTier.HIGH: AdmissionDecision.REVIEW,
        RiskTier.CRITICAL: AdmissionDecision.REVIEW,
    },
    Authority.TRUSTED: {
        RiskTier.LOW: AdmissionDecision.ADMIT,
        RiskTier.MEDIUM: AdmissionDecision.REVIEW,
        RiskTier.HIGH: AdmissionDecision.REVIEW,
        RiskTier.CRITICAL: AdmissionDecision.QUARANTINE,
    },
    Authority.CONTEXTUAL: {
        RiskTier.LOW: AdmissionDecision.REVIEW,
        RiskTier.MEDIUM: AdmissionDecision.REVIEW,
        RiskTier.HIGH: AdmissionDecision.QUARANTINE,
        RiskTier.CRITICAL: AdmissionDecision.QUARANTINE,
    },
    Authority.UNTRUSTED: {
        RiskTier.LOW: AdmissionDecision.QUARANTINE,
        RiskTier.MEDIUM: AdmissionDecision.QUARANTINE,
        RiskTier.HIGH: AdmissionDecision.QUARANTINE,
        RiskTier.CRITICAL: AdmissionDecision.REJECT,
    },
    Authority.UNKNOWN: {
        RiskTier.LOW: AdmissionDecision.REVIEW,
        RiskTier.MEDIUM: AdmissionDecision.QUARANTINE,
        RiskTier.HIGH: AdmissionDecision.QUARANTINE,
        RiskTier.CRITICAL: AdmissionDecision.REJECT,
    },
}


def _enum_value(enum_type, value: Any, *, field_name: str):
    try:
        return enum_type(str(value).strip().lower())
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"Unsupported {field_name} {value!r}; expected one of: {allowed}") from exc


@dataclass(frozen=True)
class AdmissionPolicy:
    """Human-readable deterministic policy used by the admission engine."""

    version: str = POLICY_VERSION
    enabled: bool = True
    default_mode: AdmissionDecision = AdmissionDecision.REVIEW
    auto_admit_low_risk: bool = True
    critical_requires_review: bool = True
    source_authorities: Dict[str, Authority] = field(
        default_factory=lambda: dict(_DEFAULT_SOURCE_AUTHORITIES)
    )
    matrix: Dict[Authority, Dict[RiskTier, AdmissionDecision]] = field(
        default_factory=lambda: {
            authority: dict(decisions) for authority, decisions in _DEFAULT_MATRIX.items()
        }
    )

    def authority_for(self, source_type: str) -> Authority:
        normalized = (source_type or MemorySource.UNKNOWN.value).strip().lower()
        return self.source_authorities.get(normalized, Authority.UNKNOWN)

    def decision_for(self, authority: Authority, risk_tier: RiskTier) -> AdmissionDecision:
        if not self.enabled:
            return AdmissionDecision.REVIEW
        decision = self.matrix.get(authority, {}).get(risk_tier, self.default_mode)
        if risk_tier is RiskTier.CRITICAL and self.critical_requires_review:
            if decision is AdmissionDecision.ADMIT:
                return AdmissionDecision.REVIEW
        if risk_tier is RiskTier.LOW and not self.auto_admit_low_risk:
            if decision is AdmissionDecision.ADMIT:
                return AdmissionDecision.REVIEW
        return decision

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "AdmissionPolicy":
        value = value or {}
        source_authorities = dict(_DEFAULT_SOURCE_AUTHORITIES)
        for source, authority in (value.get("sources") or {}).items():
            source_authorities[str(source).strip().lower()] = _enum_value(
                Authority, authority, field_name="authority"
            )

        matrix = {
            authority: dict(decisions) for authority, decisions in _DEFAULT_MATRIX.items()
        }
        for authority_name, risks in (value.get("matrix") or {}).items():
            authority = _enum_value(Authority, authority_name, field_name="authority")
            if not isinstance(risks, Mapping):
                raise ValueError(f"matrix entry for {authority.value} must be an object")
            for risk_name, decision_name in risks.items():
                risk = _enum_value(RiskTier, risk_name, field_name="risk tier")
                decision = _enum_value(
                    AdmissionDecision, decision_name, field_name="admission decision"
                )
                matrix.setdefault(authority, {})[risk] = decision

        return cls(
            version=str(value.get("version") or POLICY_VERSION),
            enabled=bool(value.get("enabled", True)),
            default_mode=_enum_value(
                AdmissionDecision,
                value.get("default_mode", AdmissionDecision.REVIEW.value),
                field_name="default admission mode",
            ),
            auto_admit_low_risk=bool(value.get("auto_admit_low_risk", True)),
            critical_requires_review=bool(value.get("critical_requires_review", True)),
            source_authorities=source_authorities,
            matrix=matrix,
        )


def load_admission_policy(root: Path) -> AdmissionPolicy:
    """Load trusted-memory policy from the existing cartridge policy file.

    Missing policy is not an error; conservative defaults are returned. This
    function never creates or mutates configuration.
    """

    policy_path = Path(root).expanduser() / "CARTRIDGE_POLICY.json"
    if not policy_path.exists():
        return AdmissionPolicy()
    raw = read_json(policy_path) or {}
    section = raw.get("trusted_memory") or raw.get("memory_admission") or {}
    if not isinstance(section, Mapping):
        raise ValueError("CARTRIDGE_POLICY.json trusted_memory must be an object")
    return AdmissionPolicy.from_mapping(section)
