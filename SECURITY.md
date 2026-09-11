# Security

`llm-kosh` is designed to keep agent memory local, inspectable, and permission-aware. The Python package does not enable cloud sync or telemetry by default, but some optional features intentionally create local service or MCP surfaces. This document describes the current security model and its limits.

## Security principles

- **Local-first storage.** Cartridge data, indexes, ledgers, and generated context remain on local storage unless the user explicitly exports, packs, or sends them elsewhere.
- **Least privilege for MCP.** The MCP server starts read-only. Write, mutation, and private-context capabilities require explicit opt-in flags.
- **Explicit network exposure.** MCP can run over local HTTP when `--http` is enabled. Treat any HTTP listener as a real network boundary; do not expose it beyond a trusted host/network without authentication and transport controls appropriate to your environment.
- **Auditable mutation.** State-changing operations are recorded in the cartridge ledger so changes can be inspected and verified.
- **Export safety gates.** Context export paths apply visibility policy and secret scanning before material leaves the cartridge.

## MCP permissions

The default MCP mode is read-only:

```bash
llm-kosh --root ./my-cartridge mcp-server
```

Stronger capabilities must be enabled explicitly:

```bash
llm-kosh --root ./my-cartridge mcp-server --allow-write
llm-kosh --root ./my-cartridge mcp-server --allow-write --allow-mutate
llm-kosh --root ./my-cartridge mcp-server --allow-private
```

Only grant these flags to clients you trust. `--allow-private` can make private cartridge content available to the connected client.

## Local HTTP MCP

HTTP transport is optional:

```bash
llm-kosh --root ./my-cartridge mcp-server --http --port 8000
```

If you enable HTTP transport, review the bind address and surrounding host/network controls before use. A local development endpoint should not be treated as production-grade remote access by itself.

## Background service and watched folders

The optional service can watch cartridge intake folders and configured external directories. Files placed in those locations may be processed automatically. Configure watched directories narrowly and avoid pointing them at locations that contain unrelated secrets or sensitive material.

## Export and pack controls

Export paths use two classes of controls:

1. **Visibility/policy checks** can exclude `private`, `blocked`, or `quarantine` content depending on the command and policy configuration.
2. **Secret scanning** checks assembled text content for common credential and secret patterns before export. Redaction or explicit override behaviour depends on the command and flags used.

Secret scanning is pattern-based and cannot guarantee detection of every bespoke or unlabeled secret. Review sensitive exports before sharing them with external systems.

## What this does not protect against

- A compromised local account, host, filesystem, Python environment, or MCP client.
- Secrets that do not match the scanner's detection patterns.
- Data handling performed by third-party AI providers after you explicitly send exported context to them.
- Plaintext cartridge files at rest. Use OS-level disk encryption and file permissions when needed.
- Unsafe network exposure when optional HTTP/server features are bound beyond a trusted environment.
- Malicious or untrusted files placed in watched intake locations. Treat ingest sources as a trust boundary.

## Dependency and supply-chain considerations

Optional features can install additional dependencies for watching, serving, semantic search, and document ingestion. Review and update dependencies as part of normal maintenance, and use isolated environments for untrusted workloads.

## Reporting a vulnerability

Please do **not** include secrets, exploit payloads containing real credentials, or sensitive user data in a public issue.

For non-sensitive security bugs, open a GitHub issue with reproduction steps and affected version. For sensitive disclosures, contact the maintainer using the email published in the package metadata (`pyproject.toml`) and include the affected version, impact, and a minimal reproduction.

## Related documentation

- [README security model](README.md#security-model)
- [Contribution guide](CONTRIBUTING.md)
- [GA readiness](GA_READINESS.md)
