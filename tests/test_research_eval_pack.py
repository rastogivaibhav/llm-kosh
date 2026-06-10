from pathlib import Path
import json
import subprocess
import sys


def test_research_eval_script_runs_and_produces_reports():
    repo = Path(__file__).resolve().parents[1]
    script = repo / 'research_eval' / 'scripts' / 'run_multidomain_evaluation.py'
    result = subprocess.run([sys.executable, str(script), '--no-details'], cwd=repo, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-1000:]
    report = repo / 'reports' / 'research_eval' / 'multidomain_holdout_v1.json'
    assert report.exists()
    data = json.loads(report.read_text())
    assert data['tasks'] >= 60
    assert data['average_scores']['TheHypoKosh'] > data['average_scores']['TemporalRAG_proxy']
    assert data['average_scores']['TheHypoKosh'] > data['average_scores']['GraphRAG_proxy']


def test_blind_and_private_ground_truth_files_exist():
    repo = Path(__file__).resolve().parents[1]
    data_dir = repo / 'research_eval' / 'data'
    assert (data_dir / 'questions_blind.jsonl').exists()
    assert (data_dir / 'ground_truth_private.jsonl').exists()
    assert (data_dir / 'ground_truth_hashes.json').exists()
    blind = (data_dir / 'questions_blind.jsonl').read_text().splitlines()
    private = (data_dir / 'ground_truth_private.jsonl').read_text().splitlines()
    assert len(blind) == len(private) >= 60
    first_blind = json.loads(blind[0])
    assert 'expected' not in first_blind
