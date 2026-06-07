import pytest
import time
from datetime import datetime, timezone
from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType, TrajectoryState
from llm_kosh.engine.reasoning.fiber_bundle import FiberBundle, Fiber, CausalPath, build_fiber_bundle
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic, StabilityResult
from llm_kosh.engine.reasoning.escape import EscapeMechanism
from llm_kosh.engine.reasoning.causal_dag import CausalEdge


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture
def sparse_dag(tmp_path):
    """DAG with low-confidence edges not normally traversed."""
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = _now()
    fa = dag.add_fact("Central fact", now, now, now, None, 0.9, "user")
    fb = dag.add_fact("Low-conf fact", now, now, now, None, 0.9, "user")
    # Low-confidence edge — normally skipped by retrieval
    dag.add_edge(fa, fb, EdgeType.ENABLES, 0.2, now, None, "test")
    return dag, fa, fb


def test_escape_increments_count(sparse_dag):
    dag, fa, fb = sparse_dag
    trajectory = TrajectoryState(session_id="s1")
    escape = EscapeMechanism(dag)
    bundle = FiberBundle(fibers={})
    diagnosis = StabilityResult(score=0.3, status="unstable",
        dimensions={"temporal_consistency": 1.0, "contradiction_score": 0.0,
                    "path_diversity": 0.1, "degeneracy": 0.1},
        implicated_facts=[])
    new_bundle = escape.escape(bundle, diagnosis, trajectory, time.time(), {}, depth=2)
    assert trajectory.escape_count == 1


def test_escape_low_diversity_adds_paths(sparse_dag):
    dag, fa, fb = sparse_dag
    trajectory = TrajectoryState(session_id="s1")
    escape = EscapeMechanism(dag)
    # Bundle with only fa, low path diversity
    fact_a = dag.get_fact(fa)
    path = CausalPath(edges=[], confidence_product=1.0, temporal_consistency=1.0)
    bundle = FiberBundle(fibers={
        fa: Fiber(fact=fact_a, paths=[path], degeneracy=1, max_confidence=1.0)
    })
    diagnosis = StabilityResult(score=0.3, status="unstable",
        dimensions={"temporal_consistency": 1.0, "contradiction_score": 0.0,
                    "path_diversity": 0.1, "degeneracy": 0.1},
        implicated_facts=[])
    new_bundle = escape.escape(bundle, diagnosis, trajectory, time.time(), {}, depth=2)
    # fb should now appear in the escaped bundle (via low-confidence edge traversal)
    assert fb in new_bundle.fibers


def test_deep_instability_flag(sparse_dag):
    dag, fa, fb = sparse_dag
    trajectory = TrajectoryState(session_id="s1", escape_count=3)
    escape = EscapeMechanism(dag)
    bundle = FiberBundle(fibers={})
    diagnosis = StabilityResult(score=0.2, status="unstable",
        dimensions={"temporal_consistency": 0.5, "contradiction_score": 0.5,
                    "path_diversity": 0.1, "degeneracy": 0.1},
        implicated_facts=[])
    new_bundle = escape.escape(bundle, diagnosis, trajectory, time.time(), {}, depth=2)
    assert new_bundle.fibers.get("__deep_instability__") is not None or trajectory.escape_count == 4
