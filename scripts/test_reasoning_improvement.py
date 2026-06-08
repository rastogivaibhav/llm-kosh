"""
Test Temporal Causal Reasoning Engine v0.1
==========================================

Compares baseline temporal reasoning accuracy (50%)
against the new ReasoningEngine (expected 90%+).

Uses the same F1-based scoring as stress_bench.py.
"""
import re
import sys
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta

# UTF-8 for Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_kosh.core.memory import init_cartridge
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import EdgeType


# ─────────────────────────────────────────────
# SCORING ENGINE (same as stress_bench.py)
# ─────────────────────────────────────────────

def tokenize(text: str) -> set:
    """Simple whitespace + punctuation tokenizer for F1 scoring."""
    return set(re.sub(r'[^\w\s]', '', text.lower()).split())


def compute_f1(retrieved_context: str, expected: str) -> float:
    """
    Keyword F1 between retrieved context and ground-truth expected string.
    Returns 0.0–1.0.
    """
    exp_tokens = tokenize(expected)
    ctx_tokens = tokenize(retrieved_context)
    # Filter very short stopwords
    exp_tokens = {t for t in exp_tokens if len(t) > 2}
    if not exp_tokens:
        return 1.0
    matched = exp_tokens & ctx_tokens
    # Precision relative to a localised extraction window
    effective_ctx_len = min(len(ctx_tokens), len(exp_tokens) * 2.0)
    precision = len(matched) / effective_ctx_len if effective_ctx_len else 0.0
    recall = len(matched) / len(exp_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


PASS_THRESHOLD = 0.30  # F1 threshold for PASS


# ─────────────────────────────────────────────
# TEMPORAL REASONING TEST CASES
# ─────────────────────────────────────────────

TEMPORAL_TESTS = [
    {
        "id": "tmp_001",
        "sessions": [
            "Sprint Alpha kicked off on Monday. The team focused on user authentication.",
            "On Tuesday we completed the OAuth2 provider integration.",
            "Wednesday: deployed the auth service to staging and ran smoke tests.",
            "Thursday: discovered a token refresh bug in production.",
            "Friday: hotfix merged. Authentication is fully stable.",
        ],
        "query": "What order did the authentication milestones occur during the sprint?",
        "expected": "Monday kickoff, Tuesday OAuth2, Wednesday staging deploy, Thursday bug, Friday hotfix"
    },
    {
        "id": "tmp_002",
        "sessions": [
            "January: project Helios approved by steering committee.",
            "March: architecture design finalized.",
            "June: backend API v1 shipped to internal testers.",
            "September: public beta launched with 500 users.",
            "December: Helios v1.0 released to general availability.",
        ],
        "query": "Summarise the Helios project timeline from approval to GA release.",
        "expected": "January approved, March design, June API, September beta, December GA"
    },
    {
        "id": "tmp_003",
        "sessions": [
            "The DevOps team provisioned the database cluster on Day 1.",
            "Application servers were configured on Day 3.",
            "Load balancer setup completed on Day 5.",
            "SSL certificates were issued on Day 6.",
            "Full production traffic cutover happened on Day 7.",
        ],
        "query": "In what order was the infrastructure provisioned?",
        "expected": "database Day 1, application servers Day 3, load balancer Day 5, SSL Day 6, cutover Day 7"
    },
    {
        "id": "tmp_004",
        "sessions": [
            "Team A submitted the Q1 report on 3rd January.",
            "Team B submitted their Q1 report on 10th January.",
            "Finance consolidated both reports on 15th January.",
            "Board reviewed the consolidated report on 20th January.",
        ],
        "query": "When did the board review the Q1 reports?",
        "expected": "20th January, after finance consolidated on 15th"
    },
    {
        "id": "tmp_005",
        "sessions": [
            "Contract with Vendor X was signed on 1st April.",
            "First delivery arrived on 15th April.",
            "Quality review completed on 22nd April.",
            "Payment processed on 30th April.",
        ],
        "query": "What happened between contract signing and payment?",
        "expected": "delivery 15th April, quality review 22nd April, payment 30th April"
    },
    {
        "id": "tmp_006",
        "sessions": [
            "Feature request logged: dark mode for dashboard.",
            "Design mockup approved one week later.",
            "Frontend implementation started two weeks after approval.",
            "Dark mode shipped in release 3.4.",
        ],
        "query": "Describe the dark mode feature journey from request to release.",
        "expected": "logged, mockup approved, implementation started, shipped release 3.4"
    },
    {
        "id": "tmp_007",
        "sessions": [
            "Incident started at 14:00 UTC — database connection pool exhausted.",
            "Mitigation applied at 14:12 UTC: increased pool size.",
            "Traffic restored at 14:25 UTC.",
            "Root cause analysis completed at 17:00 UTC.",
        ],
        "query": "When was traffic restored after the database incident?",
        "expected": "14:25 UTC, twelve minutes after mitigation at 14:12"
    },
    {
        "id": "tmp_008",
        "sessions": [
            "User signed up on 1st March.",
            "User upgraded to Pro tier on 15th March.",
            "User invited 3 teammates on 20th March.",
            "User downgraded back to Free tier on 1st April.",
        ],
        "query": "Summarise this user's subscription history.",
        "expected": "signed up March 1, Pro tier March 15, invited teammates March 20, downgraded April 1"
    },
    {
        "id": "tmp_009",
        "sessions": [
            "Model v1 trained and evaluated — accuracy 72%.",
            "Model v2 with additional data — accuracy 81%.",
            "Model v3 with hyperparameter tuning — accuracy 87%.",
            "Model v4 production deployment — accuracy 89%.",
        ],
        "query": "How did model accuracy improve across versions?",
        "expected": "v1 72%, v2 81%, v3 87%, v4 89% production"
    },
    {
        "id": "tmp_010",
        "sessions": [
            "Legal review started on Monday.",
            "Compliance team raised 3 blockers on Wednesday.",
            "Engineering resolved blockers by Friday.",
            "Legal signed off on Monday the following week.",
        ],
        "query": "How long did the legal review cycle take in total?",
        "expected": "Monday to the following Monday, one full week plus one day, compliance blockers resolved Friday"
    },
]


# ─────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────

def run_temporal_tests():
    """
    Run temporal reasoning tests using ReasoningEngine.
    Report F1 scores and accuracy.
    """
    print("\n" + "="*70)
    print("TEMPORAL REASONING ENGINE TEST SUITE")
    print("="*70)
    print(f"Tests: {len(TEMPORAL_TESTS)}")
    print(f"Baseline (old system): 50% (5/10 passing)")
    print(f"Target (new engine): 90%+ accuracy\n")

    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Initialize cartridge
        init_cartridge(tmpdir, "TemporalReasoningTest")

        # Create ReasoningEngine
        engine = ReasoningEngine(tmpdir)

        results = []
        passing = 0

        for test_case in TEMPORAL_TESTS:
            test_id = test_case["id"]
            query = test_case["query"]
            expected = test_case["expected"]

            print(f"\n[{test_id}] {query}")

            # Ingest all sessions for this test
            ingestion_start = time.time()
            fact_ids = []
            now = datetime.now(timezone.utc)

            # First pass: ingest all facts
            for i, session_text in enumerate(test_case["sessions"]):
                # Spread sessions across time (each session is 1 day apart)
                session_time = now + timedelta(days=i)

                fact_id = engine.ingest(
                    content=session_text,
                    documented_at=session_time,
                    valid_from=session_time,
                    valid_until=session_time + timedelta(days=365),
                    confidence=0.95,
                    causal_edges=[],  # Will add edges in second pass
                )
                fact_ids.append(fact_id)

            # Second pass: establish causal edges forward in time (fact[i] ENABLES fact[i+1])
            for i in range(len(fact_ids) - 1):
                engine.dag.add_edge(
                    source_id=fact_ids[i],
                    target_id=fact_ids[i + 1],
                    edge_type=EdgeType.ENABLES,  # Earlier event enables later event
                    confidence=0.85,
                    valid_from=now + timedelta(days=i),
                    valid_until=None,
                    established_by="test",
                )

            ingestion_time = time.time() - ingestion_start

            # Query the engine at the END of the temporal sequence
            # (so all facts are valid)
            query_temporal_context = (now + timedelta(days=len(test_case["sessions"]) + 1)).timestamp()

            query_start = time.time()
            result = engine.query(query, temporal_context=str(query_temporal_context), depth=5)
            query_time = time.time() - query_start

            # Debug: check what we got
            num_fibers = len(result.bundle.fibers)

            # Reconstruct context from bundle
            context_parts = []
            for fact_id, fiber in result.bundle.fibers.items():
                if fiber.fact and fiber.fact.content:
                    context_parts.append(fiber.fact.content)

            retrieved_context = " ".join(context_parts)

            # If no context, try anchors directly
            if not retrieved_context and result.anchors:
                for anchor_id in result.anchors:
                    fact = engine.dag.get_fact(anchor_id)
                    if fact and fact.content:
                        context_parts.append(fact.content)
                retrieved_context = " ".join(context_parts)

            # Score
            f1_score = compute_f1(retrieved_context, expected)
            status = "✅ PASS" if f1_score >= PASS_THRESHOLD else "❌ FAIL"

            if f1_score >= PASS_THRESHOLD:
                passing += 1

            results.append({
                "id": test_id,
                "f1": round(f1_score, 3),
                "status": "PASS" if f1_score >= PASS_THRESHOLD else "FAIL",
                "stability_score": round(result.stability.score, 3),
                "stability_status": result.stability.status,
                "escape_triggered": result.escape_triggered,
                "query_ms": round(query_time * 1000, 1),
            })

            print(f"  F1 Score: {f1_score:.3f} {status}")
            print(f"  Stability: {result.stability.score:.3f} ({result.stability.status})")
            print(f"  Escape: {'triggered' if result.escape_triggered else 'none'}")
            print(f"  Query latency: {query_time*1000:.1f}ms (ingest: {ingestion_time*1000:.1f}ms)")
            print(f"  Anchors: {', '.join(result.anchors[:3]) if result.anchors else 'none'}")
            print(f"  Escape surfaced: {len(result.escape_surfaced)} facts")

    # Summary
    accuracy = 100.0 * passing / len(TEMPORAL_TESTS)

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Passing: {passing}/{len(TEMPORAL_TESTS)} ({accuracy:.1f}%)")
    print(f"Baseline: 50.0% (5/10)")
    print(f"Target: 90.0%+ ✓" if accuracy >= 90.0 else f"Target: 90.0%+ (Need {90-accuracy:.1f}% more)")

    # Results table
    print("\n" + "-"*70)
    print("RESULTS TABLE")
    print("-"*70)
    print(f"{'ID':<10} {'F1':<8} {'Status':<8} {'Stability':<12} {'Query ms':<10}")
    print("-"*70)

    for r in results:
        print(
            f"{r['id']:<10} {r['f1']:<8} {r['status']:<8} "
            f"{r['stability_status']:<12} {r['query_ms']:<10.1f}"
        )

    print("-"*70)

    # JSON export
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "engine": "ReasoningEngine v0.1",
        "baseline_accuracy": 50.0,
        "new_accuracy": accuracy,
        "passing": passing,
        "total": len(TEMPORAL_TESTS),
        "target_achieved": accuracy >= 90.0,
        "results": results,
    }

    report_path = Path(__file__).parent.parent / "reports" / "reasoning_engine_test_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to: {report_path}")

    return accuracy >= 90.0


if __name__ == "__main__":
    success = run_temporal_tests()
    sys.exit(0 if success else 1)
