from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional

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

    if idf:
        scored = [(t, (cnt / total) * idf.get(t, 1.0)) for t, cnt in tf.items()]
    else:
        scored = [(t, cnt / total) for t, cnt in tf.items()]

    scored.sort(key=lambda x: -x[1])
    top_weights = [w for _, w in scored[:n_components]]
    # Pad to exactly n_components
    top_weights += [0.0] * (n_components - len(top_weights))

    coeffs = _dct(top_weights)

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
