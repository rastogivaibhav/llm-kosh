# MCP guide

MCP support is installed with the base `llm-kosh` package.

## Claude Desktop

The easiest setup is:

```bash
python -m pip install --upgrade llm-kosh
llm-kosh install --yes
```

This creates a read-only `llm-kosh` entry in Claude Desktop's configuration.
Restart Claude Desktop after setup.

For a manual configuration, use the same Python interpreter that owns the
package. Replace the root path below:

```json
{
  "mcpServers": {
    "llm-kosh": {
      "command": "/absolute/path/to/python",
      "args": [
        "-m",
        "llm_kosh.cli",
        "--root",
        "/absolute/path/to/cartridge",
        "mcp-server"
      ]
    }
  }
}
```

Using an absolute interpreter path avoids GUI `PATH` differences.

## Transports

stdio is the default and is intended for local desktop clients:

```bash
llm-kosh --root ./my-cartridge mcp-server
```

Local streamable HTTP is available at `/mcp`:

```bash
llm-kosh --root ./my-cartridge mcp-server --http --port 8000
```

The HTTP listener binds to `127.0.0.1` only.

## Capabilities

The default is read-only. Grant each stronger capability explicitly:

- `--allow-write`: submit additions and intake
- `--allow-mutate`: approve or apply memory changes
- `--allow-private`: create exports containing private context

You can inspect registration without starting a transport:

```bash
llm-kosh --root ./my-cartridge mcp-test
llm-kosh --root ./my-cartridge mcp-tools
```

For tool authoring, manifest validation, and release publishing notes, see
[MCP developer guide](MCP_DEVELOPER_GUIDE.md).
