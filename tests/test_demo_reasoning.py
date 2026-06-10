"""Smoke tests for the demo script."""
import subprocess
import sys
from pathlib import Path


DEMO_SCRIPT = Path(__file__).parent.parent / "scripts" / "demo_reasoning.py"


def test_demo_script_exists():
    """Demo script exists at expected path."""
    assert DEMO_SCRIPT.exists(), f"Demo script not found at {DEMO_SCRIPT}"


def test_demo_script_runs():
    """Demo script runs to completion without error."""
    result = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Demo script failed with exit code {result.returncode}\n"
        f"STDOUT: {result.stdout[-500:]}\n"
        f"STDERR: {result.stderr[-500:]}"
    )


def test_demo_script_output_contains_sections():
    """Demo output contains both KEYWORD SEARCH and TEMPORAL CAUSAL REASONING sections."""
    result = subprocess.run(
        [sys.executable, str(DEMO_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    output = result.stdout
    assert "KEYWORD SEARCH" in output
    assert "TEMPORAL CAUSAL REASONING" in output
    # Should show causal timeline or empty chain message
    assert ("CAUSAL TIMELINE" in output or "No causal chain found" in output)
