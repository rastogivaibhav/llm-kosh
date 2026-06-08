from __future__ import annotations

"""Framework-style multi-agent memory adapters for Kosh Verify.

This module models the Silicon-Valley product wedge more directly than the
ServiceNow-only demo.  It does not import LangGraph, CrewAI or Salesforce SDKs;
instead it gives project-native adapter shapes that can be wrapped by those
frameworks later.  The tests prove the memory behaviour we need:

- each framework-style agent has its own local Kosh cartridge;
- each agent can perform independent work on ServiceNow / CRM-shaped data;
- agents can publish provenance-preserving memory packets into a shared
  transaction/user memory pool;
- another agent can pull from the pool and reason over transferred memories;
- shared memory preserves scope (transaction vs user) and transfer provenance.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from llm_kosh.verify.api import KoshVerify, VerifyReport
from llm_kosh.verify.multi_agent import KoshAgent, MemoryTransferPacket, ServiceNowRecord


@dataclass
class AgentWorkItem:
    """Framework-neutral unit of work for an agent.

    A real LangGraph node, CrewAI task, Salesforce/Agentforce action, or any
    other agent framework can translate its state/task object into this shape.
    """

    work_id: str
    transaction_id: str
    user_id: str
    title: str
    description: str
    source_system: str
    event_time: Optional[str] = None
    records: List[ServiceNowRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def observed_at(self) -> datetime:
        if self.event_time:
            return _parse_dt(self.event_time)
        return datetime.now(timezone.utc)


@dataclass
class AgentWorkResult:
    """Result returned after a framework-style agent performs local work."""

    agent_name: str
    framework: str
    work_id: str
    transaction_id: str
    user_id: str
    local_report: VerifyReport
    published_to_pool: bool = False
    pulled_from_pool: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["local_report"] = self.local_report.to_dict()
        return data


@dataclass
class SharedPoolReceipt:
    """Audit receipt for shared memory publication/pull."""

    action: str
    pool_name: str
    scope_type: str
    scope_id: str
    agent_name: str
    framework: str
    created_at: str
    fact_count: int
    edge_count: int
    hyperedge_count: int
    transfer_id: str


class KoshSharedMemoryPool:
    """Shared memory pool for a transaction or a user.

    The pool is implemented as a normal KoshVerify cartridge, which keeps the
    system simple and testable.  It is intentionally not a global vector store:
    each pool has an explicit scope and every import/export is audited.
    """

    def __init__(self, name: str, scope_type: str, scope_id: str, root: str | Path) -> None:
        if scope_type not in {"transaction", "user"}:
            raise ValueError("scope_type must be 'transaction' or 'user'")
        self.name = name
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.root = Path(root)
        self.kv = KoshVerify(self.root)
        self.receipts: List[SharedPoolReceipt] = []

    def publish_from_agent(
        self,
        agent: "FrameworkKoshAgent",
        query: Optional[str] = None,
        max_facts: Optional[int] = None,
    ) -> SharedPoolReceipt:
        packet = agent.local_agent.export_memory_packet(
            target_agent=self.name,
            query=query,
            max_facts=max_facts,
        )
        counts = self._import_packet(packet, publishing_agent=agent)
        receipt = SharedPoolReceipt(
            action="publish",
            pool_name=self.name,
            scope_type=self.scope_type,
            scope_id=self.scope_id,
            agent_name=agent.name,
            framework=agent.framework,
            created_at=datetime.now(timezone.utc).isoformat(),
            fact_count=counts[0],
            edge_count=counts[1],
            hyperedge_count=counts[2],
            transfer_id=f"{agent.name}->{self.name}:{len(self.receipts)+1}",
        )
        self.receipts.append(receipt)
        return receipt

    def pull_into_agent(
        self,
        agent: "FrameworkKoshAgent",
        query: Optional[str] = None,
        max_facts: Optional[int] = None,
    ) -> SharedPoolReceipt:
        packet = self.export_memory_packet(
            target_agent=agent.name,
            query=query,
            max_facts=max_facts,
        )
        counts = agent.local_agent.import_memory_packet(packet)
        receipt = SharedPoolReceipt(
            action="pull",
            pool_name=self.name,
            scope_type=self.scope_type,
            scope_id=self.scope_id,
            agent_name=agent.name,
            framework=agent.framework,
            created_at=datetime.now(timezone.utc).isoformat(),
            fact_count=counts[0],
            edge_count=counts[1],
            hyperedge_count=counts[2],
            transfer_id=f"{self.name}->{agent.name}:{len(self.receipts)+1}",
        )
        self.receipts.append(receipt)
        return receipt

    def verify(self, question: str, temporal_context: Optional[str] = None, dialectic: bool = True) -> VerifyReport:
        return self.kv.verify(question, temporal_context=temporal_context, dialectic=dialectic, depth=5)

    def export_memory_packet(
        self,
        target_agent: str,
        query: Optional[str] = None,
        max_facts: Optional[int] = None,
    ) -> MemoryTransferPacket:
        fact_ids: List[str]
        if query:
            report = self.kv.verify(query, dialectic=True, depth=5)
            fact_ids = [f["id"] for f in report.facts]
        else:
            fact_ids = list(self.kv.engine.dag.nodes.keys())
        if max_facts is not None:
            fact_ids = fact_ids[:max_facts]
        fact_set = set(fact_ids)
        facts = [_fact_to_transfer(self.kv.engine.dag.nodes[fid]) for fid in fact_ids if fid in self.kv.engine.dag.nodes]
        edges: List[Dict[str, Any]] = []
        for edge_list in self.kv.engine.dag.edges.values():
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
            transfer_scope=f"{self.scope_type}:{self.scope_id}",
        )

    def _import_packet(self, packet: MemoryTransferPacket, publishing_agent: "FrameworkKoshAgent") -> Tuple[int, int, int]:
        old_to_new: Dict[str, str] = {}
        facts_imported = 0
        for fact in packet.facts:
            content = (
                f"SharedMemory[{self.scope_type}:{self.scope_id}] from {publishing_agent.framework} "
                f"agent {publishing_agent.name}: {fact['content']} [original_fact_id={fact['id']}]"
            )
            new_id = self.kv.add_fact(
                content=content,
                valid_from=_parse_dt(fact["valid_from"]),
                valid_until=_parse_optional_dt(fact.get("valid_until")),
                documented_at=_parse_dt(fact["documented_at"]),
                confidence=min(float(fact.get("confidence", 0.75)), 0.90),
                source=(
                    f"shared_pool:{self.scope_type}:{self.scope_id}:"
                    f"{publishing_agent.framework}:{publishing_agent.name}:{fact.get('source', '')}"
                ),
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
                src,
                dst,
                edge["edge_type"],
                _parse_dt(edge["valid_from"]),
                confidence=min(float(edge.get("confidence", 0.65)), 0.84),
                valid_until=_parse_optional_dt(edge.get("valid_until")),
                origin="OBSERVED" if edge.get("origin") == "OBSERVED" else "INFERRED",
                role=edge.get("role", "MECHANISTIC"),
                evidence_source=f"shared_pool:{self.name}:{edge.get('id')}",
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
                srcs,
                dst,
                he["edge_type"],
                _parse_dt(he["valid_from"]),
                confidence=min(float(he.get("confidence", 0.60)), 0.80),
                valid_until=_parse_optional_dt(he.get("valid_until")),
                origin="OBSERVED" if he.get("origin") == "OBSERVED" else "INFERRED",
                role=he.get("role", "CAUSAL"),
            )
            hyperedges_imported += 1

        return facts_imported, edges_imported, hyperedges_imported

    def receipts_json(self, **kwargs: Any) -> str:
        return json.dumps([asdict(r) for r in self.receipts], ensure_ascii=False, **kwargs)


class FrameworkKoshAgent:
    """Base adapter for framework-style agents.

    Real integration point:
    - LangGraph node calls `run_work_item` inside a graph state transition.
    - CrewAI role/task calls `run_work_item` from a Crew task tool.
    - Salesforce/Agentforce action calls `run_work_item` during customer/case flow.
    """

    framework = "generic"

    def __init__(self, name: str, role: str, cartridge_root: str | Path) -> None:
        self.name = name
        self.role = role
        self.local_agent = KoshAgent(name=name, role=role, cartridge_root=cartridge_root)

    def run_work_item(self, item: AgentWorkItem, question: Optional[str] = None) -> AgentWorkResult:
        if item.records:
            self.local_agent.ingest_servicenow_records(item.records)
        self._ingest_work_summary(item)
        report = self.local_agent.verify(
            question or self.default_question(item),
            temporal_context=item.event_time,
            dialectic=True,
        ).report
        return AgentWorkResult(
            agent_name=self.name,
            framework=self.framework,
            work_id=item.work_id,
            transaction_id=item.transaction_id,
            user_id=item.user_id,
            local_report=report,
            notes=[f"{self.framework} agent ran local verification for {item.work_id}"],
        )

    def publish_to_pool(
        self,
        pool: KoshSharedMemoryPool,
        query: Optional[str] = None,
        max_facts: Optional[int] = None,
    ) -> SharedPoolReceipt:
        return pool.publish_from_agent(self, query=query, max_facts=max_facts)

    def pull_from_pool(
        self,
        pool: KoshSharedMemoryPool,
        query: Optional[str] = None,
        max_facts: Optional[int] = None,
    ) -> SharedPoolReceipt:
        return pool.pull_into_agent(self, query=query, max_facts=max_facts)

    def verify(self, question: str, temporal_context: Optional[str] = None) -> VerifyReport:
        return self.local_agent.verify(question, temporal_context=temporal_context, dialectic=True).report

    def default_question(self, item: AgentWorkItem) -> str:
        return f"What should be verified for {item.title}?"

    def _ingest_work_summary(self, item: AgentWorkItem) -> str:
        t = item.observed_at()
        content = (
            f"{self.framework} agent {self.name} worked on {item.work_id} for "
            f"transaction {item.transaction_id} and user {item.user_id}: {item.title}. "
            f"{item.description}. source_system={item.source_system}; metadata={json.dumps(item.metadata, sort_keys=True)}"
        )
        return self.local_agent.kv.add_fact(
            content=content,
            valid_from=t,
            documented_at=t,
            confidence=float(item.metadata.get("confidence", 0.80)),
            source=f"agent_work:{self.framework}:{self.name}:{item.work_id}",
        )


class LangGraphKoshAgent(FrameworkKoshAgent):
    framework = "langgraph"

    def default_question(self, item: AgentWorkItem) -> str:
        return f"What changed in the workflow state for transaction {item.transaction_id}?"


class CrewAIKoshAgent(FrameworkKoshAgent):
    framework = "crewai"

    def default_question(self, item: AgentWorkItem) -> str:
        return f"What root-cause or contradiction should the crew analyst preserve for {item.transaction_id}?"


class SalesforceKoshAgent(FrameworkKoshAgent):
    framework = "salesforce"

    def default_question(self, item: AgentWorkItem) -> str:
        return f"What customer or case memory should be preserved for user {item.user_id}?"


class AgentFrameworkMemoryOrchestrator:
    """Coordinates framework agents around shared transaction and user pools."""

    def __init__(self, root: str | Path, transaction_id: str, user_id: str) -> None:
        self.root = Path(root)
        self.transaction_id = transaction_id
        self.user_id = user_id
        self.transaction_pool = KoshSharedMemoryPool(
            name=f"transaction_pool_{transaction_id}",
            scope_type="transaction",
            scope_id=transaction_id,
            root=self.root / "shared" / "transactions" / transaction_id,
        )
        self.user_pool = KoshSharedMemoryPool(
            name=f"user_pool_{user_id}",
            scope_type="user",
            scope_id=user_id,
            root=self.root / "shared" / "users" / user_id,
        )
        self.agents: Dict[str, FrameworkKoshAgent] = {}

    def register(self, agent: FrameworkKoshAgent) -> FrameworkKoshAgent:
        self.agents[agent.name] = agent
        return agent

    def publish_all_to_transaction_pool(self, query: Optional[str] = None) -> List[SharedPoolReceipt]:
        return [agent.publish_to_pool(self.transaction_pool, query=query) for agent in self.agents.values()]

    def publish_agent_to_user_pool(self, agent_name: str, query: Optional[str] = None) -> SharedPoolReceipt:
        return self.agents[agent_name].publish_to_pool(self.user_pool, query=query)

    def pull_transaction_pool_into_all(self, query: Optional[str] = None) -> List[SharedPoolReceipt]:
        return [agent.pull_from_pool(self.transaction_pool, query=query) for agent in self.agents.values()]

    def verify_transaction(self, question: str, temporal_context: Optional[str] = None) -> VerifyReport:
        return self.transaction_pool.verify(question, temporal_context=temporal_context, dialectic=True)

    def verify_user(self, question: str, temporal_context: Optional[str] = None) -> VerifyReport:
        return self.user_pool.verify(question, temporal_context=temporal_context, dialectic=True)


# ---------------------------------------------------------------------- synthetic demo data


def build_cross_framework_servicenow_work_items() -> List[AgentWorkItem]:
    """Synthetic cross-framework scenario around one ServiceNow transaction/user."""
    transaction_id = "txn_checkout_2026_05_01"
    user_id = "customer_acme_001"
    return [
        AgentWorkItem(
            work_id="lg_state_001",
            transaction_id=transaction_id,
            user_id=user_id,
            title="LangGraph workflow triage for checkout outage",
            description="Workflow state connected CHG9001 to checkout incidents and preserved temporal order.",
            source_system="langgraph",
            event_time="2026-05-01T12:32:00+00:00",
            records=[
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
                    work_notes=["Workflow state observed deployment before incidents."],
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
                    fields={"caused_by_change": "chg_9001", "confidence": 0.94},
                    work_notes=["Failures started after CHG9001 and affected payment completion."],
                ),
            ],
            metadata={"confidence": 0.90, "state_key": "checkout.incident.triage"},
        ),
        AgentWorkItem(
            work_id="crew_rca_001",
            transaction_id=transaction_id,
            user_id=user_id,
            title="CrewAI analyst root-cause review",
            description="Analyst preserved memory pressure as likely RCA and noted missing heap profile evidence.",
            source_system="crewai",
            event_time="2026-05-01T13:10:00+00:00",
            records=[
                ServiceNowRecord(
                    table="problem",
                    sys_id="prb_2001",
                    number="PRB2001",
                    short_description="Root cause review: checkout memory pressure increased after v4.2 config path",
                    opened_at="2026-05-01T13:05:00+00:00",
                    updated_at="2026-05-01T15:00:00+00:00",
                    state="rca_in_progress",
                    priority="2",
                    cmdb_ci="checkout-service",
                    assignment_group="platform-sre",
                    fields={"root_cause": "configuration path in CHG9001", "confidence": 0.84},
                    work_notes=["Heap profile missing for 12:30 to 13:00, so certainty remains bounded."],
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
                    work_notes=["Early update denied memory pressure; later RCA suggested memory pressure."],
                ),
            ],
            metadata={"confidence": 0.86, "crew_role": "rca_analyst"},
        ),
        AgentWorkItem(
            work_id="sf_case_001",
            transaction_id=transaction_id,
            user_id=user_id,
            title="Salesforce customer case escalation",
            description="Customer Acme reported checkout payment failures during the same transaction window.",
            source_system="salesforce",
            event_time="2026-05-01T12:40:00+00:00",
            records=[
                ServiceNowRecord(
                    table="case",
                    sys_id="case_7001",
                    number="CASE7001",
                    short_description="Acme customer case: payment failure during checkout outage window",
                    opened_at="2026-05-01T12:40:00+00:00",
                    updated_at="2026-05-01T12:45:00+00:00",
                    state="escalated",
                    priority="1",
                    cmdb_ci="checkout-service",
                    assignment_group="customer-success",
                    fields={"customer": "Acme", "related_incident": "INC1001", "confidence": 0.89},
                    work_notes=["Customer impact aligns with checkout outage transaction."],
                ),
            ],
            metadata={"confidence": 0.87, "account": "Acme", "case_priority": "P1"},
        ),
    ]


def build_framework_orchestrator(root: str | Path, transaction_id: str, user_id: str) -> AgentFrameworkMemoryOrchestrator:
    orchestrator = AgentFrameworkMemoryOrchestrator(root=root, transaction_id=transaction_id, user_id=user_id)
    orchestrator.register(LangGraphKoshAgent("langgraph_state_agent", "workflow-state-triage", Path(root) / "agents" / "langgraph"))
    orchestrator.register(CrewAIKoshAgent("crewai_rca_agent", "role-based-rca", Path(root) / "agents" / "crewai"))
    orchestrator.register(SalesforceKoshAgent("salesforce_case_agent", "customer-case-memory", Path(root) / "agents" / "salesforce"))
    return orchestrator


# ---------------------------------------------------------------------- transfer helpers copied locally to avoid exposing internal bus as public API


def _parse_dt(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_optional_dt(value: Optional[str]) -> Optional[datetime]:
    return _parse_dt(value) if value else None


def _dt(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _fact_to_transfer(fact: Any) -> Dict[str, Any]:
    return {
        "id": fact.id,
        "content": fact.content,
        "ingested_at": _dt(fact.ingested_at),
        "documented_at": _dt(fact.documented_at),
        "valid_from": _dt(fact.valid_from),
        "valid_until": _dt(fact.valid_until) if fact.valid_until else None,
        "confidence": fact.confidence,
        "source": fact.source,
    }


def _edge_to_transfer(edge: Any) -> Dict[str, Any]:
    provenance = getattr(edge, "provenance", None)
    return {
        "id": edge.id,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "edge_type": edge.edge_type.value if hasattr(edge.edge_type, "value") else str(edge.edge_type),
        "confidence": edge.confidence,
        "valid_from": _dt(edge.valid_from),
        "valid_until": _dt(edge.valid_until) if edge.valid_until else None,
        "origin": getattr(getattr(provenance, "origin", None), "value", str(getattr(provenance, "origin", "INFERRED"))),
        "role": getattr(getattr(provenance, "role", None), "value", str(getattr(provenance, "role", "MECHANISTIC"))),
    }


def _hyperedge_to_transfer(he: Any) -> Dict[str, Any]:
    provenance = getattr(he, "provenance", None)
    return {
        "id": he.id,
        "source_ids": sorted(he.source_ids),
        "target_id": he.target_id,
        "edge_type": he.edge_type.value if hasattr(he.edge_type, "value") else str(he.edge_type),
        "confidence": he.confidence,
        "valid_from": _dt(he.valid_from),
        "valid_until": _dt(he.valid_until) if he.valid_until else None,
        "origin": getattr(getattr(provenance, "origin", None), "value", str(getattr(provenance, "origin", "INFERRED"))),
        "role": getattr(getattr(provenance, "role", None), "value", str(getattr(provenance, "role", "CAUSAL"))),
    }
