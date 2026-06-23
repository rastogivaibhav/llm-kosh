# Service developer guide

The sustained service is implemented in `llm_kosh/service.py` and controlled by
the main CLI:

```bash
llm-kosh service start
llm-kosh service status
llm-kosh service stop
```

The legacy `llm-kosh daemon` interface remains for foreground scheduler use,
but new lifecycle work should target `llm-kosh service`.

## Responsibilities

The service:

- resolves the cartridge root;
- validates or initializes expected runtime paths;
- processes recurring daemon jobs;
- watches `receipts/` and `intake/` when `watchdog` is available;
- falls back to polling when `watchdog` is unavailable;
- exposes a local health endpoint;
- records PID and rotating logs under the llm-kosh home directory.

## Environment

- `LLMKOSH_ROOT` overrides the active cartridge root for the service process.
- `LLMKOSH_NO_AUTOSPAWN=1` disables automatic background spawning from CLI calls.

The service should work both from normal Python and from the frozen PyInstaller
sidecar. When changing service commands, check both execution modes.

## Health check

The service serves:

```text
GET http://127.0.0.1:5556/health
```

The response includes status, PID, uptime, and root. Do not expose private
memory contents through this endpoint.

## OS registration

Service installation is coordinated by `llm_kosh/install.py`.

- Windows uses a scheduled task.
- macOS uses a LaunchAgent plist.
- Linux uses a user systemd unit where available.

Registration code should quote paths carefully and avoid relying on shell
expansion.

## Tests

Focused tests:

```bash
python -m pytest tests/test_service_lifecycle.py tests/test_ga_lifecycle.py -q
```

Full regression:

```bash
python -m pytest -q
```

Manual smoke:

```bash
llm-kosh --root ./tmp-service init --owner "Service Dev"
llm-kosh --root ./tmp-service service start
llm-kosh --root ./tmp-service service status
llm-kosh --root ./tmp-service service stop
```

Use a disposable root for manual tests so user cartridges are not modified.

## Change checklist

- Preserve single-instance PID behavior.
- Preserve frozen sidecar command handling.
- Keep health data minimal.
- Keep shutdown paths idempotent.
- Run service lifecycle tests on Windows when changing process logic.
