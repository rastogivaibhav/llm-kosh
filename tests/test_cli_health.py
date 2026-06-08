import pytest
import os
from pathlib import Path

def test_cli_audit(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    
    code, out, err = runner("audit", workspace=temp_workspace)
    assert code == 0
    assert "Audit" in out or "Check" in out
    
def test_cli_heal(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    
    code, out, err = runner("heal", "--safe", workspace=temp_workspace)
    assert code == 0
    
def test_cli_verify_ledger(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    
    code, out, err = runner("verify-ledger", workspace=temp_workspace)
    assert code == 0

def test_cli_policy(runner, temp_workspace):
    runner("init", workspace=temp_workspace)
    
    code, out, err = runner("policy", "--init", workspace=temp_workspace)
    assert code == 0
    
    code, out, err = runner("policy", workspace=temp_workspace)
    assert code == 0
