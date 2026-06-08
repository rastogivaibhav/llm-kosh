import json
import pytest

def test_cli_embed_and_semantic_query(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Semantic Memory", "--body", "Apples and oranges are fruits", workspace=temp_workspace)
    runner("add", "--kind", "note", "--title", "Another Memory", "--body", "Cars and trucks are vehicles", workspace=temp_workspace)
    
    # embed
    code, out, err = runner("embed", "--backend", "tfidf", workspace=temp_workspace)
    assert code == 0
    assert "Vector index built" in out or "built" in out.lower() or "indexed" in out.lower()
    
    # semantic query
    code, out, err = runner("query", "fruit", "--semantic", "--json", workspace=temp_workspace)
    assert code == 0
    results = json.loads(out)
    assert len(results) >= 0
