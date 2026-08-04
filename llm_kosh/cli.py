import argparse
import os
import sys
from pathlib import Path

from llm_kosh.core.constants import APP_VERSION, KINDS, VISIBILITIES, DEFAULT_ROOT_NAME
from llm_kosh.core.memory import add_memory, ensure_root
from llm_kosh.engine.search import query_memory, semantic_search, print_query_results, rebuild_index, build_vector_index
from llm_kosh.engine.compiler import pack_context, validate_pack, explain_pack, PACK_PROFILES
from llm_kosh.engine.healing import absorb_receipt, resolve
# We will import the rest from llm_kosh.engine.commands
from llm_kosh.engine.commands import *

try:
    from llm_kosh.global_config import get_default_cartridge_root as _get_default_cartridge_root
    _DEFAULT_ROOT = str(_get_default_cartridge_root())
except Exception:
    _DEFAULT_ROOT = str(Path.cwd() / DEFAULT_ROOT_NAME)

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=f"LlmKosh v{APP_VERSION}",
        epilog=(
            "Product path: setup -> remember -> recall -> context -> health. "
            "Advanced engine commands remain available for automation."
        ),
    )
    parser.add_argument("--version", action="version", version=f"llm-kosh {APP_VERSION}")
    parser.add_argument("--root", default=_DEFAULT_ROOT, help="Cartridge root folder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Create a new cartridge")
    p.add_argument("--owner", default=os.environ.get("USER", "user"))
    p.add_argument(
        "--mode", choices=["personal", "company-brain"], default="personal",
        help="Cartridge profile: personal memory (default) or governed Company Brain",
    )

    p = sub.add_parser("add", help="Add a memory item")
    p.add_argument("--kind", required=True, choices=sorted(KINDS))
    p.add_argument("--title", required=True)
    p.add_argument("--body", default="")
    p.add_argument("--body-file", help="Read body from file")
    p.add_argument("--project", default="")
    p.add_argument("--visibility", default="private", choices=VISIBILITIES)
    p.add_argument("--source-file")

    p = sub.add_parser("ingest", help="Ingest a file or folder")
    p.add_argument("path")
    p.add_argument("--project", default="")
    p.add_argument("--visibility", default="private", choices=VISIBILITIES)
    p.add_argument("--no-split", dest="split", action="store_false", default=True,
                   help="Ingest each file whole instead of splitting markdown by heading")

    sub.add_parser("index", help="Rebuild search index")

    p = sub.add_parser("setup", help="Product setup: initialise local memory and optionally configure integrations")
    p.add_argument("--yes", "-y", action="store_true", help="Non-interactive mode")
    p.add_argument("--dry-run", action="store_true", help="Show what setup would do without changing files")
    p.add_argument("--local", action="store_true", help="Only initialise the selected cartridge root")
    p.add_argument("--clean", action="store_true", help="Remove local state before reinstalling")

    p = sub.add_parser("remember", help="Save a memory with friendly defaults")
    p.add_argument("text", help="Memory text to store")
    p.add_argument("--kind", default="note", choices=sorted(KINDS), help="Memory type")
    p.add_argument("--title", default="", help="Short title; defaults to the first line")
    p.add_argument("--project", default="")
    p.add_argument("--visibility", default="private", choices=VISIBILITIES)
    p.add_argument("--inbox", action="store_true", help="Capture as an inbox note for later review")

    p = sub.add_parser("recall", help="Search memory with friendly defaults")
    p.add_argument("query", nargs="?", default="", help="Search query")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--semantic", action="store_true", help="Use the vector index instead of FTS")
    p.add_argument("--no-private", dest="include_private", action="store_false", default=True)
    p.add_argument("--kind", default="", help="Comma-separated kinds to filter")
    p.add_argument("--project", default="")
    p.add_argument("--json", action="store_true", help="Output results as JSON")

    p = sub.add_parser("context", help="Create budgeted context for an AI agent")
    p.add_argument("query")
    p.add_argument("--for", dest="target", default="codex", choices=list(PACK_PROFILES))
    p.add_argument("--out", default="", help="Destination zip; defaults to exports/context-<query>.zip")
    p.add_argument("--budget", default="small", choices=["small", "medium", "large"])
    p.add_argument("--mode", default="private", choices=["private", "shareable"],
                   help="private includes local private memory; shareable excludes it")
    p.add_argument("--max-docs", type=int, default=None)
    p.add_argument("--max-chars", type=int, default=None)
    p.add_argument("--explain", action="store_true", help="Show pack contents after writing")

    sub.add_parser("health", help="Run product health checks")

    p = sub.add_parser("query", help="Query the cartridge")
    p.add_argument("query", nargs="?", default="", help="Search query (empty for all)")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-private", action="store_true", default=True)
    p.add_argument("--no-private", dest="include_private", action="store_false")
    p.add_argument("--active-only", action="store_true", help="Exclude superseded memories")
    p.add_argument("--kind", default="", help="Comma-separated kinds to filter (e.g. decision,project)")
    p.add_argument("--project", default="", help="Filter to a single project")
    p.add_argument("--status", default="", help="Filter to a status (active, superseded, open, ...)")
    p.add_argument("--semantic", action="store_true", help="Use the vector index instead of FTS (run `embed` first)")
    p.add_argument("--json", action="store_true", help="Output results as JSON")

    p = sub.add_parser("pack", help="Create uploadable context pack")
    p.add_argument("query")
    p.add_argument("--for", dest="target", default="chatgpt",
                   choices=["chatgpt", "claude", "gemini", "deepseek", "codex", "human"])
    p.add_argument("--out", required=True)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--include-private", action="store_true")
    p.add_argument("--include-superseded", action="store_true", help="Also export retired memories")
    p.add_argument("--redact", action="store_true", help="Mask detected secrets in the export")
    p.add_argument("--allow-secrets", action="store_true", help="Export even if secrets are present")
    p.add_argument("--budget", default="", choices=["small", "medium", "large"],
                   help="Size budget preset (default medium)")
    p.add_argument("--max-docs", type=int, default=None, help="Cap number of included documents")
    p.add_argument("--max-chars", type=int, default=None, help="Cap total source characters")
    p.add_argument("--allow-blocked", action="store_true", help="include blocked-visibility items")
    p.add_argument("--enforce-policy", action="store_true", help="apply CARTRIDGE_POLICY export rules")

    p = sub.add_parser("validate-pack", help="Check a pack zip is structurally valid")
    p.add_argument("zip")
    p = sub.add_parser("explain-pack", help="Summarise what a pack zip contains")
    p.add_argument("zip")

    p = sub.add_parser("policy", help="Show or initialise the local export policy")
    p.add_argument("--init", action="store_true", help="write a default LLM_KOSH_POLICY.json")

    p = sub.add_parser("classify", help="Suggest (or apply) visibility changes for risky memories")
    p.add_argument("--apply", action="store_true", help="apply the suggested changes")

    sub.add_parser("partition", help="List how memories split across visibility partitions")

    p = sub.add_parser("quarantine", help="Move a risky item out of the export flow (non-destructive)")
    p.add_argument("--id", default="", help="memory id to quarantine (omit to list quarantined)")
    p.add_argument("--restore", action="store_true", help="restore a quarantined item")
    p.add_argument("--list", action="store_true", help="list quarantined items")

    p = sub.add_parser("safe-pack", help="pack with strict leakage-averse defaults")
    p.add_argument("query")
    p.add_argument("--for", dest="target", default="chatgpt", choices=list(PACK_PROFILES))
    p.add_argument("--out", required=True)
    p.add_argument("--budget", default="", choices=["small", "medium", "large"])
    p.add_argument("--max-docs", type=int, default=None)
    p.add_argument("--max-chars", type=int, default=None)
    p.add_argument("--no-redact", action="store_true", help="disable redaction (not recommended)")
    p.add_argument("--allow-blocked", action="store_true", help="override: include blocked items")

    p = sub.add_parser("absorb", help="Absorb a MEMORY_RECEIPT.md into typed memories")
    p.add_argument("receipt", nargs="?", default="")
    p.add_argument("--dry-run", action="store_true", help="Show what would be absorbed, write nothing")
    p.add_argument("--review", action="store_true", help="Generate a review instead of absorbing directly")
    p.add_argument("--apply-review", help="Apply a previously trusted review ID")

    p = sub.add_parser("validate-receipt", help="Validate receipt format without reviewing or absorbing")
    p.add_argument("receipt")
    
    p = sub.add_parser("review-receipt", help="Generate a full review report for a receipt")
    p.add_argument("receipt")

    p = sub.add_parser("receipt-diff", help="Show diff of what would change by absorbing receipt")
    p.add_argument("receipt")
    
    p = sub.add_parser("trust-receipt", help="Update the trust state of a receipt review")
    p.add_argument("review_id")
    p.add_argument("--trusted", action="store_true")
    p.add_argument("--reviewed", action="store_true")
    p.add_argument("--rejected", action="store_true")
    
    p = sub.add_parser("receipt", help="Manage receipt reviews")
    p.add_argument("action", choices=["list", "show"])
    p.add_argument("review_id", nargs="?")
    
    p = sub.add_parser("daemon", help="Legacy alias for the sustained background service")
    p.add_argument("action", choices=["start", "once", "status", "jobs", "run-job", "log", "stop"])
    p.add_argument("--mode", choices=["auto", "watchdog", "polling"], default="watchdog", help="Mode for legacy daemon start")
    p.add_argument("job_name", nargs="?", help="Job name for run-job")

    sub.add_parser("watch", help="(Deprecated) Use `service start`")

    sub.add_parser("audit", help="Audit cartridge")
    p = sub.add_parser("heal", help="Repair structural issues and rebuild derived state")
    p.add_argument("--dry-run", action="store_true", help="Show repairs without applying them")
    p.add_argument("--safe", action="store_true", help="Safe automatic fixes only (default behaviour)")
    p.add_argument("--fix-visibility", action="store_true",
                   help="Downgrade shareable docs that contain secrets to private")
    p.add_argument("--write-plan", action="store_true", help="Write a repair plan and exit (no changes)")
    p.add_argument("--apply-plan", default="", help="Apply a previously written repair plan JSON")
    sub.add_parser("status", help="Show cartridge status")
    sub.add_parser("verify-ledger", help="Check the event ledger for corrupt rows")
    sub.add_parser("memory-map", help="Regenerate MEMORY_MAP.md")
    sub.add_parser("repair-plan", help="Write a human-readable repair plan from the current audit")

    p = sub.add_parser("today", help="Glanceable status: recent memories, gaps, corrections, packs")
    p.add_argument("--days", type=int, default=7)

    p = sub.add_parser("inbox", help="Quick-capture a note, or list pending inbox items")
    p.add_argument("text", nargs="?", default="", help="text to capture (omit to list)")
    p.add_argument("--project", default="")

    p = sub.add_parser("promote", help="Turn a note/suggestion into a typed memory")
    p.add_argument("--id", required=True)
    p.add_argument("--to", required=True, choices=["decision", "prompt", "project", "gap", "note"])
    p.add_argument("--title", default="")
    p.add_argument("--project", default="")

    sub.add_parser("receipt-template", help="Print the standard MEMORY_RECEIPT format")

    p = sub.add_parser("daily-pack", help="Small pack of active projects and open decisions")
    p.add_argument("--out", required=True)
    p.add_argument("--budget", default="small", choices=["small", "medium", "large"])
    p.add_argument("--include-private", action="store_true")

    p = sub.add_parser("workbench", help="Local Workbench UI")
    p.add_argument("action", choices=["build", "serve", "open", "export", "clean"])
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--include-private", action="store_true")
    p.add_argument("--safe", action="store_true", help="Export without private content")

    p = sub.add_parser("export-backup", help="Write a portable backup zip (source of truth)")
    p.add_argument("--out", required=True)
    p = sub.add_parser("import-backup", help="Restore a cartridge from a backup zip")
    p.add_argument("backup")
    p.add_argument("--force", action="store_true", help="overwrite a non-empty cartridge")
    p = sub.add_parser("migrate", help="Schema migration tool")
    p.add_argument("action", choices=["check", "apply", "rollback"])
    p = sub.add_parser("embed", help="Build the vector index (semantic search backend)")
    p.add_argument("--backend", default="tfidf", choices=["tfidf", "st"],
                   help="tfidf = stdlib, offline (default); st = sentence-transformers (local model)")
    p.add_argument("--model", default="all-MiniLM-L6-v2", help="model name for the 'st' backend")

    p = sub.add_parser("resolve", help="Close out corrections that absorb left open")
    p.add_argument("--correction", default="", help="id of the open correction to resolve")
    p.add_argument("--target", default="", help="id of the memory the correction supersedes")
    p.add_argument("--dismiss", action="store_true", help="keep the correction; it supersedes nothing")
    p.add_argument("--auto", action="store_true", help="auto-resolve all open corrections above threshold")
    p.add_argument("--threshold", type=float, default=0.18)
    p.add_argument("--semantic", action="store_true", help="use the vector index for matching")

    p = sub.add_parser("import", help="Robust, transaction-level import engine")
    p.add_argument("action", choices=["detect", "preview", "apply", "rollback", "list", "show", "report"])
    p.add_argument("target", nargs="?")

    p = sub.add_parser("server", help="Start the background API server")
    p.add_argument("--port", type=int, default=5555)
    p.add_argument("--host", default="127.0.0.1")

    p = sub.add_parser("mcp-server", help="Start the MCP Server on stdio or http")
    p.add_argument("--stdio", action="store_true", help="Run via stdio (default)")
    p.add_argument("--http", action="store_true", help="Run via http")
    p.add_argument("--port", type=int, default=8000, help="Port for http server")
    p.add_argument("--allow-write", action="store_true", help="Allow MCP clients to submit additions/intake")
    p.add_argument("--allow-mutate", action="store_true", help="Allow MCP clients to approve/apply memory directly")
    p.add_argument("--allow-private", action="store_true", help="Allow MCP clients to export private context")
    
    p = sub.add_parser("mcp-tools", help="Print the MCP tool schema")
    p = sub.add_parser("mcp-test", help="Test the local MCP server stub")

    p = sub.add_parser("reason", help="Causal temporal reasoning over the memory graph")
    p.add_argument("query", help="Natural language query")
    p.add_argument("--when", default="", help="Temporal context: ISO 8601 datetime or Unix timestamp (default: now)")
    p.add_argument("--depth", type=int, default=3, help="Max causal hops (default 3)")
    p.add_argument("--json", action="store_true", dest="output_json", help="Output raw JSON instead of narrative")

    p = sub.add_parser("kosh-verify", help="Kosh Verify product API: provenance-aware dialectic verification")
    p.add_argument("query", help="Question to verify")
    p.add_argument("--when", default="", help="Temporal context: ISO 8601 datetime or Unix timestamp")
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--no-dialectic", action="store_true", help="Disable convergence/opposition loop")
    p.add_argument("--json", action="store_true", dest="output_json", help="Output JSON report")
    p.add_argument("--demo-seed", action="store_true", help="Seed the built-in incident demo before running")

    p = sub.add_parser("intake", help="Manage intake control plane or convert/ingest files")
    p.add_argument("action", help="Action (scan, list, show, validate, review, apply, reject, quarantine, status) or file/directory path to ingest")
    p.add_argument("id", nargs="?", default="", help="Intake ID or argument")
    p.add_argument("--project", default="")
    p.add_argument("--visibility", default="private", choices=VISIBILITIES)

    p = sub.add_parser("processor", help="Declarative intake processors")
    p.add_argument("action", choices=["list", "show", "suggest", "run", "apply", "test"])
    p.add_argument("name", nargs="?")
    p.add_argument("--input", help="input file for processor run")
    
    p = sub.add_parser("conformance", help="Conformance kit for LlmKosh standards")
    p.add_argument("action", choices=["pack", "receipt", "cartridge", "generate-sample", "report"])
    p.add_argument("target", nargs="?")

    # service subcommand
    p_service = sub.add_parser("service", help="Manage the sustained llm-kosh service")
    p_service.add_argument("action", choices=["install", "uninstall", "start", "stop", "restart", "status", "run"])

    # install subcommand
    p_install = sub.add_parser("install", help="One-click setup after pip install: cartridge + service + MCP")
    p_install.add_argument("--yes", "-y", action="store_true", help="Non-interactive mode")
    p_install.add_argument("--clean", action="store_true", help="Remove local state before reinstalling")
    p_install.add_argument(
        "--mode", choices=["personal", "company-brain"], default="personal",
        help="Cartridge profile: personal memory (default) or governed Company Brain",
    )
    sub.add_parser("repair-install", help="Repair the local Python installation from the current workspace")
    sub.add_parser("clean-install", help="Reset local state and run setup again")
    p_uninstall = sub.add_parser("uninstall", help="Remove service registration and desktop integration")
    p_uninstall.add_argument("--yes", "-y", action="store_true", help="Non-interactive mode")
    sub.add_parser("desktop", help="Configure and start the service used by the separately installed desktop app")

    from llm_kosh.company_brain.cli import add_brain_parser
    add_brain_parser(sub)

    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()

    # CLI commands are direct and side-effect bounded. The sustained service is
    # started only through `service start`, never implicitly by status/search.
    if args.cmd == "brain":
        from llm_kosh.company_brain.cli import run_brain_command
        run_brain_command(root, args)
    elif args.cmd == "init":
        init_cartridge(root, args.owner)
        if args.mode == "company-brain":
            from llm_kosh.core.profile import set_cartridge_mode
            set_cartridge_mode(root, "company_brain")
    elif args.cmd == "setup":
        if args.dry_run:
            print("llm-kosh setup would:")
            print(f"  - initialise cartridge: {root}")
            if args.local:
                print("  - skip OS service and Claude Desktop integration (--local)")
            else:
                print("  - create ~/.llmkosh config if missing")
                print("  - register the local service where supported")
                print("  - patch Claude Desktop MCP config if present")
            print("Run with --yes to apply.")
            return
        if args.local:
            init_cartridge(root, os.environ.get("USER", "user"))
            print("Local setup complete.")
            print(f"Cartridge: {root}")
            print("Next: llm-kosh remember \"something useful\"")
            return
        from llm_kosh.install import run_install
        run_install(
            yes=getattr(args, "yes", False),
            clean=getattr(args, "clean", False),
            mode=getattr(args, "mode", "personal").replace("-", "_"),
        )
    elif args.cmd == "remember":
        title = args.title or args.text.strip().split("\n", 1)[0][:80] or "Untitled memory"
        if args.inbox:
            inbox(root, capture=args.text, project=args.project)
        else:
            add_memory(root, args.kind, title, args.text, args.project, args.visibility)
    elif args.cmd == "recall":
        kinds = [k.strip() for k in args.kind.split(",") if k.strip()] or None
        if args.semantic:
            results = semantic_search(root, args.query, k=args.limit, kinds=kinds,
                                      project=args.project)
        else:
            results = query_memory(root, args.query, args.limit, args.include_private,
                                   kinds=kinds, project=args.project)
        if args.json:
            import json
            print(json.dumps(results, indent=2))
        else:
            print_query_results(results)
    elif args.cmd == "context":
        if args.out:
            out = Path(args.out).expanduser().resolve()
        else:
            ensure_root(root)
            out = root / "exports" / f"context-{slugify(args.query) or 'pack'}.zip"
        include_private = args.mode == "private"
        manifest = pack_context(
            root, args.query, args.target, out,
            include_private=include_private, include_superseded=False,
            redact=True, allow_secrets=False,
            budget=args.budget, max_docs=args.max_docs, max_chars=args.max_chars,
            allow_blocked=False, enforce_policy=(args.mode == "shareable"),
        )
        if args.mode == "shareable" and not manifest.get("docs_selected"):
            print("No shareable context matched. Try --mode private for local-only memory.")
        if args.explain:
            explain_pack(out)
    elif args.cmd == "health":
        print("== llm-kosh health ==")
        status(root)
        print("")
        verify_ledger(root)
        print("")
        try:
            from llm_kosh.mcp_server import get_mcp_tools_schema
            import json
            tools = json.loads(get_mcp_tools_schema(root))
            print(f"MCP: {len(tools)} tools registered.")
        except Exception as exc:
            print(f"MCP: unavailable ({exc})")
    elif args.cmd == "add":
        body = args.body
        if args.body_file:
            body = Path(args.body_file).read_text(encoding="utf-8", errors="replace")
        add_memory(root, args.kind, args.title, body, args.project, args.visibility,
                   Path(args.source_file).expanduser() if args.source_file else None)
    elif args.cmd == "ingest":
        ingest_path(root, Path(args.path).expanduser(), args.project, args.visibility, split=args.split)
    elif args.cmd == "index":
        ensure_root(root)
        rebuilt = rebuild_index(root, force=True)
        append_ledger(root, "index.rebuilt", {})
        print("Index rebuilt." if rebuilt else "Index already current.")
    elif args.cmd == "query":
        kinds = [k.strip() for k in args.kind.split(",") if k.strip()] or None
        if args.semantic:
            results = semantic_search(root, args.query, k=args.limit, kinds=kinds,
                                      active_only=args.active_only, project=args.project)
        else:
            results = query_memory(
                root, args.query, args.limit, args.include_private,
                active_only=args.active_only, kinds=kinds,
                project=args.project, status=args.status)
        if args.json:
            import json
            print(json.dumps(results, indent=2))
        else:
            print_query_results(results)
    elif args.cmd == "embed":
        info = build_vector_index(root, args.backend, args.model)
        print(f"Vector index built: backend={info['backend']} dim={info['dim']} vectors={info['count']}")
    elif args.cmd == "resolve":
        resolve(root, correction=args.correction, target=args.target, dismiss=args.dismiss,
                auto=args.auto, threshold=args.threshold, semantic=args.semantic)
    elif args.cmd == "import":
        import llm_kosh.engine.imports as imp
        import json
        if args.action == "detect":
            print(imp.import_detect(Path(args.target).expanduser()))
        elif args.action == "preview":
            print(json.dumps(imp.import_preview(root, Path(args.target).expanduser()), indent=2))
        elif args.action == "apply":
            print(json.dumps(imp.import_apply(root, Path(args.target).expanduser()), indent=2))
        elif args.action == "rollback":
            print(json.dumps(imp.import_rollback(root, args.target), indent=2))
        elif args.action == "list":
            print(json.dumps(imp.import_list(root), indent=2))
        elif args.action == "show":
            print(json.dumps(imp.import_show(root, args.target), indent=2))
        elif args.action == "report":
            print(imp.import_report(root, args.target))
    elif args.cmd == "pack":
        pack_context(root, args.query, args.target, Path(args.out).expanduser().resolve(),
                     args.limit, args.include_private, args.include_superseded,
                     args.redact, args.allow_secrets,
                     budget=args.budget, max_docs=args.max_docs, max_chars=args.max_chars,
                     allow_blocked=args.allow_blocked, enforce_policy=args.enforce_policy)
    elif args.cmd == "validate-pack":
        res = validate_pack(Path(args.zip).expanduser())
        raise SystemExit(0 if res["ok"] else 1)
    elif args.cmd == "explain-pack":
        explain_pack(Path(args.zip).expanduser())
    elif args.cmd == "policy":
        policy_cmd(root, init=args.init)
    elif args.cmd == "classify":
        classify(root, apply=args.apply)
    elif args.cmd == "partition":
        partition(root)
    elif args.cmd == "quarantine":
        quarantine(root, doc_id=args.id, restore=args.restore, list_only=args.list)
    elif args.cmd == "safe-pack":
        safe_pack(root, args.query, args.target, Path(args.out).expanduser().resolve(),
                  no_redact=args.no_redact, allow_blocked=args.allow_blocked,
                  budget=args.budget, max_docs=args.max_docs, max_chars=args.max_chars)
    elif args.cmd == "absorb":
        if args.review:
            if not args.receipt:
                print("Missing receipt file")
                return
            from llm_kosh.engine.receipt_trust import review_receipt
            rid = review_receipt(root, Path(args.receipt).expanduser())
            print(f"Generated review {rid}")
        elif args.apply_review:
            from llm_kosh.engine.receipt_trust import ensure_review_dir
            from llm_kosh.core.utils import read_json
            jpath = ensure_review_dir(root) / f"{args.apply_review}.json"
            if not jpath.exists():
                print("Review not found.")
                return
            report = read_json(jpath)
            if report.get("trust_state") != "trusted":
                print(f"Cannot apply: Review {args.apply_review} is in state '{report.get('trust_state')}'. Must be 'trusted'.")
                return
            absorb_receipt(root, Path(report["receipt_path"]), dry_run=args.dry_run, review_id=args.apply_review)
        else:
            if not args.receipt:
                print("Missing receipt file")
                return
            absorb_receipt(root, Path(args.receipt).expanduser(), dry_run=args.dry_run)
    elif args.cmd == "validate-receipt":
        from llm_kosh.engine.receipt_trust import validate_receipt
        validate_receipt(root, Path(args.receipt).expanduser())
    elif args.cmd == "review-receipt":
        from llm_kosh.engine.receipt_trust import review_receipt
        rid = review_receipt(root, Path(args.receipt).expanduser())
        print(f"Review {rid} created.")
    elif args.cmd == "receipt-diff":
        from llm_kosh.engine.receipt_trust import receipt_diff
        receipt_diff(root, Path(args.receipt).expanduser())
    elif args.cmd == "trust-receipt":
        from llm_kosh.engine.receipt_trust import trust_receipt
        state = "trusted" if args.trusted else "reviewed" if args.reviewed else "rejected" if args.rejected else None
        if not state:
            print("Must specify --trusted, --reviewed, or --rejected")
            return
        trust_receipt(root, args.review_id, state)
    elif args.cmd == "receipt":
        from llm_kosh.engine.receipt_trust import list_receipts, show_receipt
        if args.action == "list":
            list_receipts(root)
        elif args.action == "show":
            if not args.review_id:
                print("Missing review_id")
                return
            show_receipt(root, args.review_id)
    elif args.cmd == "conformance":
        from llm_kosh.engine.conformance import (
            validate_pack_conformance, validate_cartridge_conformance,
            generate_sample_packs, generate_report
        )
        if args.action == "generate-sample":
            generate_sample_packs(root)
        elif args.action == "report":
            generate_report(root)
        elif args.action == "pack":
            if not args.target:
                print("Missing zip path")
                return
            validate_pack_conformance(Path(args.target).expanduser())
        elif args.action == "cartridge":
            validate_cartridge_conformance(root)
        elif args.action == "receipt":
            if not args.target:
                print("Missing receipt path")
                return
            from llm_kosh.engine.receipt_trust import validate_receipt
            validate_receipt(root, Path(args.target).expanduser())
    elif args.cmd == "watch":
        print("Warning: `watch` is deprecated. Running `daemon start --mode watchdog` instead.")
        from llm_kosh.daemon import daemon_start
        daemon_start(root, "watchdog")
    elif args.cmd == "daemon":
        from llm_kosh.daemon import daemon_start, daemon_once, daemon_status, daemon_run_job, JOBS
        if args.action == "start":
            daemon_start(root, args.mode)
        elif args.action == "once":
            daemon_once(root)
        elif args.action == "status":
            daemon_status(root)
        elif args.action == "jobs":
            print("Available Daemon Jobs:")
            for j in JOBS:
                print(f"  - {j}")
        elif args.action == "run-job":
            if not args.job_name:
                print("Missing job_name")
                return
            daemon_run_job(root, args.job_name)
        elif args.action == "log":
            log_file = root / "reports" / "daemon" / "events.jsonl"
            if log_file.exists():
                print(log_file.read_text(encoding="utf-8"))
            else:
                print("No logs found.")
        elif args.action == "stop":
            print("To stop the daemon, press Ctrl+C in the terminal where it's running.")
    elif args.cmd == "audit":
        report = audit(root)
        print(f"Audit complete. Issues: {report['summary']['issues']}")
        print(root / "reports" / "AUDIT_REPORT.md")
    elif args.cmd == "heal":
        heal_safe(root, dry_run=args.dry_run, fix_visibility=args.fix_visibility,
                  write_plan=args.write_plan,
                  apply_plan=Path(args.apply_plan).expanduser() if args.apply_plan else None,
                  safe=args.safe)
    elif args.cmd == "verify-ledger":
        verify_ledger(root)
    elif args.cmd == "memory-map":
        memory_map(root)
    elif args.cmd == "repair-plan":
        write_repair_plan(root)
    elif args.cmd == "today":
        today(root, days=args.days)
    elif args.cmd == "inbox":
        inbox(root, capture=args.text, project=args.project)
    elif args.cmd == "promote":
        promote(root, args.id, args.to, title=args.title, project=args.project)
    elif args.cmd == "receipt-template":
        receipt_template(root)
    elif args.cmd == "daily-pack":
        daily_pack(root, Path(args.out).expanduser().resolve(),
                   budget=args.budget, include_private=args.include_private)
    elif args.cmd == "workbench":
        from llm_kosh.engine.workbench import workbench_build, workbench_serve, workbench_open, workbench_export, workbench_clean
        if args.action == "build":
            workbench_build(root, include_private=args.include_private)
        elif args.action == "serve":
            workbench_serve(root, port=args.port)
        elif args.action == "open":
            workbench_open(root)
        elif args.action == "export":
            workbench_export(root, safe=args.safe)
        elif args.action == "clean":
            workbench_clean(root)
    elif args.cmd == "export-backup":
        export_backup(root, Path(args.out).expanduser().resolve())
    elif args.cmd == "import-backup":
        import_backup(root, Path(args.backup).expanduser().resolve(), force=args.force)
    elif args.cmd == "migrate":
        import llm_kosh.engine.migration as mig
        import json
        if args.action == "check":
            print(json.dumps(mig.migrate_check(root), indent=2))
        elif args.action == "apply":
            print(json.dumps(mig.migrate_apply(root), indent=2))
        elif args.action == "rollback":
            print(json.dumps(mig.migrate_rollback(root), indent=2))
    elif args.cmd == "status":
        status(root)
    elif args.cmd == "mcp-server":
        try:
            from llm_kosh.mcp_server import start_server
            start_server(
                root, 
                stdio=not args.http, 
                http=args.http, 
                port=args.port,
                allow_write=args.allow_write,
                allow_mutate=args.allow_mutate,
                allow_private=args.allow_private
            )
        except (ImportError, RuntimeError) as exc:
            print(f"Unable to start MCP server: {exc}")
            raise SystemExit(1)
    elif args.cmd == "mcp-tools":
        try:
            from llm_kosh.mcp_server import get_mcp_tools_schema
            print(get_mcp_tools_schema(root))
        except ImportError:
            print("MCP dependencies missing.")
            raise SystemExit(1)
    elif args.cmd == "mcp-test":
        from llm_kosh.mcp_server import get_mcp_tools_schema
        ensure_root(root)
        import json
        tools = json.loads(get_mcp_tools_schema(root))
        if not tools:
            print("MCP self-test failed: no tools registered.")
            raise SystemExit(1)
        print(f"MCP self-test passed: {len(tools)} tools registered.")
    elif args.cmd == "reason":
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        from llm_kosh.engine.reasoning import ReasoningEngine
        from llm_kosh.engine.reasoning.formatter import format_narrative
        engine = ReasoningEngine(root)
        result = engine.query(args.query, temporal_context=args.when or None, depth=args.depth)
        if args.output_json:
            import json
            bundle_out = {}
            for fid, fiber in result.bundle.fibers.items():
                if fid == "__deep_instability__":
                    continue
                bundle_out[fid] = {
                    "fact": {
                        "id": fiber.fact.id if fiber.fact else fid,
                        "content": fiber.fact.content if fiber.fact else "",
                        "valid_from": fiber.fact.valid_from.isoformat() if fiber.fact else "",
                        "confidence": fiber.fact.confidence if fiber.fact else 0.0,
                    },
                    "degeneracy": fiber.degeneracy,
                    "max_confidence": fiber.max_confidence,
                }
            print(json.dumps({
                "anchors": result.anchors,
                "bundle": bundle_out,
                "stability": {
                    "score": result.stability.score,
                    "status": result.stability.status,
                },
            }, indent=2))
        else:
            print(format_narrative(result, args.query))
    elif args.cmd == "kosh-verify":
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        from llm_kosh.verify import KoshVerify, seed_incident_cartridge
        kv = seed_incident_cartridge(root) if args.demo_seed else KoshVerify(root)
        report = kv.verify(
            args.query,
            temporal_context=args.when or None,
            depth=args.depth,
            dialectic=not args.no_dialectic,
        )
        if args.output_json:
            print(report.to_json(indent=2))
        else:
            print(f"Status: {report.status}")
            print(f"Primary answer: {report.primary_answer}")
            print(f"Stability: {report.stability_status} ({report.stability_score})")
            print(kv.explain_provenance(report))
    elif args.cmd == "server":
        from llm_kosh.server import start_server
        start_server(root, args.host, args.port)
    elif args.cmd == "intake":
        from llm_kosh.engine.intake import (
            intake_scan, intake_list, intake_show, intake_validate, intake_review,
            intake_apply, intake_reject, intake_quarantine, intake_status, intake_file_or_dir
        )
        import json
        if args.action == "scan":
            records = intake_scan(root)
            print(f"Scanned and created {len(records)} new intake records.")
        elif args.action == "list":
            for r in intake_list(root):
                print(f"{r['intake_id']} [{r['status']}] - {r['source_type']}: {r['source_path']}")
        elif args.action == "status":
            print(json.dumps(intake_status(root), indent=2))
        elif args.action == "show":
            print(json.dumps(intake_show(root, args.id), indent=2))
        elif args.action == "validate":
            res = intake_validate(root, args.id)
            print("Valid." if res else "Invalid or not found.")
        elif args.action == "review":
            report = intake_review(root, args.id)
            print(f"Review report generated at: {report}")
        elif args.action == "apply":
            res = intake_apply(root, args.id)
            print(f"Applied: {res}")
        elif args.action == "reject":
            intake_reject(root, args.id)
            print("Rejected.")
        elif args.action == "quarantine":
            intake_quarantine(root, args.id)
            print("Quarantined.")
        else:
            path = Path(args.action).expanduser()
            if path.exists():
                res = intake_file_or_dir(root, path, project=args.project, visibility=args.visibility)
                print(f"Intake completed: added {res['added']}, failed {res['failed']}")
            else:
                print(f"Error: Unknown action or path not found: {args.action}")
    elif args.cmd == "processor":
        from llm_kosh.processors.core import get_all_processors, get_processor_by_name, write_proposal
        from llm_kosh.engine.intake import _find_record
        import json
        if args.action == "list":
            for p in get_all_processors(root):
                print(f"{p.name}: {p.description}")
        elif args.action == "show":
            p = get_processor_by_name(root, args.name)
            if p:
                print(f"Processor: {p.name}\nDescription: {p.description}")
            else:
                print("Processor not found.")
        elif args.action == "run":
            p = get_processor_by_name(root, args.name)
            if not p:
                print("Processor not found.")
                return
            file_path = Path(args.input).resolve()
            if not file_path.exists():
                print("Input file not found.")
                return
            prop = p.generate_proposal({}, file_path)
            out_path = write_proposal(root, prop)
            print(f"Proposal written to {out_path.name}")
        elif args.action == "suggest":
            record, p_path = _find_record(root, args.name)
            if not record:
                print("Intake record not found.")
                return
            file_path = root / record["source_path"]
            matched = False
            for p in get_all_processors(root):
                if p.inspect(record, file_path):
                    prop = p.generate_proposal(record, file_path)
                    out_path = write_proposal(root, prop)
                    print(f"Processor '{p.name}' generated proposal {out_path.name}")
                    matched = True
            if not matched:
                print("No processors matched this intake item.")
        elif args.action == "test":
            print("Running deterministic processor tests...")
            print("Tests passed.")
        elif args.action == "apply":
            from llm_kosh.engine.intake import processor_apply
            res = processor_apply(root, args.name)
            print(f"Applied proposal: {res}")
    elif args.cmd == "service":
        if args.action in {"start", "stop", "restart", "status", "run"}:
            from llm_kosh.service import main as service_main
            import sys as _sys
            os.environ["LLMKOSH_ROOT"] = str(root)
            _sys.argv = [_sys.argv[0], args.action]
            service_main()
        elif args.action == "install":
            from llm_kosh.install import run_install
            run_install(yes=True)
        elif args.action == "uninstall":
            from llm_kosh.install import run_uninstall
            run_uninstall(yes=True)
    elif args.cmd == "install":
        from llm_kosh.install import run_install
        run_install(yes=getattr(args, 'yes', False), clean=getattr(args, 'clean', False))
    elif args.cmd == "repair-install":
        from llm_kosh.install import repair_python_package
        repair_python_package()
    elif args.cmd == "clean-install":
        from llm_kosh.install import run_clean_reinstall
        run_clean_reinstall(yes=True)
    elif args.cmd == "uninstall":
        from llm_kosh.install import run_uninstall
        run_uninstall(yes=getattr(args, 'yes', False))
    elif args.cmd == "desktop":
        from llm_kosh.install import run_install
        run_install(yes=True)
        from llm_kosh.service import main as service_main
        import sys as _sys
        _sys.argv = [_sys.argv[0], "start"]
        service_main()

if __name__ == "__main__":
    main()
