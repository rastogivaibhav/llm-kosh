# Kosh Verify

Kosh Verify is LLM-Kosh's evidence-aware verification surface for questions whose answer depends on remembered facts, their timing, causal relationships, and provenance.

It is deliberately narrower than a general-purpose fact checker. Kosh Verify does **not** claim to know whether the outside world is true. It answers a different question:

> Given the evidence in this cartridge, what can the agent support, what conflicts with that explanation, what was inferred rather than directly observed, and when should it abstain?

The implementation is local and deterministic for the core verification mechanics. It does not require an LLM to decide temporal validity, traverse causal relationships, label provenance, surface contradictions, identify evidence gaps, or abstain when evidence is absent.

## What a report can contain

A `VerifyReport` can expose:

- the primary answer supported by the cartridge
- stability score and status
- temporal context used for the verification
- supporting facts and causal paths
- contradictions
- inferred-but-not-discovered relationships
- missing evidence
- facts that were discarded or reopened during the reasoning process
- an explicit abstention state when the cartridge cannot support an answer

This is meant to make memory useful **without hiding how the answer was constructed**.

## Try the deterministic incident demo

Use a disposable cartridge because `--demo-seed` writes synthetic incident evidence into the selected root.

```bash
llm-kosh --root ./kosh-demo kosh-verify \
  "Why did checkout fail and what evidence contradicts the explanation?" \
  --when "2026-05-01T13:30:00+00:00" \
  --depth 5 \
  --demo-seed \
  --json
```

For the standalone example, which automatically uses a temporary directory:

```bash
python examples/kosh_verify/incident_demo.py
```

The demo is synthetic and deterministic. It is an executable example of the verification contract, not evidence that Kosh Verify outperforms another memory system.

## Reproduce the acceptance checks

The repository includes a small acceptance harness that validates the public behavior without network calls or an LLM:

```bash
python scripts/kosh_verify_acceptance.py
```

It checks that a seeded evidence set produces a grounded report with causal paths, provenance distinctions and evidence gaps; that the report is serializable; and that an empty cartridge causes an explicit abstention.

These checks are intentionally called **acceptance checks**, not benchmarks. Comparative benchmark claims should only be made from reproducible datasets and published methodology.

## Python API

```python
from pathlib import Path
from llm_kosh.verify import KoshVerify

verifier = KoshVerify(Path("./my-cartridge"))
report = verifier.verify(
    "What caused the incident?",
    temporal_context="2026-05-01T13:30:00+00:00",
    depth=4,
    dialectic=True,
)

print(report.status)
print(report.primary_answer)
print(report.contradictions)
print(report.missing_evidence)
print(report.inferred_not_discovered)
print(verifier.explain_provenance(report))
```

For machine-readable output:

```python
print(report.to_json(indent=2))
```

## Why this belongs in a memory system

Persistent memory changes the failure mode of an agent. A bad answer can disappear after one session; a bad memory can be recalled repeatedly and influence later decisions.

Kosh Verify therefore treats retrieval as more than similarity search. The verification layer preserves distinctions between evidence, inference, contradiction and absence. The intended contract is:

1. do not silently turn inference into observation;
2. do not silently ignore temporal validity;
3. surface material contradictions;
4. expose important missing evidence;
5. abstain when the cartridge cannot support an answer.

## Current boundaries

Kosh Verify is **not**:

- a universal truth oracle
- an internet fact-checking service
- a guarantee that an imported source is itself trustworthy
- a replacement for source authentication, authorization or human review in high-impact decisions
- a claim that every memory in a cartridge should be treated as equally authoritative

The quality of a verification is bounded by the evidence available to the cartridge and the quality of its provenance. LLM-Kosh's intake, review, policy and evidence-reference mechanisms are intended to make those boundaries inspectable rather than invisible.

## Related material

- [Kosh Verify API](product/KOSH_VERIFY_API.md)
- [Product wedge and design intent](product/KOSH_VERIFY_PRODUCT_WEDGE.md)
- [Shared-memory framework-agent verification](product/KOSH_VERIFY_FRAMEWORK_AGENTS_SHARED_MEMORY.md)
- [Multi-agent ServiceNow example](product/KOSH_VERIFY_MULTI_AGENT_SERVICENOW.md)
- [Incident demo](../examples/kosh_verify/incident_demo.py)
- [Product acceptance tests](../tests/test_kosh_verify_product_wedge.py)
- [Temporal/causal provenance dataset tests](../tests/test_kosh_verify_temporal_causal_provenance_datasets.py)
