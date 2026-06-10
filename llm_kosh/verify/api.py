from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import (
    EdgeOrigin,
    EdgeProvenance,
    EdgeRole,
    EdgeType,
    EvidenceRef,
    ReasoningMode,
    TemporalFact,
)
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle


@dataclass
class VerifyReport:
    """Serializable product-level answer from Kosh Verify."""

    question: str
    status: str
    primary_answer: Optional[str]
    stability_score: float
    stability_status: str
    abstain: bool
    temporal_context: Optional[str]
    convergent_summary: Dict[str, Any] = field(default_factory=dict)
    opposition_summary: Dict[str, Any] = field(default_factory=dict)
    facts: List[Dict[str, Any]] = field(default_factory=list)
    paths: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    inferred_not_discovered: List[Dict[str, Any]] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    discarded_or_reopened_facts: List[str] = field(default_factory=list)
    product_claim: str = (
        "Kosh Verify separates evidence, inference, contradiction, temporal validity, "
        "and opposition before returning a verified answer."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str, **kwargs)


class KoshVerify:
    """
    Product/API layer over TheHypoKosh.

    Use this API when positioning the project for collaborators, demos, or
    agent builders.  It exposes the working capabilities of the Python codebase
    without requiring an LLM:

    - temporal-causal verification;
    - provenance-aware path inspection;
    - contradiction surfacing;
    - inferred-vs-discovered separation;
    - dialectic loop: non-convergent -> convergent -> opposition -> reopen;
    - safe no-evidence abstention.
    """

    def __init__(self, cartridge_root: str | Path) -> None:
        self.root = Path(cartridge_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.engine = ReasoningEngine(self.root)

    # ------------------------------------------------------------------ ingestion helpers

    def add_fact(
        self,
        content: str,
        valid_from: datetime,
        valid_until: Optional[datetime] = None,
        documented_at: Optional[datetime] = None,
        confidence: float = 0.85,
        source: str = "user",
    ) -> str:
        """Add a fact without LLM extraction."""
        return self.engine.dag.add_fact(
            content=content,
            ingested_at=datetime.now(timezone.utc),
            documented_at=documented_at or valid_from,
            valid_from=valid_from,
            valid_until=valid_until,
            confidence=confidence,
            source=source,
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        valid_from: datetime,
        confidence: float = 0.75,
        valid_until: Optional[datetime] = None,
        origin: str = EdgeOrigin.OBSERVED.value,
        role: str = EdgeRole.MECHANISTIC.value,
        evidence_source: Optional[str] = None,
        derived_from: Optional[List[str]] = None,
    ) -> str:
        evidence_refs = []
        if evidence_source:
            evidence_refs.append(EvidenceRef(source_id=evidence_source, observed_at=datetime.now(timezone.utc)))
        provenance = EdgeProvenance(
            origin=EdgeOrigin(origin),
            role=EdgeRole(role),
            evidence_refs=evidence_refs,
            derived_from=derived_from or [],
            promotion_status="unpromoted" if origin != EdgeOrigin.DISCOVERED.value else "promoted_by_evidence",
        )
        return self.engine.dag.add_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=EdgeType(edge_type),
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
            established_by="kosh_verify_api",
            provenance=provenance,
        )

    def add_hyperedge(
        self,
        source_ids: Iterable[str],
        target_id: str,
        edge_type: str,
        valid_from: datetime,
        confidence: float = 0.70,
        valid_until: Optional[datetime] = None,
        origin: str = EdgeOrigin.OBSERVED.value,
        role: str = EdgeRole.CAUSAL.value,
    ) -> str:
        provenance = EdgeProvenance(
            origin=EdgeOrigin(origin),
            role=EdgeRole(role),
            promotion_status="joint_causality",
        )
        return self.engine.dag.add_hyperedge(
            source_ids=set(source_ids),
            target_id=target_id,
            edge_type=EdgeType(edge_type),
            confidence=confidence,
            valid_from=valid_from,
            valid_until=valid_until,
            provenance=provenance,
        )

    # ------------------------------------------------------------------ verification API

    def verify(
        self,
        question: str,
        temporal_context: Optional[str] = None,
        depth: int = 4,
        dialectic: bool = True,
    ) -> VerifyReport:
        """Verify a question using the project-native temporal-causal engine."""
        if dialectic:
            dialectic_result = self.engine.dialectic_query(
                question,
                temporal_context=temporal_context,
                depth=depth,
                reopen_on_challenge=True,
            )
            base = dialectic_result.initial_result
            converged = dialectic_result.converged
            opposition = dialectic_result.opposition
            status = dialectic_result.final_status
            primary_answer = converged.primary_content
            convergent_summary = {
                "primary_fact_id": converged.primary_fact_id,
                "score": converged.score,
                "evidence_loss": converged.evidence_loss,
                "discarded_path_count": converged.discarded_path_count,
                "compression_candidates": [asdict(c) for c in converged.compression_candidates],
                "notes": converged.notes,
            }
            opposition_summary = {
                "status": opposition.status,
                "score": opposition.opposition_score,
                "findings": [asdict(f) for f in opposition.findings],
                "reopened_fact_ids": opposition.reopened_fact_ids,
                "falsification_questions": opposition.falsification_questions,
            }
        else:
            base = self.engine.query(question, temporal_context=temporal_context, depth=depth)
            status = base.stability.status
            primary_answer = self._best_fact_content(base.bundle)
            convergent_summary = {}
            opposition_summary = {}

        facts = self._bundle_facts(base.bundle)
        paths = self._bundle_paths(base.bundle)
        contradictions = self._contradictions_for_bundle(base.bundle)
        inferred = self._inferred_not_discovered(base.bundle)
        missing_evidence = list(opposition_summary.get("falsification_questions", []))
        missing_evidence.extend(self._missing_evidence_facts(base.bundle))
        discarded_or_reopened = list(opposition_summary.get("reopened_fact_ids", []))

        return VerifyReport(
            question=question,
            status=status,
            primary_answer=primary_answer,
            stability_score=base.stability.score,
            stability_status=base.stability.status,
            abstain=base.stability.abstain,
            temporal_context=temporal_context,
            convergent_summary=convergent_summary,
            opposition_summary=opposition_summary,
            facts=facts,
            paths=paths,
            contradictions=contradictions,
            inferred_not_discovered=inferred,
            missing_evidence=missing_evidence,
            discarded_or_reopened_facts=discarded_or_reopened,
        )

    def explain_provenance(self, report: VerifyReport) -> str:
        """Return a short human-readable provenance explanation."""
        if report.abstain:
            return "No grounded evidence was retrieved. Kosh Verify abstained instead of inventing certainty."
        lines = [f"Status: {report.status}", f"Stability: {report.stability_status} ({report.stability_score})"]
        if report.inferred_not_discovered:
            lines.append(f"Inferred-not-discovered edges: {len(report.inferred_not_discovered)}")
        if report.contradictions:
            lines.append(f"Contradictions surfaced: {len(report.contradictions)}")
        if report.missing_evidence:
            lines.append("Missing evidence questions:")
            lines.extend(f"- {q}" for q in report.missing_evidence[:5])
        return "\n".join(lines)

    def export_report(self, report: VerifyReport, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.to_json(indent=2), encoding="utf-8")
        return out

    # ------------------------------------------------------------------ projection helpers

    def _best_fact_content(self, bundle: FiberBundle) -> Optional[str]:
        if not bundle.fibers:
            return None
        fid, fiber = max(bundle.fibers.items(), key=lambda item: (item[1].max_confidence, item[1].degeneracy))
        return fiber.fact.content

    def _fact_to_dict(self, fact: TemporalFact) -> Dict[str, Any]:
        return {
            "id": fact.id,
            "content": fact.content,
            "valid_from": fact.valid_from.isoformat(),
            "valid_until": fact.valid_until.isoformat() if fact.valid_until else None,
            "documented_at": fact.documented_at.isoformat(),
            "confidence": fact.confidence,
            "source": fact.source,
        }

    def _bundle_facts(self, bundle: FiberBundle) -> List[Dict[str, Any]]:
        return [self._fact_to_dict(fiber.fact) for fiber in bundle.fibers.values()]

    def _bundle_paths(self, bundle: FiberBundle) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for target_id, fiber in bundle.fibers.items():
            for path in fiber.paths:
                rows.append({
                    "target_id": target_id,
                    "confidence_product": path.confidence_product,
                    "temporal_consistency": path.temporal_consistency,
                    "edges": [
                        {
                            "id": e.id,
                            "source_id": e.source_id,
                            "target_id": e.target_id,
                            "edge_type": e.edge_type.value,
                            "confidence": e.confidence,
                            "origin": e.provenance.origin.value,
                            "role": e.provenance.role.value,
                            "promotion_status": e.provenance.promotion_status,
                            "derived_from": list(e.provenance.derived_from),
                            "reinforcement_count": e.provenance.reinforcement.count if e.provenance.reinforcement else 0,
                        }
                        for e in path.edges
                    ],
                })
        return rows

    def _missing_evidence_facts(self, bundle: FiberBundle) -> List[str]:
        out: List[str] = []
        for fiber in bundle.fibers.values():
            content = fiber.fact.content.lower()
            if "missing evidence" in content or "missing" in content or "evidence gap" in content:
                out.append(fiber.fact.content)
        return out

    def _contradictions_for_bundle(self, bundle: FiberBundle) -> List[Dict[str, Any]]:
        ids = list(bundle.fibers.keys())
        out: List[Dict[str, Any]] = []
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if self.engine.dag.has_contradiction(a, b):
                    out.append({"fact_a": a, "fact_b": b})
        return out

    def _inferred_not_discovered(self, bundle: FiberBundle) -> List[Dict[str, Any]]:
        seen = set()
        out: List[Dict[str, Any]] = []
        for path in self._bundle_paths(bundle):
            for edge in path["edges"]:
                if edge["id"] in seen:
                    continue
                seen.add(edge["id"])
                if edge["origin"] in {EdgeOrigin.INFERRED.value, EdgeOrigin.REINFORCED.value, EdgeOrigin.HYPOTHETICAL.value}:
                    out.append(edge)
        return out


def seed_incident_cartridge(root: str | Path) -> KoshVerify:
    """Create a small Kosh Verify demo cartridge grounded in Vaibhav's project thesis.

    Scenario: a checkout outage where normal retrieval would collapse to one
    answer, while Kosh Verify preserves mechanism, alternatives, contradiction,
    missing evidence, and inferred/compressed shortcut labels.
    """
    kv = KoshVerify(root)
    t0 = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 5, 1, 12, 10, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 1, 12, 20, tzinfo=timezone.utc)
    t3 = datetime(2026, 5, 1, 12, 40, tzinfo=timezone.utc)
    t4 = datetime(2026, 5, 1, 13, 10, tzinfo=timezone.utc)

    deploy = kv.add_fact("Checkout service deployment v4.2 started before the customer-impact window.", t0, confidence=0.93, source="deployment_note")
    leak = kv.add_fact("After deployment v4.2, checkout pods showed a memory leak and rising heap usage.", t1, confidence=0.87, source="monitoring")
    saturation = kv.add_fact("Memory pressure saturated checkout workers and increased request latency.", t2, confidence=0.84, source="metrics")
    outage = kv.add_fact("Checkout fail incident: checkout failed for customers during the incident window.", t3, confidence=0.95, source="incident_timeline")
    traffic = kv.add_fact("Traffic spike may also have contributed to checkout saturation.", t1, confidence=0.62, source="load_balancer")
    denial = kv.add_fact("Contradictory evidence: a status update claimed there was no memory pressure during the checkout fail incident.", t2, confidence=0.58, source="status_update")
    missing = kv.add_fact("Missing evidence for checkout fail: heap profile between 12:30 and 13:00 UTC is missing from the evidence pack.", t4, confidence=0.78, source="postmortem_gap")

    e1 = kv.add_edge(deploy, leak, "CAUSES", t1, 0.82, origin="OBSERVED", role="MECHANISTIC", evidence_source="deployment+metrics")
    e2 = kv.add_edge(leak, saturation, "CAUSES", t2, 0.80, origin="OBSERVED", role="MECHANISTIC", evidence_source="metrics")
    e3 = kv.add_edge(saturation, outage, "CAUSES", t3, 0.78, origin="OBSERVED", role="MECHANISTIC", evidence_source="incident_timeline")
    kv.add_edge(traffic, saturation, "ENABLES", t2, 0.55, origin="HYPOTHETICAL", role="PREDICTIVE", evidence_source="load_balancer")
    kv.add_edge(denial, leak, "CONTRADICTS", t2, 0.66, origin="OBSERVED", role="MECHANISTIC", evidence_source="status_update")
    kv.add_edge(missing, outage, "ENABLES", t4, 0.40, origin="HYPOTHETICAL", role="PREDICTIVE", evidence_source="postmortem_gap")
    kv.add_edge(
        deploy,
        outage,
        "INFERS",
        t3,
        0.46,
        origin="INFERRED",
        role="COMPRESSED",
        derived_from=[e1, e2, e3],
    )
    kv.add_hyperedge({deploy, traffic}, outage, "CAUSES", t3, 0.60, origin="HYPOTHETICAL", role="CAUSAL")
    return kv
