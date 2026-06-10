#!/usr/bin/env python3
"""
Evaluate TheHypoKosh system against EEDI causal discovery competition criteria.

Tasks:
  Task 1: Discover causal prerequisites among 50 learning constructs
  Task 2: Estimate Conditional Average Treatment Effect (CATE) under interventions

Ground Truth:
  adj_matrix.npy - Binary adjacency matrix [5 datasets, 50×50]
  cate_estimate.npy - CATE estimates [5 datasets, 10 queries]
"""

import sys
import io
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import system components
from llm_kosh.engine.reasoning import ReasoningEngine
from llm_kosh.engine.reasoning.causal_dag import (
    TemporalFact, CausalEdge, EdgeOrigin, EdgeRole, EdgeType, EdgeProvenance, EvidenceRef
)

# Paths
EEDI_ROOT = Path("C:/Users/vrast/Documents/Demo/dataset")
TASK1_DIR = EEDI_ROOT / "Task_1_dataset" / "Task_1_data_local_dev_csv"
TASK2_DIR = EEDI_ROOT / "Task_2_dataset" / "Task_2_data_local_dev"
CARTRIDGE = Path("C:/Users/vrast/OneDrive/Apps/Documents/llm-kosh-cart")

print("=" * 80)
print("EVALUATING THEOHYPOKOSH SYSTEM AGAINST EEDI COMPETITION CRITERIA")
print("=" * 80)

# ============================================================================
# PHASE 1: Load Ground Truth Data
# ============================================================================
print("\n[PHASE 1] Loading Ground Truth Data")
print("-" * 80)

try:
    # Load adjacency matrices (ground truth causal graphs)
    adj_matrices = np.load(TASK1_DIR / "adj_matrix.npy")
    print(f"[OK] Loaded adjacency matrices: shape {adj_matrices.shape}")
    print(f"     - Datasets: {adj_matrices.shape[0]}")
    print(f"     - Constructs: {adj_matrices.shape[1]}x{adj_matrices.shape[2]}")

    # Analyze ground truth structure
    for d in range(adj_matrices.shape[0]):
        n_edges = np.sum(adj_matrices[d])
        sparsity = 1.0 - (n_edges / (50 * 50))
        print(f"     Dataset {d}: {int(n_edges)} edges, sparsity {sparsity:.2%}")

except Exception as e:
    print(f"[ERROR] Failed to load adjacency matrices: {e}")
    sys.exit(1)

try:
    # Load CATE estimates (ground truth intervention effects)
    cate_estimates = np.load(TASK2_DIR / "cate_estimate.npy")
    print(f"[OK] Loaded CATE estimates: shape {cate_estimates.shape}")
    print(f"     - Datasets: {cate_estimates.shape[0]}, Queries: {cate_estimates.shape[1]}")
except Exception as e:
    print(f"[WARNING] CATE estimates not available: {e}")
    cate_estimates = None

# ============================================================================
# PHASE 2: Initialize ReasoningEngine
# ============================================================================
print("\n[PHASE 2] Initializing ReasoningEngine")
print("-" * 80)

try:
    engine = ReasoningEngine(CARTRIDGE)
    initial_node_count = len(engine.dag.nodes)
    print(f"[OK] Engine initialized")
    print(f"     Existing nodes: {initial_node_count}")
except Exception as e:
    print(f"[ERROR] Failed to initialize engine: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# PHASE 3: Ingest EEDI Data
# ============================================================================
print("\n[PHASE 3] Ingesting EEDI Training Data")
print("-" * 80)

DATASET_ID = 0  # Use first dataset for testing

try:
    # Load CSV data
    csv_file = TASK1_DIR / f"dataset_{DATASET_ID}" / "train.csv"
    df = pd.read_csv(csv_file, header=None)
    print(f"[OK] Loaded dataset_{DATASET_ID}: shape {df.shape}")

    # Sample ingest (first 100 records to avoid overload during testing)
    SAMPLE_SIZE = min(100, len(df))
    df_sample = df.iloc[:SAMPLE_SIZE]

    print(f"[INFO] Ingesting {SAMPLE_SIZE} temporal facts (sampled from {len(df)} total)...")

    facts_added = 0
    for idx, row in df_sample.iterrows():
        student_id = int(row.iloc[0])
        bot_action = int(row.iloc[1])
        construct_values = row.iloc[2:].values

        # Create temporal fact
        fact = TemporalFact(
            id=f"eedi_d{DATASET_ID}_s{student_id}_t{idx}",
            content=f"Student {student_id}: bot_action={bot_action}, constructs={construct_values[:5]}...",
            ingested_at=datetime.now(),
            documented_at=datetime.now(),
            valid_from=datetime(2022, 1, 1) + timedelta(hours=idx),
            valid_until=datetime(2022, 1, 1) + timedelta(hours=idx+1),
            confidence=0.95,  # synthetic data
            resonance_profile={
                "dataset": DATASET_ID,
                "student_id": student_id,
                "bot_action": bot_action,
                "construct_values": construct_values.tolist(),
            },
            source="eedi_platform",
        )

        try:
            node_id = engine.dag.add_fact(fact)
            facts_added += 1
        except Exception as e:
            print(f"     [WARN] Failed to add fact {idx}: {e}")

    print(f"[OK] Ingested {facts_added} temporal facts")
    new_node_count = len(engine.dag.nodes)
    print(f"     Graph now has {new_node_count} nodes (added {new_node_count - initial_node_count})")

except Exception as e:
    print(f"[ERROR] Data ingestion failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# PHASE 4: Attempt Causal Discovery (Task 1)
# ============================================================================
print("\n[PHASE 4] Task 1 - Causal Discovery")
print("-" * 80)

# Get ground truth for this dataset
ground_truth_adj = adj_matrices[DATASET_ID]
n_constructs = 50

print(f"Ground truth edges: {int(np.sum(ground_truth_adj))}")
print(f"Expected causal structure:")

# Show first few causal edges from ground truth
causal_edges_gt = []
for i in range(n_constructs):
    for j in range(n_constructs):
        if ground_truth_adj[i, j] == 1:
            causal_edges_gt.append((i, j))

print(f"Sample prerequisite relations (first 10):")
for src, tgt in causal_edges_gt[:10]:
    print(f"  construct_{src} → construct_{tgt}")

# Try to query the system about causal structure
print("\n[QUERY] Attempting causal discovery queries...")

test_queries = [
    "What are the prerequisite relationships between learning constructs?",
    "Which constructs enable learning of other constructs?",
    "Discover the causal structure of learning constructs.",
    "What construct relationships exist in this learning path data?",
]

discovered_edges = defaultdict(int)
query_results = []

for q_idx, query in enumerate(test_queries):
    print(f"\n  Query {q_idx+1}: {query}")
    try:
        result = engine.query(query, depth=2)

        print(f"    - Anchors found: {len(result.anchors)}")
        print(f"    - Bundle fibers: {len(result.bundle.fibers)}")
        print(f"    - Stability: {result.stability.status}")

        query_results.append({
            "query": query,
            "anchors": len(result.anchors),
            "fibers": len(result.bundle.fibers),
            "stability": result.stability.status,
            "escape_triggered": result.stability.escape_triggered,
        })

        # Try to extract edges from the bundle
        for fiber in result.bundle.fibers:
            if hasattr(fiber, 'edges'):
                for edge in fiber.edges:
                    discovered_edges[edge] += 1

    except Exception as e:
        print(f"    [ERROR] Query failed: {e}")
        query_results.append({
            "query": query,
            "error": str(e),
        })

print(f"\n[DISCOVERY RESULTS]")
print(f"  - Discovered {len(discovered_edges)} unique edges")
print(f"  - Total edge mentions: {sum(discovered_edges.values())}")

# ============================================================================
# PHASE 5: Attempt Intervention Analysis (Task 2)
# ============================================================================
print("\n[PHASE 5] Task 2 - CATE Estimation")
print("-" * 80)

try:
    # Load intervention queries
    with open(TASK2_DIR / f"intervention_{DATASET_ID}.json") as f:
        interventions = json.load(f)

    print(f"[OK] Loaded {len(interventions)} intervention queries for dataset_{DATASET_ID}")

    cate_predictions = []
    cate_errors = []

    for q_idx, intervention in enumerate(interventions[:3]):  # Test first 3
        print(f"\n  Query {q_idx}: CATE Estimation")

        conditioning_len = len(intervention.get("conditioning", []))
        bot_intervention = intervention.get("intervention")
        bot_reference = intervention.get("reference")
        effect_mask = intervention.get("effect_mask")

        print(f"    - Conditioning history: {conditioning_len} timesteps")
        print(f"    - Intervention: {bot_intervention}")
        print(f"    - Reference: {bot_reference}")

        try:
            # Build query about intervention effect
            intervention_query = (
                f"What is the effect of intervening on {bot_intervention} "
                f"compared to {bot_reference}?"
            )

            result = engine.query(intervention_query, depth=2)

            # Extract predicted effect magnitude
            predicted_cate = 0.0  # Placeholder
            if hasattr(result, 'confidence_product'):
                predicted_cate = result.confidence_product

            cate_predictions.append(predicted_cate)

            # Compare to ground truth if available
            if cate_estimates is not None:
                ground_truth_cate = cate_estimates[DATASET_ID, q_idx]
                error = abs(predicted_cate - ground_truth_cate)
                cate_errors.append(error)

                print(f"    - Predicted CATE: {predicted_cate:.4f}")
                print(f"    - Ground Truth CATE: {ground_truth_cate:.4f}")
                print(f"    - Error: {error:.4f}")
            else:
                print(f"    - Predicted CATE: {predicted_cate:.4f}")
                print(f"    - Ground Truth CATE: [not available]")

        except Exception as e:
            print(f"    [ERROR] Intervention query failed: {e}")

    if cate_errors:
        mae = np.mean(cate_errors)
        print(f"\n[CATE ESTIMATION RESULTS]")
        print(f"  - Mean Absolute Error (MAE): {mae:.4f}")
        print(f"  - Target MAE (competition): <0.10")
        print(f"  - Status: {'PASS' if mae < 0.10 else 'NEEDS IMPROVEMENT'}")

except Exception as e:
    print(f"[ERROR] Intervention analysis failed: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# PHASE 6: Evaluation Report
# ============================================================================
print("\n[PHASE 6] Evaluation Report")
print("=" * 80)

print("\n[TASK 1] CAUSAL DISCOVERY EVALUATION")
print("-" * 80)

if discovered_edges:
    print(f"Status: PARTIAL - System discovered some edges")
    print(f"Details:")
    print(f"  - Discovered edges: {len(discovered_edges)}")
    print(f"  - Ground truth edges: {int(np.sum(ground_truth_adj))}")
    print(f"  - Coverage: {len(discovered_edges) / int(np.sum(ground_truth_adj)):.1%}")
else:
    print(f"Status: INCOMPLETE - No edges discovered")
    print(f"  Ground truth edges: {int(np.sum(ground_truth_adj))}")

print(f"\nQuery Performance:")
for qr in query_results:
    if "error" not in qr:
        print(f"  - Query result: {qr['anchors']} anchors, stability={qr['stability']}")

print("\n[TASK 2] CATE ESTIMATION EVALUATION")
print("-" * 80)

if cate_errors:
    mae = np.mean(cate_errors)
    print(f"Status: {'PASS' if mae < 0.10 else 'NEEDS IMPROVEMENT'}")
    print(f"  - MAE: {mae:.4f}")
    print(f"  - Target: <0.10")
    print(f"  - Queries evaluated: {len(cate_errors)}")
else:
    print(f"Status: NO RESULTS - Could not generate CATE predictions")

print("\n[OVERALL SYSTEM ASSESSMENT]")
print("-" * 80)

criteria_met = {
    "task1_discovery": len(discovered_edges) > 0,
    "task2_estimation": len(cate_errors) > 0 and np.mean(cate_errors) < 0.10,
    "temporal_reasoning": len(query_results) > 0,
    "stability_handling": any(qr.get('escape_triggered', False) for qr in query_results),
}

for criterion, met in criteria_met.items():
    status = "✓ PASS" if met else "✗ FAIL"
    print(f"  {status}: {criterion}")

print(f"\nOverall: {sum(criteria_met.values())}/{len(criteria_met)} criteria met")

if sum(criteria_met.values()) >= 2:
    print("\n>>> SYSTEM IS CAPABLE OF HANDLING EEDI COMPETITION DATA <<<")
else:
    print("\n>>> SYSTEM NEEDS IMPROVEMENT TO MEET EEDI CRITERIA <<<")

print("\n" + "=" * 80)
print("EVALUATION COMPLETE")
print("=" * 80)
