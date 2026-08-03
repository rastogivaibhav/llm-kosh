# Reference-first multimodal artifact specification

Status: implementation contract for company-brain schema v2.

## Invariants

1. Local source bytes are not copied by default.
2. `reference` evidence stores an exact canonical path, strong SHA-256
   fingerprint, size, modification time, file identity, type and policy.
3. `snapshot` is explicit and immutable. `managed` means LLM-Kosh is the
   original owner of the bytes.
4. Artifact types describe media; memory types describe meaning.
5. A changed or missing reference is never silently treated as original
   evidence.
6. Retrieval authorizes both memory and evidence before ranking.
7. Context contains precise native locators and typed attachments, never a
   complete source file unless explicitly requested.
8. Parsed text is bounded derived understanding. All caches and indexes are
   disposable projections.

## Contracts

Storage modes: `reference`, `snapshot`, `managed`.

Artifact types: `screenshot`, `image`, `document`, `pdf`, `worksheet`, `csv`,
`html`, `web_read`, `presentation`, `email`, `chat`, `transcript`, `audio`,
`video`, `source_code`, `structured_data`, `plain_text`, `binary`.

Availability states: `available`, `changed`, `unavailable`, `forbidden`,
`invalid`.

A segment references an evidence record and contains a native locator such as
`{"page": 4}`, `{"sheet": "Revenue", "range": "B2:F20"}`,
`{"region": [0.1, 0.2, 0.5, 0.4]}`, `{"dom": "main > article"}` or
`{"lines": [20, 35]}`. Bounded extracted text, parser version and confidence
may accompany the locator.

## Cycle prompts and exit gates

### Cycle 1 — schema and migration

Development prompt: migrate canonical storage to schema v2, add storage mode,
artifact type, fingerprints, availability, parser metadata, trusted exact-file
registrations and evidence segments while preserving v1 evidence.

Validation prompt: prove transactionality, idempotency, mixed v1/v2 reads and
zero blob creation for references.

Exit gate: existing tests pass and reference ingestion stores zero source bytes.

### Cycle 2 — resolver

Development prompt: build a cross-platform exact-reference resolver with
canonical paths, streaming hashes, file identity and changed/missing/forbidden
states.

Validation prompt: exercise traversal, symlinks, rename/delete/change, large
files and reads outside registered references.

Exit gate: only registered canonical files can be read and mutations are
detected before content is returned.

### Cycle 3 — adapters

Development prompt: add bounded adapters for text, CSV, HTML, DOCX, XLSX, PDF
and images using native coordinates; degrade safely when an optional parser is
unavailable.

Validation prompt: cover malformed files, Unicode, formulas, hidden sheets,
image dimensions, PDF pages, HTML headings and strict output limits.

Exit gate: every adapter returns one common inspection contract without
persisting original bytes.

### Cycle 4 — segments and citations

Development prompt: persist deterministic bounded evidence segments with
native locators, extractor provenance and optional text.

Validation prompt: prove deduplication, exact locator round-trips and stale
source warnings.

Exit gate: every memory citation can identify an authorized artifact location.

### Cycle 5 — retrieval and context

Development prompt: compile authorized semantic memories into structured
context with typed artifact attachments, citations, availability and budgets.

Validation prompt: test permission isolation, missing and changed references,
mixed modalities, candidate warnings and context limits.

Exit gate: no unauthorized metadata or unavailable artifact is presented as
verified evidence.

### Cycle 6 — interfaces

Development prompt: add CLI and MCP operations to register, inspect, verify,
segment and explicitly snapshot artifacts. Legacy cartridge migration must
register source files by reference.

Validation prompt: run every operation read-only and capability-gated, test
dry runs, and retain old client compatibility.

Exit gate: reference is the default and snapshot is always explicit.

### Cycle 7 — evaluation

Development prompt: measure storage amplification, citation accuracy,
availability, permission isolation and context efficiency.

Validation prompt: run the full suite and end-to-end examples for all supported
artifact families.

Exit gate: reference-mode copied bytes are zero, all integrity checks pass and
documentation matches the executable interface.
