# Migration

LlmKosh databases contain internal versions mapped to the LlmKosh implementation.

As LlmKosh evolves (e.g. going from v1.x -> v2.0), the structure of the file-system database might need migration (such as reorganizing directories or moving metadata into different file blocks).

## Commands

- `llm-kosh migrate check`: Checks the `LLM_KOSH.json` root against the current version. Performs a dry run and states how many pending migrations apply.
- `llm-kosh migrate apply`: Executes any pending migrations sequentially, updating `LLM_KOSH.json` when completed.
- `llm-kosh migrate rollback`: Rolls back the last sequential migration applied if it supports reversibility.

*Note: Migrations must be non-destructive where possible, taking snapshot backups before structural transformations.*
