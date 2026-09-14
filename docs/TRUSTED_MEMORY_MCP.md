# Trusted Memory over MCP

LLM-Kosh exposes the Trusted Memory Runtime through the composed `llm-kosh-mcp` server on current source.

The goal is to let MCP-compatible agents share durable memory without bypassing evidence, admission, lifecycle, conflict, or source-authority rules.

## Tool surface

Read-only tools require no extra MCP capability:

- `trusted_memory_recall` — governed recall in `normal`, `strict`, `historical`, or `candidate` mode.
- `trusted_memory_inbox` — candidate and quarantined items awaiting review or resolution.
- `trusted_memory_conflicts` — unresolved candidate/quarantined memories whose latest assessment reports a conflict.
- `trusted_memory_explain` — authorized memory, evidence references, runtime metadata, and admission history for one memory.

Write and mutation remain explicit:

- `trusted_memory_propose` requires `--allow-write` (or the equivalent cartridge MCP policy permission).
- `trusted_memory_review` requires `--allow-mutate` (or the equivalent cartridge MCP policy permission).

These tools reuse the same `require_capability` gates as the base MCP server. They do not implement a second permission system.

## Source authority boundary

An MCP client cannot create a new memory and label its evidence as `user_direct`.

When `trusted_memory_propose` is called without an existing evidence id, LLM-Kosh stores the proposal evidence as:

```text
source_type = agent_observation
```

That source is contextual by default under the Trusted Memory admission policy. For a medium-risk decision it therefore normally requires review rather than auto-admission.

If an existing `evidence_id` is supplied, the proposal uses the source type already recorded on that evidence. The MCP caller cannot relabel web content, an imported document, a repository source, or another evidence record to obtain stronger authority.

If an agent needs a stronger/different source class, register the real evidence through the existing evidence/artifact surfaces first and pass its evidence id to `trusted_memory_propose`.

## Lifecycle and strict recall

Review and source authority are separate concepts.

For example, a human can explicitly approve an `agent_observation`, promoting its lifecycle from `candidate` to `verified`. The memory can then appear in `normal` recall. However, its original authority remains `contextual`, so it is still excluded from `strict` recall.

Strict recall currently requires all of the following:

- lifecycle `verified` or `active`
- no blocking admission decision
- authority `authoritative` or `trusted`
- at least one evidence reference

This prevents review from silently rewriting provenance.

## Conflict behavior

Trusted Memory never silently replaces a current memory because a new agent says something different.

A structured contradiction can be detected during proposal admission. Depending on source authority and risk, the new proposal is held for review or quarantined, while the existing memory remains unchanged.

`trusted_memory_conflicts` exposes the latest conflict state, conflicting memory ids, and admission reasons.

Supersession is only performed through an explicit `trusted_memory_review` action with `action="supersede"`. The reviewer validates that the target memories were identified by the admission assessment before applying the lifecycle changes atomically.

## Source install

The current PyPI `2.1.3` package predates this composed Trusted Memory MCP surface. To test current source:

```bash
python -m pip install -e .
llm-kosh-mcp --root ./my-cartridge
```

Equivalent module invocation:

```bash
python -m llm_kosh.mcp_trusted_memory_server --root ./my-cartridge
```

The composed server includes the existing Kosh Verify tool as well as Trusted Memory tools.

## Capability examples

Read-only server:

```bash
llm-kosh-mcp --root ./my-cartridge
```

Allow agents to propose governed memory, but not approve/reject/supersede it:

```bash
llm-kosh-mcp --root ./my-cartridge --allow-write
```

Allow explicit lifecycle review as well:

```bash
llm-kosh-mcp --root ./my-cartridge --allow-write --allow-mutate
```

Private context export remains a separate capability:

```bash
llm-kosh-mcp --root ./my-cartridge --allow-private
```

## Intended cross-agent workflow

A practical flow is:

1. Agent A recalls current trusted memory before acting.
2. Agent A proposes an observation or decision it believes should persist.
3. Admission policy decides whether the proposal can be admitted, requires review, must be quarantined, or must be rejected.
4. Agent B in another MCP-compatible client recalls the same cartridge later.
5. If Agent B proposes a contradictory claim, LLM-Kosh surfaces the conflict instead of overwriting the original memory.
6. An authorized reviewer explicitly resolves the conflict or supersedes prior state.

This is the product boundary LLM-Kosh is moving toward: shared cross-agent memory whose provenance and authority remain visible instead of being flattened into an opaque store.

## Non-goals

This MCP surface does not:

- treat agent output as direct user authority
- auto-resolve contradictions
- auto-supersede existing memory
- change source authority during review
- consult the internet to validate a claim
- require a hosted memory service

Kosh Verify remains the evidence-aware reasoning surface for asking what the local cartridge can support, what conflicts, what was inferred, and when the system should abstain.
