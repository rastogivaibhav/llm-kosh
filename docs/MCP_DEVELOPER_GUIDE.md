# MCP developer guide

The MCP server lives in `llm_kosh/mcp_server.py` and is exposed through:

```bash
llm-kosh mcp-server
python -m llm_kosh.mcp_server
```

The package manifest for MCP registries is `server.json`.

## Local validation

Create a disposable cartridge and inspect the registered tools:

```bash
llm-kosh --root ./tmp-mcp init --owner "MCP Dev"
llm-kosh --root ./tmp-mcp mcp-test
llm-kosh --root ./tmp-mcp mcp-tools
```

Expected baseline: 13 registered tools.

Validate the manifest syntax:

```bash
python -m json.tool server.json
```

If the MCP registry publisher is installed and authenticated, also run:

```bash
mcp-publisher validate server.json
```

Publishing to an external MCP registry is a release action. It should happen
only from a tagged release or an approved release branch with the correct
registry credentials.

## Transports

stdio is the default:

```bash
llm-kosh --root ./tmp-mcp mcp-server
```

Streamable HTTP is local-only:

```bash
llm-kosh --root ./tmp-mcp mcp-server --http --port 8000
```

The HTTP listener binds to `127.0.0.1`.

## Capability model

The server starts read-only. Stronger capabilities require explicit flags:

- `--allow-write` for receipt submission and intake conversion.
- `--allow-mutate` for applying intake proposals.
- `--allow-private` for private context pack creation.

Capability-gated tools should also append a ledger event. This lets operators
audit which MCP client actions changed cartridge state or exported private
context.

## Adding a tool

When adding a tool:

1. Add the `@mcp.tool()` function in `llm_kosh/mcp_server.py`.
2. Use narrow arguments with predictable types.
3. Return plain strings or JSON strings.
4. Keep read-only operations free of side effects.
5. Gate writes with `@require_capability("write")`.
6. Gate direct mutations with `@require_capability("mutate")`.
7. Gate private exports with `@require_capability("private")`.
8. Add or update tests that exercise registration and capability behavior.
9. Run `llm-kosh mcp-test` and `llm-kosh mcp-tools`.

## Manifest checklist

Before changing `server.json`, confirm:

- `name` matches the README `mcp-name` comment.
- `version` matches `pyproject.toml`.
- the package identifier is `llm-kosh`;
- the transport is `stdio`;
- required environment variables are documented and non-secret unless they
  truly contain credentials.

## Failure modes

- If `mcp` is missing, reinstall the base package. MCP is a base dependency.
- If a desktop client cannot find Python, use an absolute interpreter path.
- If a root is invalid, initialize it before starting the server.
- If a write tool fails, check capability flags and cartridge policy.
