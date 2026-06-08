import math
from typing import List

class MemoryTensor:
    def __init__(self):
        self.id = ""
        self.embedding = []  # List[float]
        self.t = 0.0
        self.M_sal = 0.0

def project_subspace(vec: List[float], lens: List[float]) -> List[float]:
    if len(vec) != len(lens):
        raise ValueError("Vector and lens sizes must match")
    return [v * l for v, l in zip(vec, lens)]

def weighted_cosine_similarity(a: List[float], b: List[float], w: List[float]) -> float:
    if len(a) != len(b) or len(a) != len(w):
        raise ValueError("Vector and weight sizes must match")
    
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for vi_a, vi_b, wi in zip(a, b, w):
        wa = wi * vi_a
        wb = wi * vi_b
        dot += wa * vi_b
        norm_a += wa * vi_a
        norm_b += wb * vi_b
        
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))

def temporal_euclidean_decay(q_t: float, m_t: float, alpha: float) -> float:
    return math.exp(-alpha * abs(q_t - m_t))

def temporal_vector_decay(q: List[float], m: List[float], w: List[float], alpha: float) -> float:
    if len(q) != len(m) or len(q) != len(w):
        raise ValueError("Vector and weight sizes must match")
    sum_sq = 0.0
    for qi, mi, wi in zip(q, m, w):
        diff = qi - mi
        sum_sq += wi * diff * diff
    return math.exp(-alpha * math.sqrt(sum_sq))

def mahalanobis_distance(a: List[float], b: List[float], w: List[float]) -> float:
    if len(a) != len(b) or len(a) != len(w):
        raise ValueError("Vector and weight sizes must match")
    sum_sq = 0.0
    for ai, bi, wi in zip(a, b, w):
        diff = ai - bi
        sum_sq += wi * diff * diff
    return math.sqrt(sum_sq)
