import os
import pytest
from pathlib import Path

def test_fastapi_server_endpoints(temp_workspace, monkeypatch):
    # Skip if fastapi is not installed
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from llm_kosh.server import create_fastapi_app
    from llm_kosh.core.memory import init_cartridge, add_memory
    
    root = Path(temp_workspace)
    init_cartridge(root, "user")
    add_memory(root, "note", "Test Memory Node", "Some body content")
    
    # Configure API Key in environment
    monkeypatch.setenv("LLM_KOSH_API_KEY", "secret_token_123")
    
    app = create_fastapi_app(root)
    client = TestClient(app)
    
    # Test unauthorized request (no token)
    response = client.post("/query", json={"query": "test"})
    assert response.status_code == 401
    
    # Test unauthorized request (bad token)
    headers = {"Authorization": "Bearer bad_token"}
    response = client.post("/query", json={"query": "test"}, headers=headers)
    assert response.status_code == 401
    
    # Test authorized request (good token)
    headers = {"Authorization": "Bearer secret_token_123"}
    response = client.post("/query", json={"query": "test"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # Test /add endpoint
    response = client.post("/add", json={"title": "New Node", "kind": "note", "body": "some text"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Test /status endpoint
    response = client.post("/status", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # Test /audit endpoint
    response = client.post("/audit", json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True
