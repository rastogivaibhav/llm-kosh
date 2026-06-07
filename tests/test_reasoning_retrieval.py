import pytest
import math
from llm_kosh.engine.reasoning.causal_retrieval import resonance_profile, harmonic_match, _dct


def test_dct_length():
    x = [1.0, 2.0, 3.0, 4.0]
    result = _dct(x)
    assert len(result) == 4


def test_dct_dc_component():
    # DC component (k=0) should be 2 * sum(x)
    x = [1.0, 1.0, 1.0, 1.0]
    result = _dct(x)
    assert abs(result[0] - 2 * sum(x)) < 1e-6


def test_resonance_profile_structure():
    profile = resonance_profile("apple orange fruit healthy eating")
    assert "low" in profile
    assert "mid" in profile
    assert "high" in profile
    assert isinstance(profile["low"], list)
    assert len(profile["low"]) > 0


def test_resonance_profile_empty_text():
    profile = resonance_profile("")
    assert "low" in profile
    # Should not raise, should return zero-filled profile


def test_harmonic_match_identical():
    profile = resonance_profile("machine learning neural networks")
    score = harmonic_match(profile, profile)
    assert score > 0.9, f"Identical profiles should score near 1.0, got {score}"


def test_harmonic_match_different():
    p1 = resonance_profile("quantum physics particles")
    p2 = resonance_profile("baking bread flour yeast")
    score = harmonic_match(p1, p2)
    assert score < 0.5, f"Unrelated profiles should score low, got {score}"


def test_harmonic_match_partial():
    p1 = resonance_profile("machine learning neural networks deep")
    p2 = resonance_profile("machine learning algorithms")
    score = harmonic_match(p1, p2)
    assert 0.2 < score < 1.0, f"Partial overlap should score between 0.2 and 1.0, got {score}"


from datetime import datetime, timezone
from pathlib import Path
from llm_kosh.engine.reasoning.causal_dag import CausalDAG, EdgeType
from llm_kosh.engine.reasoning.causal_retrieval import CausalRetrieval
from llm_kosh.core.memory import init_cartridge

@pytest.fixture
def dag_with_facts(tmp_path):
    init_cartridge(tmp_path, "Test")
    dag = CausalDAG(tmp_path)
    now = datetime.now(timezone.utc)
    fid1 = dag.add_fact("Gravity pulls objects toward Earth", now, now, now, None, 0.9, "user")
    fid2 = dag.add_fact("Newton formulated laws of motion", now, now, now, None, 0.9, "user")
    fid3 = dag.add_fact("Bread is a baked food product", now, now, now, None, 0.9, "user")
    dag.add_edge(fid1, fid2, EdgeType.ENABLES, 0.8, now, None, "test")
    return dag, fid1, fid2, fid3

def test_retrieve_returns_anchor_facts(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    import time
    results = retrieval.retrieve("gravity Newton motion", time.time(), depth=2)
    fact_ids = [r[0].id for r in results]
    assert fid1 in fact_ids or fid2 in fact_ids

def test_retrieve_excludes_unrelated(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    import time
    results = retrieval.retrieve("gravity Newton motion", time.time(), depth=2)
    # bread fact should score very low or absent
    scores = {r[0].id: r[2] for r in results}
    bread_score = scores.get(fid3, 0.0)
    gravity_score = scores.get(fid1, 0.0)
    assert gravity_score > bread_score

def test_retrieve_causal_distance(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    import time
    results = retrieval.retrieve("gravity", time.time(), depth=2)
    dist_map = {r[0].id: r[1] for r in results}
    # fid1 is anchor (distance 0), fid2 is 1 hop away
    if fid1 in dist_map and fid2 in dist_map:
        assert dist_map[fid1] <= dist_map[fid2]

def test_retrieve_temporal_filter(dag_with_facts):
    dag, fid1, fid2, fid3 = dag_with_facts
    retrieval = CausalRetrieval(dag)
    # Query at time 0 (before any fact's valid_from) — should return nothing
    results = retrieval.retrieve("gravity", query_time=0.0, depth=2)
    assert results == []
