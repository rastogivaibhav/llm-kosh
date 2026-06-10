import pytest
from pathlib import Path
import json

def test_orthogonal_subspaces_ingestion(temp_workspace):
    from llm_kosh.core.memory import init_cartridge, add_memory
    from llm_kosh.engine.search import rebuild_index, build_vector_index, query_memory
    from llm_kosh.engine.math_interface import math_core
    
    root = Path(temp_workspace)
    init_cartridge(root, "user")
    
    # Add a semantic note
    add_memory(root, "note", "Fruit Health benefits", "Apples and oranges are healthy fruits that contain vitamins.")
    # Add a procedural note (code block)
    add_memory(root, "note", "Calculate Sum function", "```python\ndef calculate_sum(a, b):\n    result = a + b\n    return result\n```\nUse this procedure to sum two numbers.")
    
    # Rebuild FTS index
    rebuild_index(root, force=True)
    
    # Build vector index using TF-IDF backend
    stats = build_vector_index(root, backend="tfidf")
    assert stats["count"] == 2
    assert stats["dim"] > 0
    
    # Query memory with procedural query
    res = query_memory(root, "calculate_sum", limit=10)
    assert len(res) > 0
    # The sum function should be higher scoring for a procedural search than the fruit note
    assert "Calculate Sum" in res[0]["title"]
    
    # Direct check of Mahalanobis distance
    d = math_core.mahalanobis_distance([1.0, 2.0], [4.0, 6.0], [0.5, 0.25])
    # sqrt(0.5 * (1-4)^2 + 0.25 * (2-6)^2) = sqrt(0.5 * 9 + 0.25 * 16) = sqrt(4.5 + 4) = sqrt(8.5) = 2.915475
    assert abs(d - 2.9154759) < 1e-5
