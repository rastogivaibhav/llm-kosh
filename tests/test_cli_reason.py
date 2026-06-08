import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime, timezone

import pytest


def _run(args: list) -> tuple[str, int]:
    """Run the CLI with args and capture output. Returns (stdout, exit_code)."""
    import io
    buf = io.StringIO()
    exit_code = 0
    with patch('sys.stdout', buf):
        try:
            from llm_kosh.cli import main
            with patch('sys.argv', ['llm-kosh'] + args):
                main()
        except SystemExit as e:
            exit_code = int(str(e)) if str(e).isdigit() else 0
    return buf.getvalue(), exit_code


def test_reason_empty_cartridge():
    """reason command on empty cartridge returns empty chain message."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        out, code = _run(['--root', str(root), 'reason', 'auth system'])
        assert "No causal chain found" in out or "CAUSAL TIMELINE" in out
        assert code == 0


def test_reason_narrative_output():
    """reason command returns formatted narrative for seeded cartridge."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        from llm_kosh.engine.reasoning import ReasoningEngine
        now = datetime.now(timezone.utc)
        engine = ReasoningEngine(root)
        engine.ingest("Decision to use PostgreSQL for auth", now, now, None, 0.9, [])
        out, code = _run(['--root', str(root), 'reason', 'PostgreSQL'])
        assert "CAUSAL TIMELINE" in out or "No causal chain found" in out
        assert code == 0


def test_reason_json_flag():
    """--json flag returns valid JSON."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        from llm_kosh.engine.reasoning import ReasoningEngine
        now = datetime.now(timezone.utc)
        engine = ReasoningEngine(root)
        engine.ingest("Auth uses JWT tokens", now, now, None, 0.9, [])
        out, code = _run(['--root', str(root), 'reason', 'auth', '--json'])
        parsed = json.loads(out)
        assert "anchors" in parsed
        assert "stability" in parsed
        assert code == 0


def test_reason_depth_flag():
    """--depth flag is accepted and doesn't error."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        out, code = _run(['--root', str(root), 'reason', 'anything', '--depth', '5'])
        assert code == 0


def test_reason_when_flag():
    """--when flag with ISO timestamp is accepted."""
    with TemporaryDirectory() as t:
        root = Path(t)
        from llm_kosh.core.memory import init_cartridge
        init_cartridge(root, "test")
        out, code = _run(['--root', str(root), 'reason', 'anything', '--when', '2025-06-01T00:00:00Z'])
        assert code == 0
