# Documentation standards

Use this checklist when editing public documentation.

## Keep public docs sanitized

Do not include:

- local absolute paths from a contributor machine;
- private emails, tokens, API keys, hostnames, or internal URLs;
- unreproducible benchmark claims without a linked report;
- claims that imply hosted services or telemetry when the feature is local;
- statements that signing, notarization, or publishing happened unless it was
  verified for the exact artifact.

## Prefer precise language

Use:

- "tamper-evident ledger" instead of "immutable guarantee";
- "local-first" instead of "offline-proof";
- "read-only by default" instead of "safe in all configurations";
- "release candidate" when hosted CI or signing gates remain.

Avoid broad claims such as "100% secure", "zero downtime", or "production GA"
unless the release gates prove them.

## Document commands as copy/pasteable

Commands should:

- work from the documented directory;
- use placeholder paths such as `./tmp-cartridge`;
- avoid contributor-specific usernames;
- mention when credentials are required;
- distinguish local validation from external publishing.

## Keep architecture docs current

When changing runtime behavior, update the relevant docs:

- CLI changes: `docs/CLI_REFERENCE.md` and `docs/DEVELOPER_GUIDE.md`.
- MCP changes: `docs/MCP_GUIDE.md`, `docs/MCP_DEVELOPER_GUIDE.md`, and
  `server.json`.
- Service changes: `docs/SERVICE_DEVELOPER_GUIDE.md`.
- Desktop changes: `docs/DESKTOP_DEVELOPER_GUIDE.md`.
- Release gates: `GA_READINESS.md` and `docs/RELEASE_ENGINEERING.md`.
