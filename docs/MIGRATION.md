# Migration

Koush databases contain internal versions mapped to the Koush implementation.

As Koush evolves (e.g. going from v1.x -> v2.0), the structure of the file-system database might need migration (such as reorganizing directories or moving metadata into different file blocks).

## Commands

- `koush migrate check`: Checks the `KOUSH.json` root against the current version. Performs a dry run and states how many pending migrations apply.
- `koush migrate apply`: Executes any pending migrations sequentially, updating `KOUSH.json` when completed.
- `koush migrate rollback`: Rolls back the last sequential migration applied if it supports reversibility.

*Note: Migrations must be non-destructive where possible, taking snapshot backups before structural transformations.*
