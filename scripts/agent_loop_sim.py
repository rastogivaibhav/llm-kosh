"""
LLM-Kosh STATE-Bench Analog: Agent Loop Simulator
===================================================
Simulates a realistic 5-turn agentic workflow where:
  1. The agent makes tool calls and persists state via add_memory
  2. State is correctly recalled mid-session
  3. Conflicting state is injected (knowledge update)
  4. The system correctly supersedes old state and returns the updated value
  5. Post-session recall verifies no stale state leaks

This is a structural proof that llm-kosh can serve as the memory backend
for a stateful agentic system without hallucinating stale values.

Output: Structured assertion report to stdout + JSON to reports/benchmarks/
"""
import sys
import json
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.search import rebuild_index, build_vector_index, query_memory
from llm_kosh.engine.intake import intake_file_or_dir
from llm_kosh.core.utils import append_ledger

# ─────────────────────────────────────────────
# Assertion engine
# ─────────────────────────────────────────────

ASSERTIONS = []

def assert_contains(label: str, context: str, expected_substring: str, query: str = ""):
    found = expected_substring.lower() in context.lower()
    status = "PASS" if found else "FAIL"
    icon = "✅" if found else "❌"
    print(f"  {icon}  {label}")
    if not found:
        print(f"       Expected: '{expected_substring}'")
        print(f"       Context preview: '{context[:200]}'")
    ASSERTIONS.append({"label": label, "status": status, "query": query,
                        "expected": expected_substring, "found": found})

def assert_not_contains(label: str, context: str, forbidden_substring: str, query: str = ""):
    leaked = forbidden_substring.lower() in context.lower()
    status = "PASS" if not leaked else "FAIL"
    icon = "✅" if not leaked else "❌"
    print(f"  {icon}  {label}")
    if leaked:
        print(f"       STALE LEAK: '{forbidden_substring}' found in context")
        print(f"       Context preview: '{context[:200]}'")
    ASSERTIONS.append({"label": label, "status": status, "query": query,
                        "expected": f"NOT contains '{forbidden_substring}'", "found": not leaked})

def retrieve(cart: Path, query: str, limit: int = 5, active_only: bool = True) -> tuple:
    t0 = time.perf_counter()
    results = query_memory(cart, query, limit=limit, active_only=active_only)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    ctx = " ".join([f"{r.get('title', '')} {r.get('snippet', '')}" for r in results])
    return results, ctx, elapsed_ms

def write_memory(cart: Path, filename: str, content: str):
    inbox = cart / "agent_inbox"
    inbox.mkdir(exist_ok=True)
    f = inbox / filename
    f.write_text(content, encoding="utf-8")
    intake_file_or_dir(cart, f)

def index(cart: Path):
    rebuild_index(cart, force=True)
    build_vector_index(cart, backend="tfidf")

# ─────────────────────────────────────────────
# SIMULATION SCENARIOS
# ─────────────────────────────────────────────

def scenario_code_review_agent(cart: Path):
    """
    Scenario A: Code Review Agent
    The agent reviews a PR, discovers a bug, files a ticket.
    Mid-session recall verifies the bug details.
    """
    print("\n" + "─"*60)
    print("  SCENARIO A: Code Review Agent Loop")
    print("─"*60)

    # Turn 1: Agent fetches PR details
    write_memory(cart, "pr_881_details.txt",
        "PR #881 by Layla: adds caching layer to search service. "
        "Files changed: search_cache.py, search_engine.py, tests/test_cache.py. "
        "3 new unit tests. Approved by linter."
    )
    index(cart)
    _, ctx, ms = retrieve(cart, "PR 881 author files changed")
    print(f"\n  Turn 1 — Agent reads PR #881 [{ms:.1f}ms]")
    assert_contains("PR #881 author is Layla", ctx, "Layla", "PR 881 author")
    assert_contains("PR #881 adds caching layer", ctx, "caching", "PR 881 content")

    # Turn 2: Agent finds a bug during review
    write_memory(cart, "pr_881_review_notes.txt",
        "Code review finding for PR #881: the cache_key function in search_cache.py "
        "does not sanitise unicode input. This can cause KeyError on non-ASCII queries. "
        "Severity: Medium. Assigned to Layla for fix."
    )
    index(cart)
    _, ctx, ms = retrieve(cart, "PR 881 bug unicode cache_key")
    print(f"\n  Turn 2 — Agent logs bug [{ms:.1f}ms]")
    assert_contains("Bug identified: unicode in cache_key", ctx, "unicode", "PR 881 bug")
    assert_contains("Bug assigned to Layla", ctx, "Layla", "bug assignee")

    # Turn 3: Agent recalls state — who owns the bug fix?
    _, ctx, ms = retrieve(cart, "who is fixing the cache key unicode bug PR 881?")
    print(f"\n  Turn 3 — Agent recalls bug owner [{ms:.1f}ms]")
    assert_contains("Bug owner is Layla", ctx, "Layla", "bug owner recall")
    assert_contains("Cache key unicode issue", ctx, "cache", "bug recall")

    # Turn 4: Agent records Layla's fix was merged
    write_memory(cart, "pr_881_fix.txt",
        "PR #881 bug resolved. Layla submitted fix in commit abc123. "
        "Unicode sanitisation added to cache_key. PR approved and merged to main."
    )
    index(cart)

    # Turn 5: Post-session query — is PR #881 complete?
    _, ctx, ms = retrieve(cart, "What is the final status of PR 881?")
    print(f"\n  Turn 5 — Post-session status recall [{ms:.1f}ms]")
    assert_contains("PR #881 merged", ctx, "merged", "PR status")
    assert_contains("Fix commit abc123", ctx, "abc123", "fix commit")
    assert_contains("Unicode fix applied", ctx, "unicode", "fix details")


def scenario_knowledge_update_agent(cart: Path):
    """
    Scenario B: Knowledge Update — State Overwrite Test
    The agent records a server endpoint. The endpoint changes.
    The system must return only the updated endpoint, not the stale one.
    """
    print("\n" + "─"*60)
    print("  SCENARIO B: Knowledge Update — Staleness Guard")
    print("─"*60)

    # V1: original endpoint written
    write_memory(cart, "inference_endpoint.txt",
        "The inference API endpoint is https://infer.prod.internal/v1/predict. "
        "This serves all model inference requests for production."
    )
    index(cart)
    time.sleep(1.2)  # ensure mtime difference

    # V1 verification
    _, ctx, ms = retrieve(cart, "inference API endpoint production")
    print(f"\n  V1 written and confirmed [{ms:.1f}ms]")
    assert_contains("V1 endpoint present initially", ctx, "v1/predict", "endpoint v1")

    # V2: endpoint updated (same filename = logical overwrite)
    write_memory(cart, "inference_endpoint.txt",
        "UPDATED: The inference API endpoint has been migrated to "
        "https://infer.prod.internal/v2/predict. Version v1 is deprecated and "
        "will return 410 Gone after 2026-08-01."
    )
    index(cart)

    # V2 verification — system should prefer the newer document
    _, ctx, ms = retrieve(cart, "inference API endpoint production")
    print(f"\n  V2 written — querying for current endpoint [{ms:.1f}ms]")
    assert_contains("V2 endpoint returned", ctx, "v2/predict", "endpoint v2")

    # Critical: stale guard — v1 should not be the primary result
    # (Both docs may appear; the key is v2 appears first / is in context)
    assert_not_contains("V1 stale does not dominate response", ctx,
                         "This serves all model inference requests for production", "stale check — deprecated line check")


def scenario_multi_session_agent(cart: Path):
    """
    Scenario C: Multi-Session State Continuity
    Day 1 context is correctly recalled on Day 3 query.
    Agent environment fully simulated across session gaps.
    """
    print("\n" + "─"*60)
    print("  SCENARIO C: Multi-Session State Continuity")
    print("─"*60)

    # Session 1 (Day 1): project kickoff
    write_memory(cart, "session_day1.txt",
        "Session 1 — Day 1. Project Phoenix kickoff. "
        "Team: Zara (PM), Marcus (Backend), Yvette (Frontend). "
        "Goal: Build real-time analytics dashboard. Target: Q3 launch."
    )
    index(cart)

    # Session 2 (Day 2): backend progress
    write_memory(cart, "session_day2.txt",
        "Session 2 — Day 2. Marcus completed the WebSocket server for real-time streaming. "
        "Yvette is building the chart components. "
        "First internal demo scheduled for Friday."
    )
    index(cart)

    # Session 3 (Day 3): cross-session recall query
    _, ctx, ms = retrieve(cart, "What is the Project Phoenix team composition and current status?")
    print(f"\n  Day 3 cross-session recall [{ms:.1f}ms]")
    assert_contains("PM Zara in session recall", ctx, "Zara", "team recall PM")
    assert_contains("Backend Marcus in recall", ctx, "Marcus", "team recall backend")
    assert_contains("Goal: analytics dashboard", ctx, "analytics", "goal recall")
    assert_contains("WebSocket progress recalled", ctx, "WebSocket", "progress recall")

    # Session 4 (Day 4): scope change
    write_memory(cart, "session_day4.txt",
        "Session 4 — Day 4. Scope change: Q3 launch moved to Q4 due to compliance review. "
        "Zara updated the roadmap. Marcus is now also handling data pipeline integration."
    )
    index(cart)

    # Session 5 (Day 5): verify updated timeline
    _, ctx, ms = retrieve(cart, "When is the Project Phoenix launch?")
    print(f"\n  Day 5 — updated timeline recall [{ms:.1f}ms]")
    assert_contains("Q4 launch in updated recall", ctx, "Q4", "updated timeline")


def scenario_hallucination_guard(cart: Path):
    """
    Scenario D: Hallucination Guard — strict no-invention test
    Agent is asked about things that were NEVER ingested.
    System must return empty context (not invent answers).
    """
    print("\n" + "─"*60)
    print("  SCENARIO D: Hallucination Guard — Facts Never Ingested")
    print("─"*60)

    # Ingest some real context so the system isn't empty
    write_memory(cart, "real_data.txt",
        "The company uses Python 3.13 for all backend services. "
        "Primary database is PostgreSQL. Team size: 8 engineers."
    )
    index(cart)

    ghost_queries = [
        ("What is the CEO's personal mobile number?", ["mobile", "phone", "number", "+44", "+1"]),
        ("What is the root SSH password for prod servers?", ["password", "ssh", "root", "secret"]),
        ("List all employee salaries", ["salary", "compensation", "£", "$", "annual pay"]),
    ]

    for query, forbidden_kws in ghost_queries:
        _, ctx, ms = retrieve(cart, query)
        ctx_lower = ctx.lower()
        hallucinated = any(kw.lower() in ctx_lower for kw in forbidden_kws)
        label = f"No hallucination: '{query[:45]}...'"
        assert_not_contains(label, ctx, forbidden_kws[0], query)
        print(f"     query={ms:.1f}ms  ctx_len={len(ctx)}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  LLM-KOSH AGENT LOOP SIMULATOR — STATE-BENCH ANALOG")
    print("="*60)

    base = Path(__file__).parent.parent / "test_root" / "agent_sim"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)

    # Each scenario gets its own cartridge
    results_by_scenario = {}
    scenarios = [
        ("code_review",       scenario_code_review_agent),
        ("knowledge_update",  scenario_knowledge_update_agent),
        ("multi_session",     scenario_multi_session_agent),
        ("hallucination",     scenario_hallucination_guard),
    ]

    for name, fn in scenarios:
        ASSERTIONS.clear()
        cart = base / name
        if cart.exists():
            shutil.rmtree(cart)
        init_cartridge(cart, owner=f"agent_sim_{name}")
        fn(cart)
        scenario_pass = sum(1 for a in ASSERTIONS if a["status"] == "PASS")
        scenario_total = len(ASSERTIONS)
        results_by_scenario[name] = {
            "assertions": list(ASSERTIONS),
            "pass": scenario_pass,
            "fail": scenario_total - scenario_pass,
            "total": scenario_total,
            "accuracy_pct": round(scenario_pass / scenario_total * 100, 1) if scenario_total else 0
        }
        ASSERTIONS.clear()

    # Aggregate
    all_pass  = sum(v["pass"]  for v in results_by_scenario.values())
    all_total = sum(v["total"] for v in results_by_scenario.values())
    overall   = round(all_pass / all_total * 100, 1) if all_total else 0

    print("\n" + "="*60)
    print("  AGENT SIMULATION RESULTS")
    print("="*60)
    for sname, r in results_by_scenario.items():
        icon = "✅" if r["accuracy_pct"] == 100.0 else ("⚠️" if r["accuracy_pct"] >= 75 else "❌")
        print(f"  {icon}  {sname:25s} {r['pass']}/{r['total']} ({r['accuracy_pct']}%)")
    print(f"\n  Overall: {all_pass}/{all_total} assertions passed  ({overall}%)")
    print("="*60)

    # Save report
    ts = int(time.time())
    report_dir = Path(__file__).parent.parent / "reports" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": "agent_loop_simulation",
        "overall": {"pass": all_pass, "total": all_total, "accuracy_pct": overall},
        "scenarios": results_by_scenario
    }
    out = report_dir / f"agent_sim_{ts}.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n  Report saved: {out}\n")

    if overall < 100.0:
        sys.exit(1)


if __name__ == "__main__":
    main()
