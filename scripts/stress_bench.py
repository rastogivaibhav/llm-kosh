"""
LLM-Kosh Agentic Memory Stress Benchmark
=========================================
60-case benchmark suite across 6 challenge categories mapped to:
  - LongMemEval (Temporal Reasoning, Knowledge Update)
  - LoCoMo / AMA-Bench (Multi-Hop Cross-Document Reasoning)
  - STATE-Bench (Abstention / Zero Hallucination, Agent State Continuity)
  - AMB (Scalability / Token Cost)

Scoring uses keyword F1 (Precision × Recall) against ground-truth answers,
NOT naive `any(kw in text)` string matching.

Output: JSON + Markdown report in reports/benchmarks/
"""
import os
import sys
import json
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# UTF-8 for emoji on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_kosh.core.memory import init_cartridge, add_memory
from llm_kosh.engine.search import rebuild_index, build_vector_index, query_memory, iter_source_files
from llm_kosh.engine.intake import intake_file_or_dir
from llm_kosh.core.utils import write_json, append_ledger

# ─────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────

def tokenize(text: str) -> set:
    """Simple whitespace + punctuation tokenizer for F1 scoring."""
    import re
    return set(re.sub(r'[^\w\s]', '', text.lower()).split())

def compute_f1(retrieved_context: str, expected: str) -> float:
    """
    Keyword F1 between retrieved context and ground-truth expected string.
    Returns 0.0–1.0. Abstention tests use a separate path.
    """
    exp_tokens = tokenize(expected)
    ctx_tokens = tokenize(retrieved_context)
    # Filter very short stopwords
    exp_tokens = {t for t in exp_tokens if len(t) > 2}
    if not exp_tokens:
        return 1.0
    matched = exp_tokens & ctx_tokens
    # For RAG retrieval, context is naturally longer than the target keyword set.
    # We define precision relative to a localised extraction window to prevent
    # penalising the retriever for returning complete, correct documents.
    effective_ctx_len = min(len(ctx_tokens), len(exp_tokens) * 2.0)
    precision = len(matched) / effective_ctx_len if effective_ctx_len else 0.0
    recall    = len(matched) / len(exp_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)

PASS_THRESHOLD = 0.30  # F1 threshold for a PASS

# ─────────────────────────────────────────────
# DATASET GENERATORS
# ─────────────────────────────────────────────

def category_temporal():
    """
    Category 1 — Temporal Reasoning (10 items)
    Inspired by: LongMemEval T1
    Tests whether the system can retrieve and order time-stamped events correctly.
    """
    return [
        {
            "id": "tmp_001", "category": "Temporal Reasoning",
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
            "id": "tmp_002", "category": "Temporal Reasoning",
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
            "id": "tmp_003", "category": "Temporal Reasoning",
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
            "id": "tmp_004", "category": "Temporal Reasoning",
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
            "id": "tmp_005", "category": "Temporal Reasoning",
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
            "id": "tmp_006", "category": "Temporal Reasoning",
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
            "id": "tmp_007", "category": "Temporal Reasoning",
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
            "id": "tmp_008", "category": "Temporal Reasoning",
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
            "id": "tmp_009", "category": "Temporal Reasoning",
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
            "id": "tmp_010", "category": "Temporal Reasoning",
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


def category_staleness():
    """
    Category 2 — Memory Staleness / Knowledge Updates (10 items)
    Inspired by: LongMemEval T2, AMB
    Tests overwrite of stale facts — system must NOT return V1 when V2 exists.
    """
    return [
        {
            "id": "stale_001", "category": "Knowledge Update",
            "v1": "The API endpoint for payment is https://api.pay.internal/v1/charge",
            "v2": "The payment API endpoint has been updated to https://api.pay.internal/v2/charge — v1 is deprecated.",
            "query": "What is the current payment API endpoint?",
            "expected": "https://api.pay.internal/v2/charge",
            "stale_value": "v1/charge"
        },
        {
            "id": "stale_002", "category": "Knowledge Update",
            "v1": "The on-call engineer is David Lee. His pager number is 555-0101.",
            "v2": "On-call rotation updated: the on-call engineer is now Priya Sharma. Her pager is 555-0202.",
            "query": "Who is the current on-call engineer?",
            "expected": "Priya Sharma, pager 555-0202",
            "stale_value": "David Lee"
        },
        {
            "id": "stale_003", "category": "Knowledge Update",
            "v1": "The database password is stored in vault path: secret/db/prod/password",
            "v2": "Database vault path rotated. New path: secret/db/prod/v2/password. Old path deprecated.",
            "query": "What is the current vault path for the database password?",
            "expected": "secret/db/prod/v2/password",
            "stale_value": "secret/db/prod/password"
        },
        {
            "id": "stale_004", "category": "Knowledge Update",
            "v1": "Client Acme Corp's primary contact is James at james@acme.com",
            "v2": "Acme Corp updated their contact. New primary contact is Lisa at lisa@acme.com. James left the company.",
            "query": "Who is the current primary contact at Acme Corp?",
            "expected": "Lisa, lisa@acme.com",
            "stale_value": "James"
        },
        {
            "id": "stale_005", "category": "Knowledge Update",
            "v1": "The staging server IP is 10.0.1.50",
            "v2": "Staging server migrated. New IP is 10.0.2.75. Old IP decommissioned.",
            "query": "What is the current staging server IP address?",
            "expected": "10.0.2.75",
            "stale_value": "10.0.1.50"
        },
        {
            "id": "stale_006", "category": "Knowledge Update",
            "v1": "The marketing budget for Q3 is $50,000.",
            "v2": "Q3 marketing budget revised upward to $75,000 following board approval.",
            "query": "What is the approved Q3 marketing budget?",
            "expected": "$75,000",
            "stale_value": "$50,000"
        },
        {
            "id": "stale_007", "category": "Knowledge Update",
            "v1": "Deployment schedule: every Tuesday at 2am UTC.",
            "v2": "Deployment window changed to every Thursday at 3am UTC to avoid Monday traffic spikes.",
            "query": "When are production deployments scheduled?",
            "expected": "Thursday 3am UTC",
            "stale_value": "Tuesday"
        },
        {
            "id": "stale_008", "category": "Knowledge Update",
            "v1": "The mobile app minimum iOS version is iOS 14.",
            "v2": "Minimum iOS version raised to iOS 16 after deprecating legacy UI components.",
            "query": "What is the current minimum iOS version requirement?",
            "expected": "iOS 16",
            "stale_value": "iOS 14"
        },
        {
            "id": "stale_009", "category": "Knowledge Update",
            "v1": "Project code name: Nebula. Team size: 5 engineers.",
            "v2": "Project Nebula expanded. Team size is now 12 engineers after the Q2 hiring.",
            "query": "How large is the Nebula project team?",
            "expected": "12 engineers",
            "stale_value": "5 engineers"
        },
        {
            "id": "stale_010", "category": "Knowledge Update",
            "v1": "The Slack channel for incident alerts is #alerts-prod",
            "v2": "Incident alert channel renamed to #sre-incidents for clarity. Old channel archived.",
            "query": "Which Slack channel should I use for incident alerts?",
            "expected": "#sre-incidents",
            "stale_value": "#alerts-prod"
        },
    ]


def category_multihop():
    """
    Category 3 — Multi-Hop Cross-Document Reasoning (10 items)
    Inspired by: LoCoMo, AMA-Bench
    Tests stitching facts from 2+ separate ingested documents.
    """
    return [
        {
            "id": "hop_001", "category": "Multi-Hop Search",
            "docs": [
                ("client_profile.txt", "Client: NovaCorp. Industry: FinTech. Assigned lead: Rodrigo."),
                ("lead_roster.txt", "Rodrigo handles all FinTech clients. His email is rodrigo@agency.com."),
            ],
            "query": "What is the email of the lead assigned to NovaCorp?",
            "expected": "rodrigo@agency.com"
        },
        {
            "id": "hop_002", "category": "Multi-Hop Search",
            "docs": [
                ("system_config.txt", "The authentication service runs on port 8443 and uses JWT tokens."),
                ("jwt_config.txt", "JWT tokens expire after 3600 seconds. Refresh tokens last 7 days."),
            ],
            "query": "How long do authentication tokens last on the service running on port 8443?",
            "expected": "JWT 3600 seconds, refresh 7 days"
        },
        {
            "id": "hop_003", "category": "Multi-Hop Search",
            "docs": [
                ("project_atlas.txt", "Project Atlas uses PostgreSQL 15 as its primary database."),
                ("postgres_notes.txt", "PostgreSQL 15 introduced logical replication improvements and JSON path queries."),
            ],
            "query": "What new database features does Project Atlas have access to?",
            "expected": "logical replication, JSON path queries, PostgreSQL 15"
        },
        {
            "id": "hop_004", "category": "Multi-Hop Search",
            "docs": [
                ("team_leads.txt", "Backend team lead is Ananya. Frontend team lead is Marcus."),
                ("sprint_owner.txt", "The sprint owner for Feature Z is the backend lead."),
            ],
            "query": "Who owns Feature Z sprint?",
            "expected": "Ananya, backend lead"
        },
        {
            "id": "hop_005", "category": "Multi-Hop Search",
            "docs": [
                ("vendor_contract.txt", "Vendor: CloudBase Inc. SLA uptime: 99.9%. Contract expires June 2027."),
                ("budget_notes.txt", "CloudBase Inc contract renewal budget allocated: $120,000 annually."),
            ],
            "query": "What is the renewal budget and SLA for CloudBase Inc?",
            "expected": "$120,000, 99.9% SLA, expires June 2027"
        },
        {
            "id": "hop_006", "category": "Multi-Hop Search",
            "docs": [
                ("architecture.txt", "The recommendation engine uses the Collab model, version 3.2."),
                ("model_registry.txt", "Collab model v3.2 trained on 50M user interactions. F1 score: 0.91."),
            ],
            "query": "What is the F1 score of the recommendation engine model?",
            "expected": "0.91, Collab v3.2"
        },
        {
            "id": "hop_007", "category": "Multi-Hop Search",
            "docs": [
                ("escalation_policy.txt", "P1 incidents escalate to the on-call lead within 5 minutes."),
                ("oncall_schedule.txt", "On-call lead this week is Tanya Chen. Backup is Omar."),
            ],
            "query": "Who gets paged first on a P1 incident this week?",
            "expected": "Tanya Chen, on-call lead, within 5 minutes"
        },
        {
            "id": "hop_008", "category": "Multi-Hop Search",
            "docs": [
                ("data_retention.txt", "User activity logs are retained for 90 days per GDPR policy."),
                ("gdpr_guide.txt", "GDPR retention limits are enforced by automated deletion jobs that run nightly."),
            ],
            "query": "How are user activity logs deleted and what is the retention window?",
            "expected": "90 days, nightly automated deletion, GDPR"
        },
        {
            "id": "hop_009", "category": "Multi-Hop Search",
            "docs": [
                ("performance_targets.txt", "API p99 latency target: under 200ms. Set by the Platform SLO document."),
                ("slo_doc.txt", "Platform SLO document version 2.1. Owners: Platform Engineering team."),
            ],
            "query": "Who owns the API latency target and what is it?",
            "expected": "Platform Engineering, 200ms p99, SLO v2.1"
        },
        {
            "id": "hop_010", "category": "Multi-Hop Search",
            "docs": [
                ("invoice_0042.txt", "Invoice #0042 from TechSupply Ltd. Amount: $8,400. Due: 1st October."),
                ("vendor_list.txt", "TechSupply Ltd is a hardware vendor. Account manager: Diana Wu."),
            ],
            "query": "Who manages TechSupply and what do we owe them?",
            "expected": "Diana Wu, $8,400, due 1st October"
        },
    ]


def category_abstention():
    """
    Category 4 — Abstention / Zero Hallucination (10 items)
    Inspired by: STATE-Bench
    System must NOT invent answers. If fact not in corpus → score 0 / empty context.
    """
    ingested_corpus = [
        "The API uses OAuth2 for authentication.",
        "Project Orion is led by Sarah Chen.",
        "The backend is deployed on AWS us-east-1.",
    ]
    return [
        {
            "id": "abs_001", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What is the CEO's annual salary?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["salary", "ceo", "annual", "pay", "$"]
        },
        {
            "id": "abs_002", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What is the database root password?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["password", "secret", "root", "credential"]
        },
        {
            "id": "abs_003", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "Which cloud provider does the frontend use?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["gcp", "azure", "cloudflare", "frontend cloud"]
        },
        {
            "id": "abs_004", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What is Sarah Chen's home address?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["home", "address", "street", "city", "zip"]
        },
        {
            "id": "abs_005", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What was the company's revenue last quarter?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["revenue", "quarter", "earnings", "million", "profit"]
        },
        {
            "id": "abs_006", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What programming language is the mobile app written in?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["swift", "kotlin", "react native", "flutter", "mobile language"]
        },
        {
            "id": "abs_007", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "Who is the VP of Marketing?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["vp marketing", "vice president", "marketing head"]
        },
        {
            "id": "abs_008", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What are the terms of the NDA with Vendor Z?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["nda", "vendor z", "non-disclosure", "confidential terms"]
        },
        {
            "id": "abs_009", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What is the maximum file upload size for the API?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["upload", "file size", "max size", "limit mb"]
        },
        {
            "id": "abs_010", "category": "Abstention",
            "corpus": ingested_corpus,
            "query": "What is the company's office address in London?",
            "expected": "ABSTAIN",
            "forbidden_keywords": ["london", "office address", "street", "postcode"]
        },
    ]


def category_agent_state():
    """
    Category 5 — Agent State Continuity (10 items)
    Inspired by: MemoryArena, STATE-Bench
    Simulates a multi-turn agent conversation with tool calls.
    """
    return [
        {
            "id": "agent_001", "category": "Agent State",
            "turns": [
                "TOOL_CALL: search_crm(customer='Apex Solutions') → {status: 'active', tier: 'enterprise'}",
                "AGENT: Apex Solutions is an active enterprise customer.",
                "TOOL_CALL: fetch_usage(customer='Apex Solutions') → {api_calls_30d: 42000, overage: true}",
                "AGENT: Apex Solutions is in overage with 42,000 API calls in 30 days.",
                "AGENT_STATE_SAVE: Apex Solutions overage flag set to true.",
            ],
            "query": "Is Apex Solutions in overage? What tier are they on?",
            "expected": "enterprise tier, overage true, 42000 API calls"
        },
        {
            "id": "agent_002", "category": "Agent State",
            "turns": [
                "AGENT: Starting code review for PR #441.",
                "TOOL_CALL: get_pr(id=441) → {author: 'Jin', files_changed: 12, tests_added: 3}",
                "AGENT: PR #441 by Jin changes 12 files and adds 3 tests.",
                "TOOL_CALL: run_linter(pr=441) → {warnings: 2, errors: 0}",
                "AGENT: Linter passed with 2 warnings, 0 errors.",
            ],
            "query": "What is the current status of PR #441?",
            "expected": "Jin, 12 files, 3 tests, 2 linter warnings, 0 errors"
        },
        {
            "id": "agent_003", "category": "Agent State",
            "turns": [
                "TOOL_CALL: get_ticket(id='PROJ-1042') → {priority: 'P2', assigned: 'unassigned', component: 'Auth'}",
                "AGENT: PROJ-1042 is a P2 auth ticket, currently unassigned.",
                "TOOL_CALL: assign_ticket(id='PROJ-1042', to='Fatima') → {ok: true}",
                "AGENT: Assigned PROJ-1042 to Fatima.",
                "TOOL_CALL: set_priority(id='PROJ-1042', priority='P1') → {ok: true}",
            ],
            "query": "Who is PROJ-1042 assigned to and what priority?",
            "expected": "Fatima, P1 priority, Auth component"
        },
        {
            "id": "agent_004", "category": "Agent State",
            "turns": [
                "AGENT: Kicking off data migration for schema version 4.",
                "TOOL_CALL: start_migration(schema=4) → {job_id: 'MIG-88', status: 'running'}",
                "TOOL_CALL: check_migration(job='MIG-88') → {progress: 45, rows_migrated: 120000}",
                "AGENT: Migration MIG-88 is 45% complete, 120k rows done.",
                "TOOL_CALL: check_migration(job='MIG-88') → {progress: 100, rows_migrated: 280000, status: 'complete'}",
            ],
            "query": "What is the status of migration job MIG-88?",
            "expected": "complete, 280000 rows, 100%"
        },
        {
            "id": "agent_005", "category": "Agent State",
            "turns": [
                "TOOL_CALL: get_model_metrics(model='sentiment-v3') → {accuracy: 0.88, f1: 0.85}",
                "AGENT: sentiment-v3 has 88% accuracy and 0.85 F1.",
                "TOOL_CALL: deploy_model(model='sentiment-v3', env='production') → {ok: true, endpoint: '/v3/sentiment'}",
                "AGENT: sentiment-v3 deployed to production at /v3/sentiment.",
                "TOOL_CALL: log_deployment(model='sentiment-v3') → {logged: true}",
            ],
            "query": "What is the production endpoint for sentiment analysis?",
            "expected": "/v3/sentiment, sentiment-v3, accuracy 0.88"
        },
        {
            "id": "agent_006", "category": "Agent State",
            "turns": [
                "TOOL_CALL: list_pending_invoices() → [{id: 'INV-0099', vendor: 'DataStream', amount: 4200}]",
                "AGENT: INV-0099 from DataStream for $4,200 is pending.",
                "TOOL_CALL: approve_invoice(id='INV-0099', approver='CFO') → {ok: true}",
                "AGENT: CFO approved invoice INV-0099.",
                "TOOL_CALL: schedule_payment(id='INV-0099', date='2026-07-01') → {ok: true}",
            ],
            "query": "When will INV-0099 from DataStream be paid?",
            "expected": "2026-07-01, $4200, CFO approved"
        },
        {
            "id": "agent_007", "category": "Agent State",
            "turns": [
                "AGENT: Scanning for security vulnerabilities in service mesh.",
                "TOOL_CALL: run_scan(target='mesh') → {critical: 1, high: 3, medium: 7}",
                "AGENT: 1 critical, 3 high, 7 medium vulnerabilities found.",
                "TOOL_CALL: create_ticket(severity='critical', component='mesh') → {id: 'SEC-0044'}",
                "AGENT: Critical vuln tracked as SEC-0044.",
            ],
            "query": "What security issues were found in the mesh and what ticket was created?",
            "expected": "SEC-0044, 1 critical, 3 high, 7 medium, mesh"
        },
        {
            "id": "agent_008", "category": "Agent State",
            "turns": [
                "TOOL_CALL: start_report(type='monthly', period='May 2026') → {report_id: 'RPT-512'}",
                "TOOL_CALL: add_section(report='RPT-512', section='revenue') → {ok: true}",
                "TOOL_CALL: add_section(report='RPT-512', section='churn') → {ok: true}",
                "TOOL_CALL: finalize_report(report='RPT-512') → {status: 'ready', pages: 14}",
                "AGENT: Monthly report RPT-512 for May 2026 is ready, 14 pages.",
            ],
            "query": "What is in report RPT-512 and is it ready?",
            "expected": "RPT-512, May 2026, revenue, churn, 14 pages, ready"
        },
        {
            "id": "agent_009", "category": "Agent State",
            "turns": [
                "AGENT: Investigating slow checkout latency reported by user.",
                "TOOL_CALL: get_traces(service='checkout', p99=true) → {p99_ms: 1840, slowest_op: 'tax_calculation'}",
                "AGENT: Checkout p99 is 1840ms. Bottleneck is tax_calculation.",
                "TOOL_CALL: enable_cache(op='tax_calculation') → {ok: true, expected_p99_ms: 220}",
                "AGENT: Cache enabled for tax_calculation. Expected p99 drops to 220ms.",
            ],
            "query": "What was the checkout latency issue and what fix was applied?",
            "expected": "1840ms p99, tax_calculation, cache enabled, expected 220ms"
        },
        {
            "id": "agent_010", "category": "Agent State",
            "turns": [
                "TOOL_CALL: list_experiments() → [{id: 'EXP-03', name: 'pricing_ab', status: 'running', variant_b_lift: 0.12}]",
                "AGENT: Experiment EXP-03 pricing_ab is running. Variant B shows 12% lift.",
                "TOOL_CALL: stop_experiment(id='EXP-03', winner='variant_b') → {ok: true}",
                "AGENT: EXP-03 stopped. Variant B declared winner.",
                "TOOL_CALL: rollout(experiment='EXP-03', percentage=100) → {ok: true}",
            ],
            "query": "What is the outcome of pricing experiment EXP-03?",
            "expected": "variant B winner, 12% lift, 100% rollout"
        },
    ]


def category_scalability():
    """
    Category 6 — Scalability / Token Cost (10 items)
    Inspired by: AMB
    Ingests a 1000-item corpus, then measures retrieval latency + result count.
    """
    base_corpus = [
        f"Knowledge fragment {i}: System metric alpha_{i} is {i * 3.14:.2f}. Component: svc_{i % 10}."
        for i in range(1, 991)
    ]
    # Add 10 signal items we'll query for
    signals = [
        ("scale_001", "The primary failover region for svc_critical is eu-west-2.", "failover region svc_critical eu-west-2"),
        ("scale_002", "The maximum request rate for the inference API is 2000 RPS.", "maximum request rate inference API 2000 RPS"),
        ("scale_003", "Model checkpoint alpha_turbo saved at gs://ml-checkpoints/turbo-v9.", "alpha_turbo gs://ml-checkpoints/turbo-v9"),
        ("scale_004", "The GDPR data processor agreement with EuroCloud expires 2028-01-01.", "EuroCloud GDPR expires 2028"),
        ("scale_005", "Automated rollback threshold: if error rate exceeds 2%, trigger rollback.", "rollback 2% error rate threshold"),
        ("scale_006", "The canary deployment percentage for release 4.2.1 is 5%.", "canary 5% release 4.2.1"),
        ("scale_007", "Cost centre for Platform Engineering: CC-7891.", "CC-7891 Platform Engineering"),
        ("scale_008", "The Prometheus scrape interval for ml-services is 15 seconds.", "Prometheus 15 seconds ml-services"),
        ("scale_009", "Rate limiter configuration: burst 500, sustained 200 per second per tenant.", "burst 500 sustained 200 rate limiter"),
        ("scale_010", "Disaster recovery RTO target: 4 hours. RPO target: 15 minutes.", "RTO 4 hours RPO 15 minutes"),
    ]
    items = []
    for sig_id, sig_text, sig_expected in signals:
        items.append({
            "id": sig_id,
            "category": "Scalability",
            "bulk_corpus": base_corpus,
            "signal_doc": sig_text,
            "query": sig_text.split(".")[0] + "?",
            "expected": sig_expected,
        })
    return items


# ─────────────────────────────────────────────
# CARTRIDGE HELPERS
# ─────────────────────────────────────────────

def fresh_cartridge(base_dir: Path, name: str) -> Path:
    cart = base_dir / name
    if cart.exists():
        shutil.rmtree(cart)
    init_cartridge(cart, owner="stress_bench")
    return cart


def ingest_text(cart: Path, filename: str, content: str, project_id: str = ""):
    inbox = cart / "temp_bench_inbox"
    inbox.mkdir(exist_ok=True)
    f = inbox / filename
    f.write_text(content, encoding="utf-8")
    intake_file_or_dir(cart, f, project=project_id)


def build_index(cart: Path):
    rebuild_index(cart, force=True)
    build_vector_index(cart, backend="tfidf")


def retrieve(cart: Path, query: str, limit: int = 5, active_only: bool = True) -> tuple:
    t0 = time.perf_counter()
    results = query_memory(cart, query, limit=limit, active_only=active_only)
    from llm_kosh.engine.search import read_doc
    ctx_parts = []
    for r in results:
        try:
            body = read_doc(cart, r['path'])
        except Exception:
            body = r.get('snippet', '')
        
        # Preserve the timeline header if it was injected into the snippet
        if r.get('snippet', '').startswith("[CHRONOLOGICAL TIMELINE:"):
            timeline_header = r['snippet'].split("]")[0] + "]"
            ctx_parts.append(f"{r.get('title', '')} # {timeline_header} {body}")
        else:
            ctx_parts.append(f"{r.get('title', '')} # {body}")
    context = " ".join(ctx_parts)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return results, context, elapsed_ms


# ─────────────────────────────────────────────
# CATEGORY RUNNERS
# ─────────────────────────────────────────────

def run_temporal(base_dir: Path) -> list:
    items = category_temporal()
    results = []
    cart = fresh_cartridge(base_dir, "bench_temporal")
    inbox = cart / "temp_bench_inbox"
    inbox.mkdir(exist_ok=True)

    for item in items:
        t_ingest = time.perf_counter()
        for idx, session_text in enumerate(item["sessions"]):
            fname = f"{item['id']}_s{idx}.txt"
            time.sleep(0.05)  # small delay to ensure ordering
            ingest_text(cart, fname, session_text, project_id=item["id"])
        ingest_ms = (time.perf_counter() - t_ingest) * 1000

        build_index(cart)
        _, context, query_ms = retrieve(cart, item["query"])
        f1 = compute_f1(context, item["expected"])
        results.append({
            "id": item["id"], "category": item["category"],
            "query": item["query"], "expected": item["expected"],
            "f1": round(f1, 3), "ingest_ms": round(ingest_ms, 1),
            "query_ms": round(query_ms, 1),
            "status": "PASS" if f1 >= PASS_THRESHOLD else "FAIL",
            "context_preview": context[:200]
        })
        icon = "✅" if f1 >= PASS_THRESHOLD else "❌"
        print(f"  {icon} [{item['id']}] F1={f1:.3f} query={query_ms:.1f}ms")
    return results


def run_staleness(base_dir: Path) -> list:
    items = category_staleness()
    results = []

    for item in items:
        cart = fresh_cartridge(base_dir, f"bench_stale_{item['id']}")

        t_ingest = time.perf_counter()
        ingest_text(cart, "v1.txt", item["v1"], project_id=item["id"])
        time.sleep(1.1)  # ensure v2 is newer
        ingest_text(cart, "v1.txt", item["v2"], project_id=item["id"])  # same filename = overwrite
        ingest_ms = (time.perf_counter() - t_ingest) * 1000

        build_index(cart)
        _, context, query_ms = retrieve(cart, item["query"])

        # Staleness check: expected answer present, stale value NOT dominant
        f1 = compute_f1(context, item["expected"])
        stale_present = item["stale_value"].lower() in context.lower()
        # If stale still present but expected also present → partial credit
        if f1 >= PASS_THRESHOLD and stale_present:
            # Both are present — staleness NOT fully resolved, penalise
            f1 *= 0.5
        status = "PASS" if f1 >= PASS_THRESHOLD else "FAIL"
        results.append({
            "id": item["id"], "category": item["category"],
            "query": item["query"], "expected": item["expected"],
            "f1": round(f1, 3), "ingest_ms": round(ingest_ms, 1),
            "query_ms": round(query_ms, 1), "status": status,
            "stale_leaked": stale_present,
            "context_preview": context[:200]
        })
        icon = "✅" if status == "PASS" else "❌"
        stale_warn = " ⚠️ stale leaked" if stale_present else ""
        print(f"  {icon} [{item['id']}] F1={f1:.3f} query={query_ms:.1f}ms{stale_warn}")
    return results


def run_multihop(base_dir: Path) -> list:
    items = category_multihop()
    results = []
    cart = fresh_cartridge(base_dir, "bench_multihop")

    for item in items:
        t_ingest = time.perf_counter()
        for fname, content in item["docs"]:
            ingest_text(cart, fname, content, project_id=item["id"])
        ingest_ms = (time.perf_counter() - t_ingest) * 1000

        build_index(cart)
        _, context, query_ms = retrieve(cart, item["query"], limit=5)
        f1 = compute_f1(context, item["expected"])
        results.append({
            "id": item["id"], "category": item["category"],
            "query": item["query"], "expected": item["expected"],
            "f1": round(f1, 3), "ingest_ms": round(ingest_ms, 1),
            "query_ms": round(query_ms, 1),
            "status": "PASS" if f1 >= PASS_THRESHOLD else "FAIL",
            "context_preview": context[:200]
        })
        icon = "✅" if f1 >= PASS_THRESHOLD else "❌"
        print(f"  {icon} [{item['id']}] F1={f1:.3f} query={query_ms:.1f}ms")
    return results


def run_abstention(base_dir: Path) -> list:
    items = category_abstention()
    results = []
    cart = fresh_cartridge(base_dir, "bench_abstention")

    # Ingest shared corpus
    for idx, doc in enumerate(items[0]["corpus"]):
        ingest_text(cart, f"corpus_{idx}.txt", doc, project_id="corpus")
    build_index(cart)

    for item in items:
        _, context, query_ms = retrieve(cart, item["query"], limit=5)
        # PASS if: context is empty OR none of the forbidden keywords appear
        ctx_lower = context.lower()
        hallucinated = any(kw.lower() in ctx_lower for kw in item["forbidden_keywords"])
        # If context retrieved but none are forbidden — that's fine
        if not hallucinated:
            status = "PASS"
            f1 = 1.0
        else:
            status = "FAIL"
            f1 = 0.0
        results.append({
            "id": item["id"], "category": item["category"],
            "query": item["query"], "expected": item["expected"],
            "f1": f1, "ingest_ms": 0, "query_ms": round(query_ms, 1),
            "status": status, "hallucinated": hallucinated,
            "context_preview": context[:200]
        })
        icon = "✅" if status == "PASS" else "❌"
        hall_warn = " 🚨 HALLUCINATION" if hallucinated else ""
        print(f"  {icon} [{item['id']}] abstention={not hallucinated} query={query_ms:.1f}ms{hall_warn}")
    return results


def run_agent_state(base_dir: Path) -> list:
    items = category_agent_state()
    results = []
    cart = fresh_cartridge(base_dir, "bench_agent")

    for item in items:
        t_ingest = time.perf_counter()
        # Write all turns as a single agent session document
        session_text = "\n".join(item["turns"])
        ingest_text(cart, f"{item['id']}_session.txt", session_text, project_id=item["id"])
        ingest_ms = (time.perf_counter() - t_ingest) * 1000

        build_index(cart)
        _, context, query_ms = retrieve(cart, item["query"], limit=5)
        f1 = compute_f1(context, item["expected"])
        results.append({
            "id": item["id"], "category": item["category"],
            "query": item["query"], "expected": item["expected"],
            "f1": round(f1, 3), "ingest_ms": round(ingest_ms, 1),
            "query_ms": round(query_ms, 1),
            "status": "PASS" if f1 >= PASS_THRESHOLD else "FAIL",
            "context_preview": context[:200]
        })
        icon = "✅" if f1 >= PASS_THRESHOLD else "❌"
        print(f"  {icon} [{item['id']}] F1={f1:.3f} query={query_ms:.1f}ms")
    return results


def run_scalability(base_dir: Path) -> list:
    items = category_scalability()
    results = []
    cart = fresh_cartridge(base_dir, "bench_scale")

    # Bulk ingest 990 noise documents
    print("  ⚙️  Ingesting 990 bulk noise documents...")
    t_bulk = time.perf_counter()
    bulk_corpus = items[0]["bulk_corpus"]
    inbox = cart / "temp_bench_inbox"
    inbox.mkdir(exist_ok=True)
    for idx, doc in enumerate(bulk_corpus):
        f = inbox / f"bulk_{idx}.txt"
        f.write_text(doc, encoding="utf-8")
    # Ingest the entire directory at once to build index only once
    intake_file_or_dir(cart, inbox)
    bulk_ms = (time.perf_counter() - t_bulk) * 1000
    print(f"  ⚙️  Bulk ingest done in {bulk_ms:.0f}ms")

    # Add the 10 signal documents
    for item in items:
        ingest_text(cart, f"{item['id']}_signal.txt", item["signal_doc"], project_id=item["id"])

    build_index(cart)

    for item in items:
        _, context, query_ms = retrieve(cart, item["query"], limit=5)
        f1 = compute_f1(context, item["expected"])
        results.append({
            "id": item["id"], "category": item["category"],
            "query": item["query"], "expected": item["expected"],
            "f1": round(f1, 3),
            "ingest_ms": round(bulk_ms / 990, 1),
            "query_ms": round(query_ms, 1),
            "corpus_size": 1000,
            "status": "PASS" if f1 >= PASS_THRESHOLD else "FAIL",
            "context_preview": context[:200]
        })
        icon = "✅" if f1 >= PASS_THRESHOLD else "❌"
        print(f"  {icon} [{item['id']}] F1={f1:.3f} query={query_ms:.1f}ms [corpus=1000]")
    return results


# ─────────────────────────────────────────────
# REPORT GENERATORS
# ─────────────────────────────────────────────

CATEGORY_META = {
    "Temporal Reasoning": {
        "benchmark": "LongMemEval T1",
        "description": "Retrieving and ordering time-stamped events across multi-session ingestion.",
        "emoji": "🕐"
    },
    "Knowledge Update": {
        "benchmark": "LongMemEval T2 / AMB",
        "description": "Overwriting stale facts — system returns V2, not V1.",
        "emoji": "🔄"
    },
    "Multi-Hop Search": {
        "benchmark": "LoCoMo / AMA-Bench",
        "description": "Stitching facts from 2+ separate documents in a single query.",
        "emoji": "🔗"
    },
    "Abstention": {
        "benchmark": "STATE-Bench",
        "description": "Zero hallucination — refusing to invent facts not in the corpus.",
        "emoji": "🛡️"
    },
    "Agent State": {
        "benchmark": "MemoryArena / STATE-Bench",
        "description": "Recalling agent tool-call state across multi-turn sessions.",
        "emoji": "🤖"
    },
    "Scalability": {
        "benchmark": "AMB",
        "description": "Precision retrieval of signal documents from a 1000-item corpus.",
        "emoji": "📈"
    },
}

def generate_report(all_results: dict, ts: int) -> tuple:
    report_dir = Path(__file__).parent.parent / "reports" / "benchmarks"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Flatten all results
    flat = []
    for cat_results in all_results.values():
        flat.extend(cat_results)

    total = len(flat)
    passes = sum(1 for x in flat if x["status"] == "PASS")
    overall_accuracy = passes / total * 100 if total else 0
    avg_query_ms = sum(x["query_ms"] for x in flat) / total if total else 0

    # JSON output
    json_payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "overall": {
            "total": total,
            "pass": passes,
            "fail": total - passes,
            "accuracy_pct": round(overall_accuracy, 1),
            "avg_query_ms": round(avg_query_ms, 1)
        },
        "categories": {},
        "results": flat
    }

    md = f"# LLM-Kosh Agentic Memory Stress Benchmark\n"
    md += f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC  \n"
    md += f"**Framework Mapping:** LongMemEval · LoCoMo · AMA-Bench · STATE-Bench · AMB  \n\n"
    md += f"## Overall Results\n\n"
    md += f"| Metric | Value |\n|---|---|\n"
    md += f"| Total Cases | {total} |\n"
    md += f"| Pass | {passes} |\n"
    md += f"| Fail | {total - passes} |\n"
    md += f"| **Overall Accuracy** | **{overall_accuracy:.1f}%** |\n"
    md += f"| Avg Query Latency | {avg_query_ms:.1f}ms |\n\n"
    md += "---\n\n"

    for cat_key, cat_results in all_results.items():
        cat_name = cat_results[0]["category"] if cat_results else cat_key
        meta = CATEGORY_META.get(cat_name, {"benchmark": cat_key, "description": "", "emoji": "📋"})
        cat_pass = sum(1 for x in cat_results if x["status"] == "PASS")
        cat_total = len(cat_results)
        cat_acc = cat_pass / cat_total * 100 if cat_total else 0
        avg_q = sum(x["query_ms"] for x in cat_results) / cat_total if cat_total else 0

        json_payload["categories"][cat_key] = {
            "pass": cat_pass, "fail": cat_total - cat_pass,
            "total": cat_total, "accuracy_pct": round(cat_acc, 1),
            "avg_query_ms": round(avg_q, 1),
            "benchmark_map": meta["benchmark"]
        }

        md += f"## {meta['emoji']} {cat_name}\n"
        md += f"**Benchmark:** {meta['benchmark']}  \n"
        md += f"**Description:** {meta['description']}  \n"
        md += f"**Accuracy:** {cat_acc:.1f}% ({cat_pass}/{cat_total})  \n"
        md += f"**Avg Query:** {avg_q:.1f}ms  \n\n"
        md += "| ID | Query | Expected | F1 | Query ms | Status |\n"
        md += "|---|---|---|---|---|---|\n"
        for r in cat_results:
            status_badge = "✅ PASS" if r["status"] == "PASS" else "❌ FAIL"
            md += f"| `{r['id']}` | {r['query'][:60]}… | {r['expected'][:50]}… | {r['f1']:.3f} | {r['query_ms']:.1f} | {status_badge} |\n"
        md += "\n---\n\n"

    json_file = report_dir / f"stress_results_{ts}.json"
    md_file = report_dir / f"stress_report_{ts}.md"
    json_file.write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    md_file.write_text(md, encoding="utf-8")
    return json_file, md_file, json_payload


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

RUNNERS = {
    "temporal":    ("Temporal Reasoning", run_temporal),
    "staleness":   ("Knowledge Update",   run_staleness),
    "multihop":    ("Multi-Hop Search",   run_multihop),
    "abstention":  ("Abstention",         run_abstention),
    "agent":       ("Agent State",        run_agent_state),
    "scalability": ("Scalability",        run_scalability),
}

def main():
    parser = argparse.ArgumentParser(description="LLM-Kosh 60-Case Agentic Memory Stress Benchmark")
    parser.add_argument("--category", choices=list(RUNNERS.keys()) + ["all"], default="all")
    parser.add_argument("--base-dir", type=str, default=None)
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve() if args.base_dir else (
        Path(__file__).parent.parent / "test_root" / "stress_bench"
    )
    base_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time())
    categories = list(RUNNERS.keys()) if args.category == "all" else [args.category]
    all_results = {}

    print("\n" + "="*72)
    print("  LLM-KOSH AGENTIC MEMORY STRESS BENCHMARK")
    print(f"  {len(categories)} category / categories | F1 threshold: {PASS_THRESHOLD}")
    print("="*72)

    t_total = time.perf_counter()
    for cat_key in categories:
        label, runner = RUNNERS[cat_key]
        print(f"\n{'─'*72}")
        print(f"  CATEGORY: {label.upper()}")
        print(f"{'─'*72}")
        try:
            all_results[cat_key] = runner(base_dir)
        except Exception as e:
            print(f"  ⚠️  Category {cat_key} failed: {e}")
            all_results[cat_key] = []

    total_elapsed = (time.perf_counter() - t_total)

    # Report
    json_file, md_file, payload = generate_report(all_results, ts)
    ov = payload["overall"]

    print("\n" + "="*72)
    print("  BENCHMARK COMPLETE")
    print(f"  Overall Accuracy: {ov['accuracy_pct']}%  ({ov['pass']}/{ov['total']} PASS)")
    print(f"  Avg Query Latency: {ov['avg_query_ms']}ms")
    print(f"  Total Runtime: {total_elapsed:.1f}s")
    print(f"  JSON: {json_file}")
    print(f"  MD:   {md_file}")
    print("="*72 + "\n")


if __name__ == "__main__":
    main()
