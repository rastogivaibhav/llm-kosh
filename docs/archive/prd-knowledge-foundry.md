# Knowledge Foundry - Product Requirements Document

## 1. Problem Statement

Large software and AI projects lose context across tools, repositories, documents, and AI sessions.

Knowledge Foundry solves this by creating one durable project brain for:

- knowledge vaults such as Second_Brain
- project repositories
- specs, PRDs, ADRs, test plans, and docs
- code symbols, modules, routes, schemas, tests, and dependencies
- AI-assisted work history from Codex, Gemini CLI, Hermes, VS Code, GitHub CLI, and similar tools

## 2. Goals

1. Build a tool-agnostic project knowledge graph.
2. Support local-first workflows while targeting the existing lab server for shared use.
3. Track code structure like an API/schema layer: symbols, relationships, tests, docs, and behavior metadata.
4. Connect project planning to implementation: PRD -> specs -> tasks -> TDD -> code -> docs.
5. Expose project memory through CLI, MCP, generated context files, and later a dashboard.
6. Keep Markdown/Git as human-readable truth.

## 3. Non-Goals

- Replace Git, Obsidian, VS Code, Codex, Gemini CLI, Hermes, or GitHub.
- Require cloud hosting for the first usable version.
- Require direct LLM API keys for deterministic indexing and project tracking.
- Build an autonomous company simulator.
- Store the only copy of human knowledge in an opaque database.

## 4. Primary Architecture Direction

The primary target is the lab-server solution:

```txt
Windows dev machine
  -> CLI, MCP clients, Codex, Gemini CLI, VS Code, GitHub CLI

k8s-01 lab server
  -> dedicated Knowledge Foundry Postgres
  -> API, dashboard, dedicated Redis when needed, workers, observability

Source truth
  -> Git repos and Markdown knowledge vaults
```

## 5. User Stories

| ID | As a | I want | So that |
|---|---|---|---|
| US-001 | developer | index a repo and ask for architecture context | I do not need to reread the entire codebase in every session |
| US-002 | knowledge worker | index Second_Brain and find stale or missing notes | the KB stays useful and navigable |
| US-003 | architect | trace a PRD requirement to specs, code, and tests | large work remains controlled |
| US-004 | AI coding tool | query relevant project context through MCP | it can act with grounded context |
| US-005 | project owner | generate docs and diagrams from the graph | documentation stays aligned with implementation |

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Register knowledge roots and project repos. | Must |
| FR-002 | Index Markdown documents, wikilinks, headings, tags, and frontmatter. | Must |
| FR-003 | Index code files, symbols, imports, signatures, and line locations. | Must |
| FR-004 | Store graph nodes and edges with source location and confidence. | Must |
| FR-005 | Provide full-text search across docs and indexed metadata. | Must |
| FR-006 | Expose read-only CLI queries. | Must |
| FR-007 | Expose read-only MCP tools. | Must |
| FR-008 | Generate project context files for AI tools. | Should |
| FR-009 | Track PRD/spec/task/test/run/artifact relationships. | Should |
| FR-010 | Deploy shared API/dashboard to lab server. | Should |
| FR-011 | Support GitHub Actions CI. | Must |
| FR-012 | Support automated lab deployment later through ARC runner. | Could |

## 7. Non-Functional Requirements

| ID | Area | Requirement |
|---|---|---|
| NFR-012 | Portability | Core data must be exportable as Markdown, JSON, JSONL, and SQL dumps. |
| NFR-013 | Safety | Vault/repo writes require approval. |
| NFR-014 | Performance | Incremental indexing should avoid reprocessing unchanged files. |
| NFR-015 | Security | No secrets in docs, logs, generated context files, or committed config. |
| NFR-016 | Operability | Lab deployment must include health checks and basic runbook. |
| NFR-017 | Tool independence | No single AI tool should be required. |

> These NFRs are promoted into `docs/project/requirements-traceability.md` (NFR-012..NFR-017) for tracking. See KF-T120 / KF-G020 finding F-13.

## 8. MVP Scope

1. Monorepo scaffold.
2. Dedicated Knowledge Foundry Postgres primary store.
3. Root registry.
4. Markdown indexer.
5. Basic code inventory and symbol extractor.
6. CLI search/report commands.
7. MCP read-only server.
8. Lab deployment design and manifests.
9. GitHub Actions CI.

## 9. Success Metrics

| Metric | Target |
|---|---|
| Repo indexing | Can index Knowledge Foundry itself and one external repo. |
| Context generation | Can generate a project context brief from indexed data. |
| Search | Can search docs and symbols from CLI. |
| MCP | Can answer basic document/symbol/graph queries. |
| Lab readiness | Has manifests and manual deployment path for `k8s-01`. |
