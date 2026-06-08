from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_uploaded_itsm_temporal_causal_provenance_eval_runs(tmp_path: Path):
    archive4 = Path('/mnt/data/archive 4.zip')
    archive5 = Path('/mnt/data/archive 5.zip')
    if not archive4.exists() or not archive5.exists():
        # Allows the test to remain in the package even when the uploaded
        # benchmark archives are not present on another machine.
        return
    out = tmp_path / 'reports'
    cart = tmp_path / 'cartridge'
    cmd = [
        sys.executable,
        'scripts/run_temporal_causal_provenance_dataset_eval.py',
        '--archive4', str(archive4),
        '--archive5', str(archive5),
        '--incident-limit', '20',
        '--ticket-limit', '20',
        '--out', str(out),
        '--cartridge', str(cart),
    ]
    subprocess.run(cmd, check=True, cwd=Path(__file__).resolve().parents[1])
    data = json.loads((out / 'temporal_causal_provenance_eval_results.json').read_text())
    assert data['verdict']['passed_checks'] >= 5
    assert data['dataset_audit']['archive4_incident_event_log']['rows'] > 100000
    assert data['dataset_audit']['archive5_itsm_dataset']['rows'] == 100000
    assert data['time_ablation']['sla_accuracy_exact_time'] == 1.0
