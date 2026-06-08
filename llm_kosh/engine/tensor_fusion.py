import math
import re
from typing import List, Dict, Any
from collections import defaultdict
from llm_kosh.engine.math_interface import math_core
from llm_kosh.engine.receipt_dag import ReceiptDAG

def _extract_numeric_time(text: str) -> float:
    """Extract numeric time references from text (Day N, Month N, etc)."""
    if not text:
        return float('inf')

    # Try to extract "Day N"
    day_match = re.search(r'Day\s+(\d+)', text, re.IGNORECASE)
    if day_match:
        return float(day_match.group(1))

    # Try to extract month position (January=1, February=2, etc)
    months = ['january', 'february', 'march', 'april', 'may', 'june',
              'july', 'august', 'september', 'october', 'november', 'december']
    for i, month in enumerate(months, 1):
        if month in text.lower():
            return float(i)

    # Try to extract numeric date (1st, 2nd, 3rd, etc)
    date_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text)
    if date_match:
        return float(date_match.group(1))

    # Try to extract time (HH:MM)
    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
    if time_match:
        hours = float(time_match.group(1))
        mins = float(time_match.group(2)) / 60.0
        return hours + mins

    return float('inf')

def sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-10.0 * x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

def _apply_temporal_sequence_clustering(results: List[dict], task_context: dict, all_candidates: List[dict]) -> List[dict]:
    """
    Detect and boost temporally coherent document sequences.
    If any document from a project is retrieved, include ALL documents from that project
    with appropriate temporal ordering boosts.
    """
    if not results:
        return results

    # Find which projects are represented in the results
    retrieved_projects = set()
    for r in results:
        project = (r.get("project", "") or "").lower().strip()
        if project:
            retrieved_projects.add(project)

    # For each retrieved project, find ALL candidates from that project
    to_add = []
    for project in retrieved_projects:
        project_candidates = [c for c in all_candidates
                             if (c.get("project", "") or "").lower().strip() == project]

        if len(project_candidates) < 2:
            continue

        # Sort by narrative time
        with_time = [(c, _extract_numeric_time(c.get("body", ""))) for c in project_candidates]
        with_time.sort(key=lambda x: x[1])
        times = [t for _, t in with_time]

        # Check if they form a coherent temporal sequence
        is_coherent = all(times[i] < times[i + 1] or times[i + 1] == float('inf')
                         for i in range(len(times) - 1))

        if is_coherent and all(t != float('inf') for t in times[:-1]):
            # Check which ones are already in results
            result_ids = {r["id"] for r in results}
            sequence_bonus = task_context.get("sequence_coherence_bonus", 0.25)

            for doc, _ in with_time:
                if doc["id"] not in result_ids:
                    # Add missing document with sequence bonus
                    doc_copy = doc.copy()
                    doc_copy["score"] = round(sequence_bonus, 4)
                    to_add.append(doc_copy)
                else:
                    # Boost existing document
                    for r in results:
                        if r["id"] == doc["id"]:
                            r["score"] = round(r.get("score", 0.0) + sequence_bonus, 4)
                            break

    results.extend(to_add)
    return results

def retrieve_memory_tensor(
    query_vector_sem: List[float],
    query_vector_proc: List[float],
    query_time: float,
    candidates: List[dict],
    task_context: dict,
    dag: ReceiptDAG,
    project_counts: Dict[str, int]
) -> List[dict]:
    beta_sem = task_context.get("beta_sem", 0.7)
    beta_proc = task_context.get("beta_proc", 0.3)
    alpha = task_context.get("alpha", 0.02)
    gamma = task_context.get("gamma", 0.5)
    tau = task_context.get("tau", 0.5)

    results = []
    for cand in candidates:
        cand_id = cand.get("id", "")
        status = cand.get("status", "")
        
        m_bool = dag.get_boolean_admissibility(cand_id, status)
        if m_bool <= 0.0:
            continue

        cand_sem = cand.get("embedding_sem")
        if not cand_sem:
            cand_sem = [0.0] * len(query_vector_sem)
        cand_proc = cand.get("embedding_proc")
        if not cand_proc:
            cand_proc = [0.0] * len(query_vector_proc)

        w_sem = [1.0] * len(query_vector_sem)
        w_proc = [1.0] * len(query_vector_proc)

        cos_sem = math_core.weighted_cosine_similarity(query_vector_sem, cand_sem, w_sem)
        cos_proc = math_core.weighted_cosine_similarity(query_vector_proc, cand_proc, w_proc)

        s_dir = (beta_sem * cos_sem) + (beta_proc * cos_proc)

        # Spatiotemporal distance warping using Mahalanobis distance
        cand_t = float(cand.get("t", 0.0) or cand.get("created_t", 0.0) or 0.0)
        cand_sal = float(cand.get("M_sal", 1.0) or 1.0)
        
        q_st = [query_time, 1.0]
        m_st = [cand_t, cand_sal]
        # weights: alpha squared for time decay, and 0.1 for salience warp
        w_st = [alpha * alpha, 0.1]
        
        st_dist = math_core.mahalanobis_distance(q_st, m_st, w_st)
        p_mag = math.exp(-st_dist)

        m_base = s_dir * p_mag

        cand_project = cand.get("project", "") or ""
        proj_key = cand_project.lower().strip()
        count = project_counts.get(proj_key, 1)
        count = max(count, 1)
        
        # Negative Entropy Centrality
        entropy_score = 1.0 / math.log(2.0 + count)

        boost = 0.0
        if m_base > tau:
            boost = gamma * sigmoid(m_base - tau) * entropy_score

        s_final = m_bool * m_base * (1.0 + boost)

        cand_meta = cand.copy()
        cand_meta["score"] = round(s_final, 4)
        cand_meta["m_base"] = round(m_base, 4)
        cand_meta["s_dir"] = round(s_dir, 4)
        cand_meta["p_mag"] = round(p_mag, 4)
        cand_meta["boost"] = round(boost, 4)
        results.append(cand_meta)

    # State-Recency Mask: Penalize older memories if procedural footprints collide (>0.95)
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            proc_i = results[i].get("embedding_proc")
            proc_j = results[j].get("embedding_proc")
            if not proc_i or not proc_j or len(proc_i) != len(proc_j):
                continue

            w_proc = [1.0] * len(proc_i)
            collision_sim = math_core.weighted_cosine_similarity(proc_i, proc_j, w_proc)

            if collision_sim > 0.95:
                t_i = float(results[i].get("t", 0.0) or results[i].get("created_t", 0.0) or 0.0)
                t_j = float(results[j].get("t", 0.0) or results[j].get("created_t", 0.0) or 0.0)

                # Apply 0.01x multiplier to the older procedural memory
                if t_i < t_j:
                    results[i]["score"] = round(results[i]["score"] * 0.01, 4)
                elif t_j < t_i:
                    results[j]["score"] = round(results[j]["score"] * 0.01, 4)

    # Temporal Proximity Radiance: High-scoring memories radiate to chronologically adjacent items
    radiance_threshold = task_context.get("radiance_threshold", 0.1)
    radiance_window = task_context.get("radiance_window", 60.0)
    radiance_fraction = task_context.get("radiance_fraction", 0.3)

    for i, radiator in enumerate(results):
        radiator_score = radiator.get("score", 0.0)
        if radiator_score <= radiance_threshold:
            continue

        radiator_project = (radiator.get("project", "") or "").lower().strip()
        radiator_time = float(radiator.get("t", 0.0) or radiator.get("created_t", 0.0) or 0.0)

        for j, candidate in enumerate(results):
            if i == j:
                continue

            candidate_project = (candidate.get("project", "") or "").lower().strip()
            if candidate_project != radiator_project or not candidate_project:
                continue

            candidate_time = float(candidate.get("t", 0.0) or candidate.get("created_t", 0.0) or 0.0)
            time_diff = abs(candidate_time - radiator_time)

            if time_diff <= radiance_window:
                radiance_amount = radiator_score * radiance_fraction
                candidate["score"] = round(candidate.get("score", 0.0) + radiance_amount, 4)

    # Temporal Sequence Clustering: Boost documents forming coherent temporal sequences
    results = _apply_temporal_sequence_clustering(results, task_context, candidates)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
