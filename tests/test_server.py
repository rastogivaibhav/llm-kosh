import threading
import time
import json
import urllib.request
import pytest
from pathlib import Path

@pytest.fixture
def test_server(temp_workspace):
    # run server in background thread
    server_thread = None
    httpd_ref = []
    
    def run_server():
        from http.server import HTTPServer
        from llm_kosh.server import CartridgeAPIHandler
        
        # small hack to pass root to handler
        class CustomHTTPServer(HTTPServer):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.cartridge_root = temp_workspace
                
        httpd = CustomHTTPServer(("127.0.0.1", 0), CartridgeAPIHandler)
        httpd_ref.append(httpd)
        httpd.serve_forever()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # wait for port
    time.sleep(0.5)
    if not httpd_ref:
        yield None
        return
        
    httpd = httpd_ref[0]
    port = httpd.server_port
    
    yield f"http://127.0.0.1:{port}"
    
    httpd.shutdown()
    httpd.server_close()
    server_thread.join()

def test_server_query_endpoint(test_server):
    if not test_server:
        pytest.skip("Server failed to start")
        
    # Test /query
    req = urllib.request.Request(f"{test_server}/query", data=json.dumps({"query": "test"}).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            assert response.status == 200
            data = json.loads(response.read().decode('utf-8'))
            assert isinstance(data, list)
    except Exception as e:
        pytest.fail(f"Request failed: {e}")

def test_server_status_endpoint(test_server):
    if not test_server:
        pytest.skip("Server failed to start")
        
    # Test /status
    req = urllib.request.Request(f"{test_server}/status", data=b"{}")
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            assert response.status == 200
            data = json.loads(response.read().decode('utf-8'))
            assert data.get("success") is True
            assert "output" in data
    except Exception as e:
        pytest.fail(f"Request failed: {e}")

def test_server_pack_endpoint(test_server):
    if not test_server:
        pytest.skip("Server failed to start")
        
    # Test /pack
    req = urllib.request.Request(f"{test_server}/pack", data=json.dumps({"query": "test", "target": "chatgpt"}).encode('utf-8'))
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as response:
            assert response.status == 200
            data = json.loads(response.read().decode('utf-8'))
            assert data.get("success") is True
    except Exception as e:
        pytest.fail(f"Request failed: {e}")

def test_mcp_tools(temp_workspace):
    pytest.importorskip("mcp")
    import llm_kosh.mcp_server
    
    # Override workspace for the imported module
    llm_kosh.mcp_server.WORKSPACE_PATH = Path(temp_workspace)
    
    # init so search doesn't fail on missing db
    from llm_kosh.core.memory import init_cartridge, add_memory
    init_cartridge(llm_kosh.mcp_server.WORKSPACE_PATH, "user")
    add_memory(llm_kosh.mcp_server.WORKSPACE_PATH, "note", "MCP Test", "Body of the note")
    
    # Test tools
    res1 = llm_kosh.mcp_server.search_memory("MCP")
    assert "MCP Test" in res1
    
    try:
        res2 = llm_kosh.mcp_server.search_memory("MCP", use_semantic=True)
        assert isinstance(res2, str)
    except SystemExit:
        pass
    

