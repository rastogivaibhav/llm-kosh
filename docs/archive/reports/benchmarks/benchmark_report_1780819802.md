# LLM-Kosh Benchmark Evaluation Report
Generated At: 2026-06-07 09:10:02
Cartridge Root: `C:\Users\vrast\Documents\Projects\test\ai_memory_cartridge_v1.0\test_root\benchmarks`

## Dataset: LONGMEMEVAL
- **Total items:** 4
- **Pass:** 4 | **Fail:** 0
- **Accuracy:** 100.0%

| ID | Category | Query | Expected Answer | Status | Ingest (ms) | Search (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lme_001` | Factual Retrieval | What caching provider does SelectiveOS use and who is the lead developer? | *Redis is the caching provider, and Sarah is the lead developer.* | **PASS** | 2648.4 | 17.4 |
| `lme_002` | Knowledge Update | What is my current backup email address? | *security@my-firm.com* | **PASS** | 1703.0 | 15.2 |
| `lme_003` | Temporal Reasoning | List the three features (auth, search, payment) in the chronological order they were deployed. | *1. Authentication layer (Monday), 2. Search engine features (Wednesday), 3. Payment portal integration (Friday).* | **PASS** | 535.6 | 14.1 |
| `lme_004` | Abstention | What is client A's target hosting platform? | *Abstain / Information not found in context* | **PASS** | 202.0 | 20.5 |

---

## Dataset: LOCOMO
- **Total items:** 2
- **Pass:** 2 | **Fail:** 0
- **Accuracy:** 100.0%

| ID | Category | Query | Expected Answer | Status | Ingest (ms) | Search (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `locomo_001` | Event Summarization | Summarize the schedule dependencies and reviews needed for the product launch. | *Design assets will be completed on Thursday, and Sarah must review the landing page before the deployment on Friday.* | **PASS** | 160.3 | 17.3 |
| `locomo_002` | Multi-hop Reasoning | Why is John focusing on database scaling for the sprint? | *Because client SelectiveCorp reported a timeout issue last week and is moving to production next month.* | **PASS** | 178.7 | 13.8 |

---

