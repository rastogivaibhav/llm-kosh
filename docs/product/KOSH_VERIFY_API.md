# Kosh Verify API

## Purpose

`llm_kosh.verify` is the product-facing API for the current LLM-Kosh / TheHypoKosh codebase. It wraps the existing reasoning engine into a simple verifier interface.

## Import

```python
from llm_kosh.verify import KoshVerify, seed_incident_cartridge
```

## Create a verifier

```python
kv = KoshVerify("./my-cartridge")
```

## Add facts

```python
fact_id = kv.add_fact(
    content="Deployment v4.2 started before customer impact.",
    valid_from=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
    confidence=0.9,
    source="deployment_note",
)
```

## Add edges

```python
edge_id = kv.add_edge(
    source_id=deployment_fact,
    target_id=memory_leak_fact,
    edge_type="CAUSES",
    valid_from=datetime(2026, 5, 1, 12, 10, tzinfo=timezone.utc),
    origin="OBSERVED",
    role="MECHANISTIC",
    evidence_source="metrics",
)
```

## Verify a question

```python
report = kv.verify(
    "Why did checkout fail and what contradicts the explanation?",
    temporal_context="2026-05-01T13:30:00+00:00",
    depth=5,
    dialectic=True,
)
```

## Report fields

- `status`
- `primary_answer`
- `stability_score`
- `abstain`
- `facts`
- `paths`
- `contradictions`
- `inferred_not_discovered`
- `missing_evidence`
- `convergent_summary`
- `opposition_summary`

## Demo

```bash
python scripts/kosh_verify_demo.py
```
