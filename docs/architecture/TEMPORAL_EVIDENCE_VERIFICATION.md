# Temporal Evidence Verification Layer

TheHypoKosh should not treat timestamps as the only form of time. The correct principle is:

> Temporal truth needs temporal evidence, not always exact timestamps.

This layer verifies whether LLM-Kosh Verify can distinguish:

- exact clock/calendar timestamps;
- approximate dates;
- relative order, such as `A before B`;
- version order, such as `v0.1 < v0.2`;
- causal order, such as `A causes B`, therefore `A before B`;
- unknown temporal state requiring abstention on time-sensitive questions.

## What it proves

The verification suite proves three bounded claims:

1. Exact validity windows are necessary for supersession questions such as “what was true in February vs May?”
2. If timestamps collapse to fallback ingestion time, temporal truth is lost or ambiguous.
3. Data without explicit timestamps can still be usable if it carries temporal evidence such as relative, versioned, or causal order.

## New module

```text
llm_kosh/engine/reasoning/temporal_evidence.py
```

Key types:

```text
TemporalStatus: EXACT | APPROXIMATE | RELATIVE | VERSIONED | INFERRED | UNKNOWN
TemporalPrecision: SECOND | DAY | MONTH | YEAR | VERSION | ORDER_ONLY | UNKNOWN
TemporalSource: METADATA | CONTENT | CAUSAL_INFERENCE | VERSION_ORDER | USER_ASSERTION | DEFAULT_NOW | UNKNOWN
TemporalConstraint: subject relation object with confidence and source
TemporalEvidence: timestamp-generalised temporal evidence object
TemporalEvidenceEngine: extractor/auditor for temporal evidence quality
```

## Run

```bash
python -m pytest -q tests/test_reasoning_temporal_evidence_need.py
python scripts/run_temporal_evidence_verification.py
```

Outputs:

```text
reports/temporal_evidence/TEMPORAL_EVIDENCE_AUDIT.md
reports/temporal_evidence/temporal_evidence_verification.json
```

## Design implication

Future ingestion should avoid forcing missing dates into fake exact timestamps. Instead it should store:

```json
{
  "status": "RELATIVE",
  "precision": "ORDER_ONLY",
  "constraints": ["config_change BEFORE parser_failure"],
  "confidence": 0.72,
  "source": "CAUSAL_INFERENCE"
}
```

This makes the system less brittle and more human-like: it can reason with ordering even when exact dates are unavailable.
