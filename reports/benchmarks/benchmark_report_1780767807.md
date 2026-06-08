# LLM-Kosh Benchmark Evaluation Report
Generated At: 2026-06-06 18:43:27
Cartridge Root: `C:\Users\vrast\Documents\Projects\test\ai_memory_cartridge_v1.0\test_root\benchmarks`

## Dataset: LONGMEMEVAL
- **Total items:** 4
- **Pass:** 4 | **Fail:** 0
- **Accuracy:** 100.0%

| ID | Category | Query | Expected Answer | Status | Ingest (ms) | Search (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lme_001` | Factual Retrieval | What caching provider does SelectiveOS use and who is the lead developer? | *Redis is the caching provider, and Sarah is the lead developer.* | **PASS** | 1862.4 | 11.2 |
| `lme_002` | Knowledge Update | What is my current backup email address? | *security@my-firm.com* | **PASS** | 1342.3 | 9.5 |
| `lme_003` | Temporal Reasoning | List the three features (auth, search, payment) in the chronological order they were deployed. | *1. Authentication layer (Monday), 2. Search engine features (Wednesday), 3. Payment portal integration (Friday).* | **PASS** | 390.0 | 7.4 |
| `lme_004` | Abstention | What is client A's target hosting platform? | *Abstain / Information not found in context* | **PASS** | 106.6 | 10.9 |

---

## Dataset: LOCOMO
- **Total items:** 2
- **Pass:** 2 | **Fail:** 0
- **Accuracy:** 100.0%

| ID | Category | Query | Expected Answer | Status | Ingest (ms) | Search (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `locomo_001` | Event Summarization | Summarize the schedule dependencies and reviews needed for the product launch. | *Design assets will be completed on Thursday, and Sarah must review the landing page before the deployment on Friday.* | **PASS** | 123.0 | 11.8 |
| `locomo_002` | Multi-hop Reasoning | Why is John focusing on database scaling for the sprint? | *Because client SelectiveCorp reported a timeout issue last week and is moving to production next month.* | **PASS** | 133.9 | 13.1 |

---

