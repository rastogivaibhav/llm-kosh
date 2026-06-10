---
title: "Knowledge Foundry Feature Registry"
date: 2026-05-27
status: living-document
type: product
---

# Knowledge Foundry Feature Registry

**Version**: 0.1  
**Status**: Living document  
**Update Cadence**: Update whenever features move status, scope changes, or new implementation specs are added.

This is the product source of truth for Knowledge Foundry capabilities. It links features to phase, package area, source requirement, spec, and ADRs.

## 1. Status Values

| Status | Meaning |
|---|---|
| `not-started` | Feature is defined but implementation has not begun. |
| `in-design` | Product/design/spec work is active. |
| `in-progress` | Implementation is active. |
| `implemented` | Code exists and tests/validation are complete. |
| `deployed` | Feature is running in its intended environment. |
| `deferred` | Explicitly out of current phase. |

## 2. Source Documents

| Abbrev | Document |
|---|---|
| PRD | `docs/product/prd-knowledge-foundry.md` |
| DESIGN-LAB | `docs/engineering/design-knowledge-foundry-lab.md` |
| MVP-SPEC | `docs/engineering/specs/spec-mvp-local-index.md` |
| RTM | `docs/project/requirements-traceability.md` |
| ADR | `docs/engineering/adrs/` |
| TEST | `docs/governance/test-plan-mvp-local-index.md`, plus per-feature plans under `docs/governance/test-plan-*.md` |

## 3. MVP Features

| ID | Feature | Description | Phase | Status | Package/Area | Source | Spec | ADR |
|---|---|---|---:|---|---|---|---|---|
| KF-001 | Workspace Initialization | Create local Knowledge Foundry workspace metadata and output locations. | 1 | `implemented` | `source/knowledge_foundry/cli`, `source/knowledge_foundry/registry` | PRD, MVP-SPEC | `spec-root-registry.md` | ADR-0007, ADR-0008 |
| KF-002 | Source Root Registry | Register readable project/doc roots for indexing. | 1 | `implemented` | `source/knowledge_foundry/cli`, `source/knowledge_foundry/registry` | PRD, MVP-SPEC | `spec-root-registry.md` | ADR-0008, ADR-0011 |
| KF-003 | Dedicated Postgres Schema | Store workspaces, roots, documents, symbols, graph nodes, graph edges, and search text in Knowledge Foundry-owned Postgres. | 1 | `implemented` | `source/knowledge_foundry/db`, `migrations` | DESIGN-LAB, MVP-SPEC | `spec-postgres-schema-and-migrations.md` | ADR-0009 |
| KF-004 | Markdown Indexer | Extract markdown files, headings, links, metadata, and document text. | 1 | `implemented` | `source/knowledge_foundry/indexer/markdown`, `source/knowledge_foundry/indexer/pipeline.py` | PRD, MVP-SPEC | `spec-markdown-indexer.md` | ADR-0005, ADR-0006 |
| KF-005 | Code Inventory Indexer | Extract code files and initial language-neutral symbol inventory using tree-sitter. | 1 | `implemented` | `source/knowledge_foundry/indexer/code` | PRD, MVP-SPEC | `spec-code-and-symbol-inventory.md` | ADR-0006 |
| KF-006 | Graph Relation Store | Store deterministic relationships among docs, code, specs, tests, ADRs, and requirements. | 1 | `in-progress` | `source/knowledge_foundry/db`, `source/knowledge_foundry/indexer` | DESIGN-LAB, RTM | `spec-postgres-schema-and-migrations.md` (schema), `spec-markdown-indexer.md` + `spec-code-and-symbol-inventory.md` (writers) | ADR-0006, ADR-0008 |
| KF-007 | Postgres Full-Text Search | Search indexed content using PostgreSQL FTS with a generated `tsv` column and `websearch_to_tsquery`. | 1 | `implemented` | `source/knowledge_foundry/cli`, `source/knowledge_foundry/search` | PRD, MVP-SPEC | `spec-fts-search.md` | ADR-0008, ADR-0009 |
| KF-008 | Context Report Generator | Generate agent/tool-readable Markdown briefs from indexed project state. | 1 | `implemented` | `source/knowledge_foundry/cli`, `source/knowledge_foundry/context` | PRD, MVP-SPEC | `spec-context-report.md` | ADR-0007, ADR-0008, ADR-0011 |
| KF-009 | MVP Test Harness | Pytest coverage for local indexing, search, and reports. | 1 | `implemented` | `tests` | TEST, ADR | `spec-python-package-scaffold.md`, `spec-postgres-schema-and-migrations.md`, `spec-root-registry.md` | ADR-0003 |
| KF-010 | Local Lab DB Connectivity | Define and implement secure local Windows CLI access to lab Postgres through SSH tunnel/local config. | 1 | `implemented` | `source/knowledge_foundry/config`, `source/knowledge_foundry/db/diagnostics.py`, `docs/operations/runbook-local-lab-db-connectivity.md` | MVP-SPEC, DESIGN-LAB | `spec-local-lab-db-connectivity.md` | ADR-0001, ADR-0009 |
| KF-011 | Index Pruning And Deletes | Detect deleted/moved/ignored files and prevent stale graph/search/context output. | 1 | `implemented` | `source/knowledge_foundry/indexer/pipeline.py`, `migrations/versions/20260527_0002_documents_stale.py` | MVP-SPEC | `spec-index-pruning-and-deletes.md` | ADR-0006, ADR-0011 |

## 4. Agent And Tool Integration

| ID | Feature | Description | Phase | Status | Package/Area | Source | Spec | ADR |
|---|---|---|---:|---|---|---|---|---|
| KF-020 | Read-Only MCP Server | Expose search/context tools over MCP after CLI primitives are stable. Implemented under KF-T110: read-only bridge with six operations, SDK-free dispatch layer, and stdio transport on the official `mcp` Python SDK wired into `kf mcp serve`. | 2 | `implemented` | `source/knowledge_foundry/mcp` | PRD, DESIGN-LAB | `spec-mcp-and-tool-context.md` | ADR-0007, ADR-0008, ADR-0011 |
| KF-021 | Tool Context Profiles | Generate context tailored for Codex, Droid, Gemini CLI, VS Code, and other tools. Implemented as the `formatters` submodule under KF-T110 (`to_codex`, `to_droid`, `to_gemini`, `to_vscode`, `to_mcp`). | 2 | `implemented` | `source/knowledge_foundry/mcp` | PRD | `spec-mcp-and-tool-context.md` | ADR-0007, ADR-0008 |
| KF-022 | Write Review Artifacts | Emit proposed docs/spec/code changes as review artifacts, not direct source writes. | 2 | `not-started` | `source/shared` | PRD | TBD | ADR-0011 |
| KF-023 | Droid Development Orchestration | Use Factory Droid CLI as a bounded implementation worker with Codex-managed specs, task graph, model routing, token/cost tracking, and regeneration notes. | 1 | `implemented` | `docs/project`, `docs/engineering/specs` | User request, RTM | `spec-droid-development-orchestration.md` | ADR-0003, ADR-0007, ADR-0010 |
| KF-024 | Gemini Research And Documentation Orchestration | Use Gemini CLI for grounded research, documentation synthesis, docs consistency review, UI mock data, and research prompt artifacts. | 1 | `in-progress` | `GEMINI.md`, `docs/project/gemini-prompts`, `docs/engineering/specs` | User request, RTM | `spec-gemini-research-documentation-orchestration.md` | ADR-0003, ADR-0007, ADR-0010 |

## 5. Lab Server Features

| ID | Feature | Description | Phase | Status | Package/Area | Source | Spec | ADR |
|---|---|---|---:|---|---|---|---|---|
| KF-040 | FastAPI Service | Read-only HTTP/JSON API mounted at `/api/v1`. Adapter on top of the MCP bridge kernel; six endpoints matching the dashboard `DataSource` interface so `ApiDataSource` swaps in without view changes. Write surface is out of scope per ADR-0008 §5. | 3 | `implemented` | `source/api` | KF-T132 | `spec-readonly-api.md` | ADR-0008, ADR-0011, ADR-0012 |
| KF-041 | Dedicated Postgres Store | Knowledge Foundry-owned Postgres workload/release, database, user, secret, and PVC boundary. | 1 | `deployed` | `infra/kubernetes`, `source/shared` | DESIGN-LAB, MVP-SPEC | MVP-SPEC | ADR-0009 |
| KF-046 | Postgres Backup And Restore | Manual backup and restore validation for the dedicated Knowledge Foundry database. | 1 | `in-progress` | `docs/operations/runbook-postgres-backup-restore.md`, `source/knowledge_foundry/operations/backup.py` | DESIGN-LAB | `spec-postgres-backup-restore.md` | ADR-0009 |
| KF-047 | Lab Security Baseline | Network/service exposure, resource controls, and secret rotation baseline before API/worker pods. | 2 | `implemented` | `infra/kubernetes/knowledge-foundry`, `docs/operations/runbook-postgres-secret-rotation.md` | DESIGN-LAB | `spec-lab-security-baseline.md` | ADR-0010, ADR-0011 |
| KF-042 | Worker Process | Background indexing/report generation jobs. | 3 | `deferred` | `source/worker` | DESIGN-LAB | TBD | ADR-0009 |
| KF-043 | Dedicated Redis Jobs | Knowledge Foundry-owned Redis for queue/event support when async workers require it. | 3 | `deferred` | `source/worker`, `infra` | DESIGN-LAB | TBD | ADR-0009 |
| KF-044 | Kubernetes Manifests | Lab deployment manifests for API, worker, and dependencies integration. | 3 | `deferred` | `infra/kubernetes` | DESIGN-LAB | TBD | ADR-0001, ADR-0002 |
| KF-045 | Health And Readiness | `/health` and `/ready` for lab services. | 3 | `deferred` | `source/api`, `source/worker` | DESIGN-LAB | TBD | ADR-0010 |

## 6. Dashboard And Visualization

| ID | Feature | Description | Phase | Status | Package/Area | Source | Spec | ADR |
|---|---|---|---:|---|---|---|---|---|
| KF-060 | Dashboard Shell | React/Vite/TypeScript shell with left-rail nav, main pane, and right inspector. Consumes a swappable DataSource (mock fixture today; the read-only HTTP API later). Drives the workspace overview + the four drill-down views under KF-T131. | 4 | `implemented` | `source/dashboard` | DESIGN-LAB | `spec-dashboard-mvp.md` | ADR-0008, ADR-0012 |
| KF-061 | Graph Browser | Visual browse/search of nodes and edges (root detail Graph tab). Powered by read-only `GET /api/v1/graph/subgraph` with deterministic ordering and truncation metadata; dashboard Graph tab renders the bounded subgraph payload from the same DataSource seam as the other tabs. | 4 | `implemented` | `source/dashboard`, `source/api` | PRD | `spec-graph-subgraph-endpoint.md`, `spec-graph-subgraph-implementation.md` | ADR-0006, ADR-0008, ADR-0012 |
| KF-062 | Feature/Spec/Test Trace View | Dashboard traceability matrix mirroring `docs/project/requirements-traceability.md` with Scope (functional/non-functional) + Status + Priority chip filters and a stale-source banner. | 4 | `implemented` | `source/dashboard` | PRD, RTM | `spec-dashboard-mvp.md` | ADR-0003, ADR-0008, ADR-0012 |
| KF-063 | Index Health View | Workspace overview KPIs + root detail (Documents/Symbols/Index Runs tabs) + Index Run Detail forensic view, all sourced from the existing index/search/context data. | 4 | `implemented` | `source/dashboard` | DESIGN-LAB | `spec-dashboard-mvp.md` | ADR-0008, ADR-0012 |

## 7. CI/CD And Operations

| ID | Feature | Description | Phase | Status | Package/Area | Source | Spec | ADR |
|---|---|---|---:|---|---|---|---|---|
| KF-080 | GitHub-Hosted CI | Docs inventory, JSON validation (`task-graph.json`, `mock-data.json`), ruff + pytest (with the `[dev,api]` extras so `tests/api/*` resolve `fastapi`), secret scan, CI gate; plus a separate dashboard workflow (typecheck + unit + a11y + build + Playwright smoke). | 1 | `implemented` | `.github/workflows/{ci,dashboard}.yml` | FR-011 | N/A | ADR-0002 |
| KF-084 | Lab Foundation Spec | Define dedicated namespace, Postgres, PVC, config, secret strategy, and manifest validation. | 1 | `deployed` | `docs/engineering/specs`, `infra/kubernetes`, `tests` | MVP-SPEC, DESIGN-LAB | `spec-lab-foundation.md` | ADR-0001, ADR-0009 |
| KF-081 | Manual Lab Deploy | Documented deploy from trusted local workstation. | 3 | `deferred` | `docs/infrastructure`, `infra` | DESIGN-LAB | TBD | ADR-0001, ADR-0002 |
| KF-082 | Lab Runner Deploy | ARC or self-hosted runner deployment pipeline. | 4 | `deferred` | `.github/workflows`, `infra` | DESIGN-LAB | TBD | ADR-0002 |
| KF-083 | Structured Logs | Consistent logs for CLI/API/worker. | 2 | `not-started` | `source/shared` | DESIGN-LAB | TBD | ADR-0010 |

## 8. Out Of Scope For MVP

| Feature | Reason |
|---|---|
| Cloud-native AWS/GCP deployment | No-constraints reference only; lab target selected first. |
| Native graph database | Relational graph tables are enough for MVP. |
| Embedding/vector search | Exact search and deterministic graph extraction come first. |
| Automated writes to indexed projects | Review artifacts only until write policy is designed. |
| Multi-user auth/RBAC | Needed for lab/team mode, not local MVP. |
| Existing lab Postgres/Redis from another project | Forbidden because those resources can be destroyed or rebuilt independently. |
