import argparse
import os
from pathlib import Path

from ai_cartridge.core.constants import APP_VERSION, KINDS, VISIBILITIES, DEFAULT_ROOT_NAME
from ai_cartridge.core.memory import add_memory, ensure_root
from ai_cartridge.engine.search import query_memory, semantic_search, print_query_results, rebuild_index, build_vector_index
from ai_cartridge.engine.compiler import pack_context, validate_pack, explain_pack, PACK_PROFILES
from ai_cartridge.engine.healing import absorb_receipt, resolve
from ai_cartridge.daemon import watch_command

# We will import the rest from ai_cartridge.engine.commands
from ai_cartridge.engine.commands import *

def main() -> None:
    parser = argparse.ArgumentParser(description=f"AI Memory Cartridge v{APP_VERSION}")
    parser.add_argument("--root", default=str(Path.cwd() / DEFAULT_ROOT_NAME), help="Cartridge root folder")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="Create a new cartridge")
    p.add_argument("--owner", default=os.environ.get("USER", "user"))

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

    p = sub.add_parser("query", help="Query the cartridge")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--include-private", action="store_true", default=True)
    p.add_argument("--no-private", dest="include_private", action="store_false")
    p.add_argument("--active-only", action="store_true", help="Exclude superseded memories")
    p.add_argument("--kind", default="", help="Comma-separated kinds to filter (e.g. decision,project)")
    p.add_argument("--project", default="", help="Filter to a single project")
    p.add_argument("--status", default="", help="Filter to a status (active, superseded, open, ...)")
    p.add_argument("--semantic", action="store_true", help="Use the vector index instead of FTS (run `embed` first)")

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
    p.add_argument("--init", action="store_true", help="write a default CARTRIDGE_POLICY.json")

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
    p.add_argument("receipt")
    p.add_argument("--dry-run", action="store_true", help="Show what would be absorbed, write nothing")
    
    sub.add_parser("watch", help="Watch the receipts folder and auto-absorb incoming receipts")

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

    p = sub.add_parser("static-site", help="Generate a local static HTML dashboard (stdlib only)")
    p.add_argument("--include-private", action="store_true")

    p = sub.add_parser("export-backup", help="Write a portable backup zip (source of truth)")
    p.add_argument("--out", required=True)
    p = sub.add_parser("import-backup", help="Restore a cartridge from a backup zip")
    p.add_argument("backup")
    p.add_argument("--force", action="store_true", help="overwrite a non-empty cartridge")
    p = sub.add_parser("migrate", help="Stamp current version / ensure cartridge_id (reversible)")
    p.add_argument("--dry-run", action="store_true")

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

    def _add_import_parser(name, helptext):
        ip = sub.add_parser(name, help=helptext)
        ip.add_argument("path", help="export zip, folder, or file")
        ip.add_argument("--project", default="", help="attach imported conversations to a project")
        ip.add_argument("--visibility", default="private", choices=VISIBILITIES)
        ip.add_argument("--limit", type=int, default=None, help="cap conversations imported (testing)")
        ip.add_argument("--dry-run", action="store_true", help="show what would be imported; write nothing")
        return ip

    _add_import_parser("import-chatgpt", "Import a ChatGPT export (conversations.json / zip)")
    _add_import_parser("import-claude", "Import a Claude export (conversations.json / zip)")
    _add_import_parser("import-gemini", "Import a Gemini/Bard Google Takeout export (MyActivity.json)")
    _add_import_parser("import-generic", "Import generic transcript file(s): .md/.txt/.json")

    p = sub.add_parser("import-report", help="Show import report(s) written by import-* commands")
    p.add_argument("--import-id", default="", help="show a specific import; default lists all + most recent")

    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()

    if args.cmd == "init":
        init_cartridge(root, args.owner)
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
        print_query_results(results)
    elif args.cmd == "embed":
        info = build_vector_index(root, args.backend, args.model)
        print(f"Vector index built: backend={info['backend']} dim={info['dim']} vectors={info['count']}")
    elif args.cmd == "resolve":
        resolve(root, correction=args.correction, target=args.target, dismiss=args.dismiss,
                auto=args.auto, threshold=args.threshold, semantic=args.semantic)
    elif args.cmd in ("import-chatgpt", "import-claude", "import-gemini", "import-generic"):
        provider = args.cmd.split("-", 1)[1]
        import_conversations(root, provider, Path(args.path).expanduser(),
                             project=args.project, visibility=args.visibility,
                             limit=args.limit, dry_run=args.dry_run)
    elif args.cmd == "import-report":
        import_report(root, import_id=args.import_id)
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
        absorb_receipt(root, Path(args.receipt).expanduser(), dry_run=args.dry_run)
    elif args.cmd == "watch":
        watch_command(root)
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
    elif args.cmd == "static-site":
        static_site(root, include_private=args.include_private)
    elif args.cmd == "export-backup":
        export_backup(root, Path(args.out).expanduser().resolve())
    elif args.cmd == "import-backup":
        import_backup(root, Path(args.backup).expanduser().resolve(), force=args.force)
    elif args.cmd == "migrate":
        migrate(root, dry_run=args.dry_run)
    elif args.cmd == "status":
        status(root)


if __name__ == "__main__":
    main()
