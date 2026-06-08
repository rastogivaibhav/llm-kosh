from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from llm_kosh.engine.reasoning.causal_dag import CausalEdge, EdgeType, HyperEdge, TemporalFact
from llm_kosh.verify.api import KoshVerify, VerifyReport


@dataclass
class ServiceNowRecord:
    """Small ServiceNow-shaped record used by Kosh Verify demos/tests.

    This is deliberately schema-light.  Real ServiceNow connectors can map
    incidents, changes, problems, CIs, alerts and work notes into this form.
    """

    table: str
    sys_id: str
    number: str
    short_description: str
    opened_at: Optional[str] = None
    updated_at: Optional[str] = None
    resolved_at: Optional[str] = None
    state: str = ""
    priority: str = ""
    cmdb_ci: str = ""
    assignment_group: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)
    work_notes: List[str] = field(default_factory=list)

    def event_time(self) -> datetime:
        """Best available temporal anchor for the record.

        ServiceNow data often has opened_at/updated_at/resolved_at.  When a
        record lacks explicit time, we use ingestion time but keep the source
        table/field provenance in the fact content so callers can see that the
        temporal evidence was weak.
        """
        for value in (self.opened_at, self.updated_at, self.resolved_at):
            if value:
                return _parse_dt(value)
        return datetime.now(timezone.utc)

    def to_content(self) -> str:
        notes = " | notes: " + " ; ".join(self.work_notes) if self.work_notes else ""
        fields = " | fields: " + json.dumps(self.fields, sort_keys=True) if self.fields else ""
        return (
            f"ServiceNow {self.table} {self.number}: {self.short_description}. "
            f"state={self.state}; priority={self.priority}; ci={self.cmdb_ci}; "
            f"assignment_group={self.assignment_group}; sys_id={self.sys_id}."
            f"{fields}{notes}"
        )


@dataclass
class MemoryTransferPacket:
    """Portable memory packet transferred between Kosh agents."""

    source_agent: str
    target_agent: str
    created_at: str
    facts: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    hyperedges: List[Dict[str, Any]]
    transfer_scope: str = "selected"

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, **kwargs)

    @classmethod
    def from_json(cls, text: str) -> "MemoryTransferPacket":
        return cls(**json.loads(text))


@dataclass
class AgentRunResult:
    agent_name: str
    report: VerifyReport
    transferred_fact_count: int = 0
    transferred_edge_count: int = 0


class KoshAgent:
    """Independent Kosh Verify agent with its own local cartridge.

    The agent has no LLM dependency.  It can ingest structured ServiceNow-like
    records, verify questions against its private memory, and share selected
    memory with another KoshAgent through a provenance-preserving transfer
    packet.
    """

    def __init__(self, name: str, role: str, cartridge_root: str | Path) -> None:
        self.name = name
        self.role = role
        self.root = Path(cartridge_root)
        self.kv = KoshVerify(self.root)
        self._external_to_fact: Dict[str, str] = {}

    # ------------------------------------------------------------------ ServiceNow ingest

    def ingest_servicenow_records(self, records: Iterable[ServiceNowRecord]) -> Dict[str, str]:
        """Ingest ServiceNow-shaped records as temporal facts and causal/provenance edges.

        Returns mapping from ServiceNow sys_id/number to Kosh fact_id.
        """
        records = list(records)
        local_map: Dict[str, str] = {}

        for rec in records:
            t = rec.event_time()
            content = rec.to_content()
            if not rec.opened_at and not rec.updated_at and not rec.resolved_at:
                content += " Temporal evidence: UNKNOWN_EXACT_TIME; ingestion time used only as weak ordering evidence."
            fact_id = self.kv.add_fact(
                content=content,
                valid_from=t,
                documented_at=t,
                confidence=float(rec.fields.get("confidence", 0.82)),
                source=f"servicenow:{rec.table}:{rec.number}",
            )
            local_map[rec.sys_id] = fact_id
            local_map[rec.number] = fact_id
            self._external_to_fact[rec.sys_id] = fact_id
            self._external_to_fact[rec.number] = fact_id

        # Create deterministic ServiceNow relationship edges within the agent's
        # memory.  This is connector logic, not LLM inference.
        for rec in records:
            source_fact = local_map.get(rec.sys_id)
            if not source_fact:
                continue
            t = rec.event_time()
            caused_by = _first_present(rec.fields, ["caused_by_change", "caused_by", "change_request"])
            if caused_by and caused_by in local_map:
                # Change/problem is a likely causal predecessor of an incident.
                self.kv.add_edge(
                    local_map[caused_by], source_fact, "CAUSES", t, confidence=0.78,
                    origin="OBSERVED", role="MECHANISTIC", evidence_source=f"servicenow:{rec.number}:caused_by",
                )
            parent = rec.fields.get("parent_incident") or rec.fields.get("parent")
            if parent and parent in local_map:
                self.kv.add_edge(
                    source_fact, local_map[parent], "ENABLES", t, confidence=0.68,
                    origin="OBSERVED", role="MECHANISTIC", evidence_source=f"servicenow:{rec.number}:parent",
                )
            related_problem = rec.fields.get("problem_id") or rec.fields.get("problem")
            if related_problem and related_problem in local_map:
                self.kv.add_edge(
                    local_map[related_problem], source_fact, "CAUSES", t, confidence=0.72,
                    origin="OBSERVED", role="MECHANISTIC", evidence_source=f"servicenow:{rec.number}:problem",
                )
            contradicts = rec.fields.get("contradicts")
            if contradicts and contradicts in local_map:
                self.kv.add_edge(
                    source_fact, local_map[contradicts], "CONTRADICTS", t, confidence=0.66,
                    origin="OBSERVED", role="MECHANISTIC", evidence_source=f"servicenow:{rec.number}:contradicts",
                )

        return dict(local_map)

    # ------------------------------------------------------------------ operate

    def verify(self, question: str, temporal_context: Optional[str] = None, dialectic: bool = True) -> AgentRunResult:
        report = self.kv.verify(question, temporal_context=temporal_context, dialectic=dialectic, depth=5)
        return AgentRunResult(agent_name=self.name, report=report)

    # ------------------------------------------------------------------ memory transfer

    def export_memory_packet(
        self,
        target_agent: str,
        query: Optional[str] = None,
        temporal_context: Optional[str] = None,
        max_facts: Optional[int] = None,
    ) -> MemoryTransferPacket:
        """Export either all memory or the bundle retrieved for a query."""
        fact_ids: List[str]
        if query:
            report = self.kv.verify(query, temporal_context=temporal_context, dialectic=True, depth=5)
            fact_ids = [f["id"] for f in report.facts]
        else:
            fact_ids = list(self.kv.engine.dag.nodes.keys())

        if max_facts is not None:
            fact_ids = fact_ids[:max_facts]

        fact_set = set(fact_ids)
        facts = [_fact_to_transfer(self.kv.engine.dag.nodes[fid]) for fid in fact_ids if fid in self.kv.engine.dag.nodes]
        edges: List[Dict[str, Any]] = []
        for src_id, edge_list in self.kv.engine.dag.edges.items():
            for edge in edge_list:
                if edge.source_id in fact_set and edge.target_id in fact_set:
                    edges.append(_edge_to_transfer(edge))

        hyperedges: List[Dict[str, Any]] = []
        for he in self.kv.engine.dag.hyperedges:
            if he.target_id in fact_set and set(he.source_ids).issubset(fact_set):
                hyperedges.append(_hyperedge_to_transfer(he))

        return MemoryTransferPacket(
            source_agent=self.name,
            target_agent=target_agent,
            created_at=datetime.now(timezone.utc).isoformat(),
            facts=facts,
            edges=edges,
            hyperedges=hyperedges,
            transfer_scope="query" if query else "all",
        )

    def import_memory_packet(self, packet: MemoryTransferPacket) -> Tuple[int, int, int]:
        """Import packet into this agent's cartridge, preserving transfer provenance.

        Returns (facts_imported, edges_imported, hyperedges_imported).
        """
        old_to_new: Dict[str, str] = {}
        facts_imported = 0
        for fact in packet.facts:
            content = (
                f"Transferred from agent {packet.source_agent}: "
                f"{fact['content']} [original_fact_id={fact['id']}]"
            )
            new_id = self.kv.add_fact(
                content=content,
                valid_from=_parse_dt(fact["valid_from"]),
                valid_until=_parse_optional_dt(fact.get("valid_until")),
                documented_at=_parse_dt(fact["documented_at"]),
                confidence=min(float(fact.get("confidence", 0.75)), 0.88),
                source=f"agent_transfer:{packet.source_agent}:{fact.get('source', '')}",
            )
            old_to_new[fact["id"]] = new_id
            facts_imported += 1

        edges_imported = 0
        for edge in packet.edges:
            src = old_to_new.get(edge["source_id"])
            dst = old_to_new.get(edge["target_id"])
            if not src or not dst:
                continue
            self.kv.add_edge(
                src, dst, edge["edge_type"], _parse_dt(edge["valid_from"]),
                confidence=min(float(edge.get("confidence", 0.65)), 0.82),
                valid_until=_parse_optional_dt(edge.get("valid_until")),
                origin="OBSERVED" if edge.get("origin") == "OBSERVED" else "INFERRED",
                role=edge.get("role", "MECHANISTIC"),
                evidence_source=f"agent_transfer:{packet.source_agent}:{edge.get('id')}",
                derived_from=[edge.get("id", "")],
            )
            edges_imported += 1

        hyperedges_imported = 0
        for he in packet.hyperedges:
            srcs = {old_to_new[sid] for sid in he.get("source_ids", []) if sid in old_to_new}
            dst = old_to_new.get(he.get("target_id"))
            if not srcs or not dst or len(srcs) != len(he.get("source_ids", [])):
                continue
            self.kv.add_hyperedge(
                srcs, dst, he["edge_type"], _parse_dt(he["valid_from"]),
                confidence=min(float(he.get("confidence", 0.60)), 0.78),
                valid_until=_parse_optional_dt(he.get("valid_until")),
                origin="OBSERVED" if he.get("origin") == "OBSERVED" else "INFERRED",
                role=he.get("role", "CAUSAL"),
            )
            hyperedges_imported += 1

        return facts_imported, edges_imported, hyperedges_imported


class MultiAgentMemoryBus:
    """Tiny in-process memory bus for testing multi-agent transfer."""

    def __init__(self) -> None:
        self.packets: List[MemoryTransferPacket] = []

    def transfer(self, source: KoshAgent, target: KoshAgent, query: Optional[str] = None) -> Tuple[int, int, int]:
        packet = source.export_memory_packet(target_agent=target.name, query=query)
        self.packets.append(packet)
        return target.import_memory_packet(packet)


def build_synthetic_servicenow_dataset() -> List[ServiceNowRecord]:
    """Synthetic ServiceNow incident/change/problem dataset for deterministic tests.

    The dataset is shaped like ServiceNow ITSM data without including private or
    customer data.  It is designed to test independent agents and shared memory.
    """
    return [
        ServiceNowRecord(
            table="change_request",
            sys_id="chg_9001",
            number="CHG9001",
            short_description="Checkout deployment v4.2 changed payment timeout and cache settings",
            opened_at="2026-05-01T11:55:00+00:00",
            updated_at="2026-05-01T12:05:00+00:00",
            state="implemented",
            priority="3",
            cmdb_ci="checkout-service",
            assignment_group="payments-platform",
            fields={"risk": "medium", "confidence": 0.88},
            work_notes=["Implementation completed shortly before checkout incidents started."],
        ),
        ServiceNowRecord(
            table="incident",
            sys_id="inc_1001",
            number="INC1001",
            short_description="Checkout outage: customers cannot complete payment",
            opened_at="2026-05-01T12:22:00+00:00",
            updated_at="2026-05-01T12:30:00+00:00",
            state="major_incident",
            priority="1",
            cmdb_ci="checkout-service",
            assignment_group="service-desk",
            fields={"caused_by_change": "chg_9001", "problem_id": "prb_2001", "confidence": 0.94},
            work_notes=["Failures started after CHG9001 and affected payment completion."],
        ),
        ServiceNowRecord(
            table="incident",
            sys_id="inc_1002",
            number="INC1002",
            short_description="Checkout latency and worker saturation after deployment",
            opened_at="2026-05-01T12:24:00+00:00",
            updated_at="2026-05-01T12:35:00+00:00",
            state="resolved",
            priority="2",
            cmdb_ci="checkout-service",
            assignment_group="platform-sre",
            fields={"parent_incident": "inc_1001", "caused_by_change": "chg_9001", "confidence": 0.86},
            work_notes=["Workers saturated after the checkout deployment; rollback reduced latency."],
        ),
        ServiceNowRecord(
            table="problem",
            sys_id="prb_2001",
            number="PRB2001",
            short_description="Root cause review: checkout memory pressure increased after v4.2 config path",
            opened_at="2026-05-01T13:05:00+00:00",
            updated_at="2026-05-01T15:00:00+00:00",
            state="rca_complete",
            priority="2",
            cmdb_ci="checkout-service",
            assignment_group="platform-sre",
            fields={"root_cause": "configuration path in CHG9001", "confidence": 0.84},
            work_notes=["Heap profile still missing for 12:30 to 13:00, so final causal certainty is bounded."],
        ),
        ServiceNowRecord(
            table="incident",
            sys_id="inc_1003",
            number="INC1003",
            short_description="Status update says checkout issue not related to memory pressure",
            opened_at="2026-05-01T12:27:00+00:00",
            updated_at="2026-05-01T12:31:00+00:00",
            state="closed",
            priority="3",
            cmdb_ci="checkout-service",
            assignment_group="service-desk",
            fields={"contradicts": "prb_2001", "confidence": 0.62},
            work_notes=["Early status update denied memory pressure; later RCA suggested memory pressure."],
        ),
    ]


def split_servicenow_dataset_by_agent(records: List[ServiceNowRecord]) -> Dict[str, List[ServiceNowRecord]]:
    return {
        "change_agent": [r for r in records if r.table == "change_request"],
        "incident_agent": [r for r in records if r.table == "incident"],
        "problem_agent": [r for r in records if r.table == "problem"],
    }


# ---------------------------------------------------------------------- helpers


def _parse_dt(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_optional_dt(value: Optional[str]) -> Optional[datetime]:
    return _parse_dt(value) if value else None


def _first_present(data: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return None


def _fact_to_transfer(fact: TemporalFact) -> Dict[str, Any]:
    return {
        "id": fact.id,
        "content": fact.content,
        "ingested_at": fact.ingested_at.isoformat(),
        "documented_at": fact.documented_at.isoformat(),
        "valid_from": fact.valid_from.isoformat(),
        "valid_until": fact.valid_until.isoformat() if fact.valid_until else None,
        "confidence": fact.confidence,
        "source": fact.source,
    }


def _edge_to_transfer(edge: CausalEdge) -> Dict[str, Any]:
    return {
        "id": edge.id,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "edge_type": edge.edge_type.value,
        "confidence": edge.confidence,
        "valid_from": edge.valid_from.isoformat(),
        "valid_until": edge.valid_until.isoformat() if edge.valid_until else None,
        "origin": edge.provenance.origin.value,
        "role": edge.provenance.role.value,
        "promotion_status": edge.provenance.promotion_status,
    }


def _hyperedge_to_transfer(he: HyperEdge) -> Dict[str, Any]:
    return {
        "id": he.id,
        "source_ids": list(he.source_ids),
        "target_id": he.target_id,
        "edge_type": he.edge_type.value,
        "confidence": he.confidence,
        "valid_from": he.valid_from.isoformat(),
        "valid_until": he.valid_until.isoformat() if he.valid_until else None,
        "origin": he.provenance.origin.value,
        "role": he.provenance.role.value,
        "promotion_status": he.provenance.promotion_status,
    }
