import sys
import os
import io
import json
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from contextlib import redirect_stdout

from llm_kosh.engine.search import query_memory, semantic_search
from llm_kosh.engine.compiler import pack_context
from llm_kosh.engine.commands import heal_safe, audit

# FastAPI & Uvicorn checks
try:
    from fastapi import FastAPI, Depends, HTTPException as FastAPIHTTPException, status as FastAPIStatus, Request
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import Optional, List
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# Class-based handler for fallback HTTP Server
class CartridgeAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def check_auth(self, root):
        cfg_path = root / "LLM_KOSH.json"
        cfg = {}
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        expected_key = os.environ.get("LLM_KOSH_API_KEY") or cfg.get("api_key")
        if not expected_key:
            return True
            
        auth_header = self.headers.get("Authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif auth_header:
            token = auth_header
            
        return token == expected_key

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = json.loads(post_data) if post_data else {}
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON body: {str(e)}"}).encode('utf-8'))
            return

        root = Path(self.server.cartridge_root)
        
        # Enforce authentication if key is configured
        if not self.check_auth(root):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized: Invalid or missing API Key"}).encode('utf-8'))
            return

        if not (root / "LLM_KOSH.json").exists():
            try:
                from llm_kosh.core.memory import init_cartridge
                init_cartridge(root, "user")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Failed to auto-initialize cartridge: {str(e)}"}).encode('utf-8'))
                return

        if self.path == '/query':
            try:
                query = params.get('query', '')
                limit = params.get('limit', 10)
                include_private = params.get('include_private', True)
                active_only = params.get('active_only', False)
                kinds = params.get('kinds')
                project = params.get('project', '')
                status = params.get('status', '')
                semantic = params.get('semantic', False)

                if semantic:
                    results = semantic_search(root, query, k=limit, kinds=kinds,
                                              active_only=active_only, project=project)
                else:
                    results = query_memory(
                        root, query, limit, include_private,
                        active_only=active_only, kinds=kinds,
                        project=project, status=status)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(results).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/pack':
            try:
                query = params.get('query', '')
                target = params.get('target', 'chatgpt')
                out_path = Path(params.get('out', 'pack.zip'))
                limit = params.get('limit', 12)
                include_private = params.get('include_private', True)
                include_superseded = params.get('include_superseded', False)
                redact = params.get('redact', True)
                allow_secrets = params.get('allow_secrets', False)
                budget = params.get('budget', 'medium')
                max_docs = params.get('max_docs')
                max_chars = params.get('max_chars')
                allow_blocked = params.get('allow_blocked', False)
                enforce_policy = params.get('enforce_policy', False)

                f = io.StringIO()
                with redirect_stdout(f):
                    pack_context(root, query, target, out_path,
                                 limit, include_private, include_superseded,
                                 redact, allow_secrets,
                                 budget=budget, max_docs=max_docs, max_chars=max_chars,
                                 allow_blocked=allow_blocked, enforce_policy=enforce_policy)
                output = f.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "output": output}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/read':
            try:
                rel_path = params.get('path', '')
                if not rel_path:
                    raise ValueError("path parameter is required")
                
                from llm_kosh.core.utils import parse_frontmatter
                text = (root / rel_path).read_text(encoding="utf-8", errors="replace")
                meta, body = parse_frontmatter(text)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "body": body}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/heal':
            try:
                dry_run = params.get('dry_run', False)
                fix_visibility = params.get('fix_visibility', False)
                write_plan = params.get('write_plan', False)
                apply_plan_str = params.get('apply_plan', '')
                apply_plan = Path(apply_plan_str) if apply_plan_str else None
                safe = params.get('safe', True)

                f = io.StringIO()
                with redirect_stdout(f):
                    heal_safe(root, dry_run=dry_run, fix_visibility=fix_visibility,
                              write_plan=write_plan, apply_plan=apply_plan, safe=safe)
                output = f.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "output": output}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/audit':
            try:
                f = io.StringIO()
                with redirect_stdout(f):
                    report = audit(root)
                    print(f"Audit complete. Issues: {report['summary']['issues']}")
                    print(root / "reports" / "AUDIT_REPORT.md")
                output = f.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "output": output}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/add':
            try:
                from llm_kosh.core.memory import add_memory
                title = params.get('title')
                if not title:
                    raise ValueError("title parameter is required")
                kind = params.get('kind', 'note')
                project = params.get('project', '')
                visibility = params.get('visibility', 'private')
                body = params.get('body', '')

                f = io.StringIO()
                with redirect_stdout(f):
                    add_memory(root, kind, title, body, project=project, visibility=visibility)
                output = f.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "output": output}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/status':
            try:
                from llm_kosh.engine.commands import status
                f = io.StringIO()
                with redirect_stdout(f):
                    status(root)
                output = f.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "output": output}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/classify':
            try:
                from llm_kosh.engine.commands import classify
                dry_run = params.get('dry_run', True)
                f = io.StringIO()
                with redirect_stdout(f):
                    classify(root, dry_run=dry_run)
                output = f.getvalue()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "output": output}).encode('utf-8'))
            except Exception as e:
                self.send_error_response(e)

        elif self.path == '/shutdown':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "message": "Shutting down..."}).encode('utf-8'))
            import threading
            threading.Thread(target=self.server.shutdown).start()

        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode('utf-8'))

    def send_error_response(self, exception):
        exc_traceback = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        self.send_response(500)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": str(exception),
            "traceback": exc_traceback
        }).encode('utf-8'))


# FastAPI App Creator function
def create_fastapi_app(root_path: Path):
    app = FastAPI(title="LlmKosh API Daemon")
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    security = HTTPBearer(auto_error=False)

    def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
        cfg = {}
        cfg_path = root_path / "LLM_KOSH.json"
        if cfg_path.exists():
            try:
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        env_key = os.environ.get("LLM_KOSH_API_KEY")
        cfg_key = cfg.get("api_key")
        
        expected_key = env_key or cfg_key
        if not expected_key:
            return
            
        if not credentials or credentials.credentials != expected_key:
            raise FastAPIHTTPException(
                status_code=FastAPIStatus.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Key",
                headers={"WWW-Authenticate": "Bearer"},
            )

    class QueryParams(BaseModel):
        query: str = ""
        limit: int = 10
        include_private: bool = True
        active_only: bool = False
        kinds: Optional[List[str]] = None
        project: str = ""
        status: str = ""
        semantic: bool = False

    class PackParams(BaseModel):
        query: str = ""
        target: str = "chatgpt"
        out: str = "pack.zip"
        limit: int = 12
        include_private: bool = True
        include_superseded: bool = False
        redact: bool = True
        allow_secrets: bool = False
        budget: str = "medium"
        max_docs: Optional[int] = None
        max_chars: Optional[int] = None
        allow_blocked: bool = False
        enforce_policy: bool = False

    class ReadParams(BaseModel):
        path: str

    class HealParams(BaseModel):
        dry_run: bool = False
        fix_visibility: bool = False
        write_plan: bool = False
        apply_plan: str = ""
        safe: bool = True

    class AddParams(BaseModel):
        title: str
        kind: str = "note"
        project: str = ""
        visibility: str = "private"
        body: str = ""

    class ClassifyParams(BaseModel):
        dry_run: bool = True

    def ensure_init():
        if not (root_path / "LLM_KOSH.json").exists():
            from llm_kosh.core.memory import init_cartridge
            init_cartridge(root_path, "user")

    @app.post("/query", dependencies=[Depends(verify_api_key)])
    def api_query(params: QueryParams):
        ensure_init()
        if params.semantic:
            return semantic_search(root_path, params.query, k=params.limit, kinds=params.kinds,
                                   active_only=params.active_only, project=params.project)
        else:
            return query_memory(
                root_path, params.query, params.limit, params.include_private,
                active_only=params.active_only, kinds=params.kinds,
                project=params.project, status=params.status)

    @app.post("/pack", dependencies=[Depends(verify_api_key)])
    def api_pack(params: PackParams):
        ensure_init()
        out_path = Path(params.out)
        f = io.StringIO()
        with redirect_stdout(f):
            pack_context(root_path, params.query, params.target, out_path,
                         params.limit, params.include_private, params.include_superseded,
                         params.redact, params.allow_secrets,
                         budget=params.budget, max_docs=params.max_docs, max_chars=params.max_chars,
                         allow_blocked=params.allow_blocked, enforce_policy=params.enforce_policy)
        return {"success": True, "output": f.getvalue()}

    @app.post("/read", dependencies=[Depends(verify_api_key)])
    def api_read(params: ReadParams):
        ensure_init()
        from llm_kosh.core.utils import parse_frontmatter
        text = (root_path / params.path).read_text(encoding="utf-8", errors="replace")
        meta, body = parse_frontmatter(text)
        return {"success": True, "body": body}

    @app.post("/heal", dependencies=[Depends(verify_api_key)])
    def api_heal(params: HealParams):
        ensure_init()
        apply_plan = Path(params.apply_plan) if params.apply_plan else None
        f = io.StringIO()
        with redirect_stdout(f):
            heal_safe(root_path, dry_run=params.dry_run, fix_visibility=params.fix_visibility,
                      write_plan=params.write_plan, apply_plan=apply_plan, safe=params.safe)
        return {"success": True, "output": f.getvalue()}

    @app.post("/audit", dependencies=[Depends(verify_api_key)])
    def api_audit():
        ensure_init()
        f = io.StringIO()
        with redirect_stdout(f):
            report = audit(root_path)
            print(f"Audit complete. Issues: {report['summary']['issues']}")
            print(root_path / "reports" / "AUDIT_REPORT.md")
        return {"success": True, "output": f.getvalue()}

    @app.post("/add", dependencies=[Depends(verify_api_key)])
    def api_add(params: AddParams):
        ensure_init()
        from llm_kosh.core.memory import add_memory
        f = io.StringIO()
        with redirect_stdout(f):
            add_memory(root_path, params.kind, params.title, params.body, project=params.project, visibility=params.visibility)
        return {"success": True, "output": f.getvalue()}

    @app.post("/status", dependencies=[Depends(verify_api_key)])
    def api_status():
        ensure_init()
        from llm_kosh.engine.commands import status
        f = io.StringIO()
        with redirect_stdout(f):
            status(root_path)
        return {"success": True, "output": f.getvalue()}

    @app.post("/classify", dependencies=[Depends(verify_api_key)])
    def api_classify(params: ClassifyParams):
        ensure_init()
        from llm_kosh.engine.commands import classify
        f = io.StringIO()
        with redirect_stdout(f):
            classify(root_path, dry_run=params.dry_run)
        return {"success": True, "output": f.getvalue()}

    @app.post("/shutdown")
    def api_shutdown():
        import threading
        def stop_server():
            import time
            time.sleep(0.5)
            os._exit(0)
        threading.Thread(target=stop_server).start()
        return {"success": True, "message": "Shutting down..."}

    return app


def start_server(root_path: Path, host: str, port: int):
    # Setup Debounced Async Watcher
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
        from llm_kosh.engine.search import rebuild_index
        import queue
        import threading
        import time
        
        event_queue = queue.Queue()
        
        class CartridgeEventHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory and event.src_path.endswith(('.md', '.txt', '.json')):
                    event_queue.put(event.src_path)
            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith(('.md', '.txt', '.json')):
                    event_queue.put(event.src_path)

        def worker():
            while True:
                batch = set()
                try:
                    item = event_queue.get(timeout=1.0)
                    batch.add(item)
                except queue.Empty:
                    continue
                
                time.sleep(2.0)
                while not event_queue.empty():
                    try:
                        batch.add(event_queue.get_nowait())
                    except queue.Empty:
                        break
                
                if batch:
                    print(f"[Watcher] Auto-ingesting {len(batch)} modified files...")
                    try:
                        rebuild_index(root_path)
                        print("[Watcher] Auto-ingestion complete.")
                    except Exception as e:
                        print(f"[Watcher] Auto-ingestion failed: {e}")

        worker_thread = threading.Thread(target=worker, daemon=True)
        worker_thread.start()

        observer = Observer()
        observer.schedule(CartridgeEventHandler(), str(root_path), recursive=True)
        observer.start()
    except ImportError:
        observer = None
        print("[Warning] Watchdog not installed. Auto-ingestion disabled.")

    if HAS_FASTAPI:
        print(f"LlmKosh API Daemon running in FastAPI mode at http://{host}:{port}")
        app = create_fastapi_app(root_path)
        try:
            uvicorn.run(app, host=host, port=port, log_level="warning")
            return
        except Exception as e:
            print(f"[Warning] Failed to start FastAPI server: {e}. Falling back to standard HTTP server.")

    # Fallback to standard HTTPServer
    server = HTTPServer((host, port), CartridgeAPIHandler)
    server.cartridge_root = root_path
    print(f"LlmKosh API Daemon running in fallback HTTP mode at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if observer:
            observer.stop()
            observer.join()
        server.server_close()
        print("API Daemon stopped.")
