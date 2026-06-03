# Self-Healing Daemon OS

The Koush Daemon (`koush daemon`) acts as an automated background maintenance runtime. Instead of relying on crontabs or external automation tools, Koush can manage its own health and intake queues.

## Modes

- `watchdog`: Listens for file system events (specifically `.md` receipts in `receipts/`) and runs maintenance jobs instantaneously when changes occur.
- `polling`: Runs jobs on a set interval (default 10 seconds).
- `auto`: Uses both `watchdog` and `polling`.

## Jobs

The Daemon executes jobs defined in `koush.daemon.JOBS`. Common jobs include:

1. `scan_intake`: Ingests records from various sources into the Intake Queue.
2. `process_safe_receipts`: Reviews receipts, blocks high-impact/risky changes, and automatically applies safe changes, archiving them to `receipts/processed/`.
3. `rebuild_stale_index`: Rebuilds derived sqlite/FTS indices if stale.
4. `audit`: Validates Koush integrity.
5. `heal_safe`: Repairs missing source-maps or structure without human intervention.
6. `regenerate_memory_map`: Rebuilds the `MEMORY_MAP.md`.
7. `regenerate_workbench`: Compiles the static web UI.
8. `backup_snapshot`: Archives a `.zip` of your source files.

## Policy Configuration

You can enable or disable specific jobs by editing the `KOUSH_POLICY.json` at the root of your cartridge:

```json
{
  "daemon": {
    "enabled_jobs": [
      "scan_intake",
      "process_safe_receipts",
      "rebuild_stale_index",
      "regenerate_memory_map"
    ],
    "poll_interval_seconds": 10
  }
}
```

## Logs and Status

- Run `koush daemon status` to view the last time each job ran and its output.
- Run `koush daemon log` to output the structured JSONL events log stored at `reports/daemon/events.jsonl`.
