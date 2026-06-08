# Kosh Verify — Temporal-Causal Provenance Dataset Evaluation

This package adds a deterministic, non-LLM evaluation harness for two uploaded ITSM datasets:

- `data/raw/archive_4_incident_event_log.zip`: ServiceNow-style incident event log.
- `data/raw/archive_5_itsm_sla_dataset.zip`: ITSM ticket/SLA dataset.

The test is designed to validate whether Kosh Verify / TheHypoKosh can model operational data as:

- temporal facts,
- state-validity windows,
- lifecycle/progression edges,
- supersession edges,
- change/problem/RFC provenance links,
- SLA joint-causality hyperedges,
- no-evidence abstention,
- dialectic convergence/opposition.

## Run the evaluation

From the package root:

```bash
PYTHONPATH=. python scripts/run_temporal_causal_provenance_dataset_eval.py \
  --archive4 data/raw/archive_4_incident_event_log.zip \
  --archive5 data/raw/archive_5_itsm_sla_dataset.zip \
  --incident-limit 100 \
  --ticket-limit 100 \
  --out reports/kosh_verify_temporal_causal_provenance \
  --cartridge .tmp/temporal_causal_provenance_cartridge
```

Run the pytest wrapper:

```bash
PYTHONPATH=. pytest -q tests/test_kosh_verify_temporal_causal_provenance_datasets.py
```

## What the current run achieved

The shipped report shows:

- full dataset audit across 241,712 rows,
- representative Kosh ingestion of 100 incidents and 100 SLA tickets,
- 1,667 facts,
- 2,522 binary edges,
- 200 hyperedges,
- 6/6 verification checks passed.

See:

- `reports/kosh_verify_temporal_causal_provenance/TEMPORAL_CAUSAL_PROVENANCE_DATASET_EVAL_REPORT.md`
- `reports/kosh_verify_temporal_causal_provenance/temporal_causal_provenance_eval_results.json`

## Honest interpretation

This validates the deterministic Kosh memory/reasoning kernel on real ITSM-shaped data. It does not validate LLM extraction, because no LLM was needed for this test. Archive 4 is excellent for incident state history; Archive 5 is strong for SLA timing, but all SLA labels are `Met`, so future evaluation should add breach cases.
