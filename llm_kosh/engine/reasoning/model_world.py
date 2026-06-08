from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class ModelWorldNodeKind(str, Enum):
    TEMPORAL_FACT = "TEMPORAL_FACT"
    CONCEPT = "CONCEPT"
    HYPOTHESIS = "HYPOTHESIS"
    CONTRADICTION = "CONTRADICTION"
    ABSTRACTION = "ABSTRACTION"
    EXPERIMENT = "EXPERIMENT"
    IMPLEMENTATION = "IMPLEMENTATION"
    OUTCOME = "OUTCOME"
    FAILURE = "FAILURE"
    DECISION = "DECISION"
    MODEL = "MODEL"
    OPPOSITION = "OPPOSITION"
    REINFORCEMENT = "REINFORCEMENT"


@dataclass
class ModelWorldNode:
    id: str
    kind: ModelWorldNodeKind
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class ModelWorldLink:
    source_id: str
    target_id: str
    relation: str
    confidence: float = 0.5
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class ModelWorldStats:
    node_count: int
    link_count: int
    kind_counts: Dict[str, int]
    partition_count: int
    target_nodes_per_partition: int


class ModelWorld:
    """
    Finite, inspectable model-world registry.

    This is not a graph database replacement. It is a schema and runtime hook
    for running dialectical loops over a bounded universe of typed cognitive
    objects. It can scale toward a million-node model world by partitioning and
    summarising rather than turning everything into flat vector chunks.
    """

    def __init__(self, target_nodes_per_partition: int = 50_000) -> None:
        self.target_nodes_per_partition = target_nodes_per_partition
        self.nodes: Dict[str, ModelWorldNode] = {}
        self.links: List[ModelWorldLink] = []

    def add_node(self, node: ModelWorldNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"duplicate model-world node: {node.id}")
        self.nodes[node.id] = node

    def add_link(self, link: ModelWorldLink) -> None:
        if link.source_id not in self.nodes:
            raise ValueError(f"link source not found: {link.source_id}")
        if link.target_id not in self.nodes:
            raise ValueError(f"link target not found: {link.target_id}")
        if not 0.0 <= link.confidence <= 1.0:
            raise ValueError("link confidence must be in [0, 1]")
        self.links.append(link)

    def record_dialectic_result(self, result) -> str:
        """Record a dialectic loop as an inspectable model-world node."""
        node_id = f"dialectic.{len(self.nodes) + 1:08d}"
        node = ModelWorldNode(
            id=node_id,
            kind=ModelWorldNodeKind.MODEL,
            content=f"Dialectic result for query: {result.query}",
            metadata={
                "final_status": result.final_status,
                "iterations": result.iterations,
                "primary_fact_id": result.synthesis.get("primary_fact_id"),
                "opposition_status": result.synthesis.get("opposition_status"),
                "evidence_loss": result.synthesis.get("evidence_loss"),
            },
        )
        self.add_node(node)
        return node_id

    def partition_plan(self, target_total_nodes: int = 1_000_000) -> Dict[str, int]:
        partitions = max(1, (target_total_nodes + self.target_nodes_per_partition - 1) // self.target_nodes_per_partition)
        return {
            "target_total_nodes": target_total_nodes,
            "target_nodes_per_partition": self.target_nodes_per_partition,
            "recommended_partitions": partitions,
        }

    def stats(self, target_total_nodes: Optional[int] = None) -> ModelWorldStats:
        kind_counts: Dict[str, int] = {}
        for node in self.nodes.values():
            kind_counts[node.kind.value] = kind_counts.get(node.kind.value, 0) + 1
        target = target_total_nodes or max(len(self.nodes), 1)
        partition_count = self.partition_plan(target)["recommended_partitions"]
        return ModelWorldStats(
            node_count=len(self.nodes),
            link_count=len(self.links),
            kind_counts=kind_counts,
            partition_count=partition_count,
            target_nodes_per_partition=self.target_nodes_per_partition,
        )
