from __future__ import annotations

import hashlib
import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

# Re-use existing tokenizer (no new dependency)
from llm_kosh.engine.search import tokenize

_N_COMPONENTS = 32  # DCT vector size — 32 gives good frequency resolution at low cost


def _dct(x: List[float]) -> List[float]:
    """DCT-II: standard type-II Discrete Cosine Transform (stdlib math only)."""
    N = len(x)
    if N == 0:
        return []
    result = []
    for k in range(N):
        s = sum(x[n] * math.cos(math.pi * k * (2 * n + 1) / (2 * N)) for n in range(N))
        result.append(2.0 * s)
    return result


def resonance_profile(
    text: str,
    idf: Optional[Dict[str, float]] = None,
    n_components: int = _N_COMPONENTS,
) -> Dict[str, List[float]]:
    """
    Build a DCT-based resonance profile for text.

    1. Tokenize text.
    2. Compute TF (or TF-IDF if idf supplied).
    3. Take top-n_components terms sorted by weight.
    4. Apply DCT-II to the weight vector.
    5. Split into low / mid / high frequency bands.

    Returns dict with keys "low", "mid", "high".
    """
    tokens = tokenize(text)
    if not tokens:
        band = n_components // 3
        return {
            "low": [0.0] * band,
            "mid": [0.0] * band,
            "high": [0.0] * (n_components - 2 * band),
        }

    tf = Counter(tokens)
    total = len(tokens)

    # Hash-bucket projection: map each token to a deterministic bucket so that
    # token identity (not just weight distribution) influences the DCT input.
    # This prevents texts with different tokens but identical tf distributions
    # from producing the same resonance profile.
    # Uses hashlib (stable across runs; Python's built-in hash() is randomized).
    freq_vector = [0.0] * n_components
    for token, cnt in tf.items():
        weight = (cnt / total) * idf.get(token, 1.0) if idf else cnt / total
        digest = int(hashlib.md5(token.encode(), usedforsecurity=False).hexdigest(), 16)
        bucket = digest % n_components
        freq_vector[bucket] += weight

    coeffs = _dct(freq_vector)

    band = n_components // 3
    return {
        "low": coeffs[:band],
        "mid": coeffs[band : 2 * band],
        "high": coeffs[2 * band :],
    }


def harmonic_match(
    profile_a: Dict[str, List[float]],
    profile_b: Dict[str, List[float]],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Compute multi-scale resonance score between two profiles.
    Bands weighted: low=0.5 (dominant concepts), mid=0.3, high=0.2 (rare terms).
    Returns score in [0, 1].
    """
    if weights is None:
        weights = {"low": 0.5, "mid": 0.3, "high": 0.2}

    score = 0.0
    for band, w in weights.items():
        a = profile_a.get(band, [])
        b = profile_b.get(band, [])
        if not a or not b:
            continue
        min_len = min(len(a), len(b))
        dot = sum(a[i] * b[i] for i in range(min_len))
        norm_a = math.sqrt(sum(v * v for v in a))
        norm_b = math.sqrt(sum(v * v for v in b))
        if norm_a > 0 and norm_b > 0:
            score += w * (dot / (norm_a * norm_b))

    return min(1.0, max(0.0, score))


from llm_kosh.engine.reasoning.causal_dag import CausalDAG, TemporalFact, CausalEdge


class CausalRetrieval:
    """
    Resonance-based retrieval over the CausalDAG.
    Returns (TemporalFact, causal_distance, score) tuples.
    """

    def __init__(self, dag: CausalDAG, idf: Optional[Dict[str, float]] = None) -> None:
        self.dag = dag
        self.idf = idf  # TF-IDF weights for richer resonance (optional)
        self._build_resonance_index()

    def _build_resonance_index(self) -> None:
        """Build resonance profiles for all facts currently in the DAG."""
        self._resonance_index: Dict[str, Dict[str, List[float]]] = {}
        for fid, fact in self.dag.nodes.items():
            if fact.resonance_profile:
                self._resonance_index[fid] = fact.resonance_profile
            else:
                self._resonance_index[fid] = resonance_profile(fact.content, self.idf)

    def retrieve(
        self,
        query: str,
        query_time: float,
        depth: int = 3,
        top_anchors: int = 5,
        min_anchor_overlap: float = 0.18,
        min_anchor_resonance: float = 1.10,
    ) -> List[Tuple[TemporalFact, int, float]]:
        """
        Full retrieval pipeline.

        1. Build query resonance profile.
        2. Harmonic-match against all facts valid at query_time.
        3. Select top-anchor facts.
        4. BFS-traverse causal edges up to depth hops.
        5. Score each candidate.

        Returns list of (fact, causal_distance, score) sorted by score descending.
        """
        if query_time <= 0:
            return []

        query_prof = resonance_profile(query, self.idf)
        query_tokens = set(tokenize(query))
        valid_ids = set(self.dag.interval_tree.query_valid_at(query_time))

        if not valid_ids or not query_tokens:
            return []

        # Step 1: harmonic match -> anchor scores.
        # Guardrail: resonance is a wake-up signal, not proof of evidence.
        # DCT/hash resonance can produce weak positive matches for unrelated text,
        # so an anchor must have either lexical grounding or strong resonance.
        # Without this, unrelated queries can still receive a causal_bonus and look
        # falsely stable instead of producing no_evidence/abstain.
        anchor_scores: Dict[str, float] = {}
        for fid in valid_ids:
            fact = self.dag.nodes.get(fid)
            if not fact:
                continue
            prof = self._resonance_index.get(fid)
            if prof is None:
                prof = resonance_profile(fact.content, self.idf)
                self._resonance_index[fid] = prof
            resonance = harmonic_match(query_prof, prof)
            fact_tokens = set(tokenize(fact.content))
            lexical_overlap = len(query_tokens & fact_tokens) / max(1, len(query_tokens))
            if lexical_overlap >= min_anchor_overlap or resonance >= min_anchor_resonance:
                anchor_scores[fid] = resonance

        if not anchor_scores:
            return []

        # Step 2: pick top anchors
        top = sorted(anchor_scores, key=lambda x: -anchor_scores[x])[:top_anchors]

        # Step 3: BFS from anchors
        visited: Dict[str, int] = {fid: 0 for fid in top}
        queue = list(top)
        for _ in range(depth):
            next_q: List[str] = []
            for fid in queue:
                outgoing = list(self.dag.get_outgoing_edges(fid, query_time))
                outgoing.extend(self.dag.get_hyperedge_expansions(fid, set(visited.keys()), query_time))
                for edge in outgoing:
                    if edge.target_id not in visited and edge.target_id in valid_ids:
                        visited[edge.target_id] = visited[fid] + 1
                        next_q.append(edge.target_id)
            queue = next_q
            if not queue:
                break

        # Step 4: score
        results: List[Tuple[TemporalFact, int, float]] = []
        for fid, dist in visited.items():
            fact = self.dag.nodes.get(fid)
            if not fact:
                continue
            resonance = anchor_scores.get(fid, 0.0)
            causal_bonus = 1.0 / (dist + 1)
            score = 0.6 * resonance + 0.3 * causal_bonus + 0.1 * fact.confidence
            results.append((fact, dist, round(score, 4)))

        results.sort(key=lambda x: -x[2])
        return results
