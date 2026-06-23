# Karpathy-Style Hardening Notes

Goal: reduce abstraction drift and make the smallest coherent branch pass.

## Changes

1. `CausalDAG.add_fact` now supports positional, `TemporalFact`, and keyword `content=` ingestion.
2. v1.1 experimental classes are exported under `V11*` names so they no longer shadow production `QueryTrace` or `SelfModel`.
3. v1.1 critic uses no-evidence semantics for unscored traces.
4. MCP server has a minimal fallback when optional `mcp` package is absent.

## Design principle

The recursive loop should inspect and improve the stable production reasoning trace, not replace the production trace model with a parallel one.

## What remains

The v1.1 standalone tracer still exists for experiments. It should either be merged into the production trace system or kept behind an explicit experimental namespace.
