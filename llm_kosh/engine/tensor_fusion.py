import math
from typing import List, Dict, Any
from llm_kosh.engine.math_interface import math_core
from llm_kosh.engine.receipt_dag import ReceiptDAG

def sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-10.0 * x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

def retrieve_memory_tensor(
    query_vector: List[float],
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

    dim = len(query_vector)
    # Split vector into halves to represent semantic vs procedural subspaces
    sem_lens = [1.0 if i < dim // 2 else 0.0 for i in range(dim)]
    proc_lens = [1.0 if i >= dim // 2 else 0.0 for i in range(dim)]
    weight_vector = [1.0] * dim

    results = []
    for cand in candidates:
        cand_id = cand.get("id", "")
        status = cand.get("status", "")
        
        m_bool = dag.get_boolean_admissibility(cand_id, status)
        if m_bool <= 0.0:
            continue

        cand_emb = cand.get("embedding")
        if not cand_emb:
            cand_emb = [0.0] * dim
        elif isinstance(cand_emb, str):
            import json
            try:
                cand_emb = json.loads(cand_emb)
            except Exception:
                cand_emb = [0.0] * dim
        
        if len(cand_emb) < dim:
            cand_emb = cand_emb + [0.0] * (dim - len(cand_emb))
        else:
            cand_emb = cand_emb[:dim]

        q_sem = math_core.project_subspace(query_vector, sem_lens)
        m_sem = math_core.project_subspace(cand_emb, sem_lens)
        q_proc = math_core.project_subspace(query_vector, proc_lens)
        m_proc = math_core.project_subspace(cand_emb, proc_lens)

        cos_sem = math_core.weighted_cosine_similarity(q_sem, m_sem, weight_vector)
        cos_proc = math_core.weighted_cosine_similarity(q_proc, m_proc, weight_vector)

        s_dir = (beta_sem * cos_sem) + (beta_proc * cos_proc)

        cand_t = float(cand.get("t", 0.0) or cand.get("created_t", 0.0) or 0.0)
        p_mag = math_core.temporal_euclidean_decay(query_time, cand_t, alpha)

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

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
