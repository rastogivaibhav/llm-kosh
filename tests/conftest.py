import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# Ensure the root of the project is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture
def temp_workspace():
    """Provides a temporary workspace path initialized for Koush."""
    temp_dir = tempfile.mkdtemp(prefix="koush_test_")
    
    # Initialize basic koush structure
    ledger_dir = Path(temp_dir) / ".koush"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    
    yield temp_dir
    
    # Teardown
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def runner():
    """Provides a helper to run koush_cli main with args and capture output."""
    from koush.cli import main
    
    def _run(*args, workspace=None):
        import contextlib
        import io
        
        stdout = io.StringIO()
        stderr = io.StringIO()
        
        cmd = ["koush_cli"]
        if workspace:
            cmd.extend(["--root", str(workspace)])
        cmd.extend(args)
        
        sys_argv_backup = sys.argv
        sys.argv = cmd
        
        code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                main()
            except SystemExit as e:
                code = e.code
                
        sys.argv = sys_argv_backup
        
        return code, stdout.getvalue(), stderr.getvalue()
        
    return _run
