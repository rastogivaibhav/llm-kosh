#!/usr/bin/env bash
set -euo pipefail

pytest -q \
  tests/test_reasoning_causal_dag.py \
  tests/test_reasoning_retrieval.py \
  tests/test_reasoning_fiber_bundle.py \
  tests/test_reasoning_lyapunov.py \
  tests/test_reasoning_escape.py \
  tests/test_reasoning_engine.py \
  tests/test_reasoning_discourse.py \
  tests/test_reasoning_formatter.py \
  tests/test_demo_reasoning.py \
  tests/test_cli_reason.py \
  tests/test_reasoning_provenance_layers.py \
  tests/test_reasoning_no_evidence_guard.py \
  tests/test_research_eval_pack.py \
  tests/test_reasoning_dialectic_model_world.py

pytest -q \
  tests/test_cli_core.py \
  tests/test_cli_healing.py \
  tests/test_cli_health.py \
  tests/test_cli_intake.py \
  tests/test_cli_packs.py \
  tests/test_cli_processors.py \
  tests/test_cli_semantic.py \
  tests/test_conformance.py \
  tests/test_daemon.py \
  tests/test_daemon_reasoning_sync.py \
  tests/test_engine_direct.py \
  tests/test_imports.py \
  tests/test_orthogonal_subspaces.py \
  tests/test_receipt_trust.py \
  tests/test_workbench.py

python3 research_eval/scripts/run_multidomain_evaluation.py
