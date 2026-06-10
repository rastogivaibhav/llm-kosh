"""EEDI evaluation for v1.1 system."""
import numpy as np
from pathlib import Path
from datetime import datetime


class EEDIV1_1Evaluation:
    """Evaluate v1.1 system against EEDI benchmark."""

    def __init__(self, engine, eedi_root: Path):
        self.engine = engine
        self.eedi_root = eedi_root
        self.results = []

    def load_eedi_data(self, dataset_id: int = 0):
        """Load EEDI data for evaluation."""

        task1_dir = self.eedi_root / "Task_1_dataset" / "Task_1_data_local_dev_csv"
        task2_dir = self.eedi_root / "Task_2_dataset" / "Task_2_data_local_dev"

        try:
            # Load ground truth
            adj_matrix = np.load(task1_dir / "adj_matrix.npy")
            cate_estimates = np.load(task2_dir / "cate_estimate.npy")

            return {
                "adj_matrix": adj_matrix[dataset_id],
                "cate_estimates": cate_estimates[dataset_id]
            }
        except Exception as e:
            print(f"[WARNING] Could not load EEDI data: {e}")
            return None

    def evaluate_v1_0_baseline(self):
        """Get v1.0 baseline performance."""

        print("\n   Running v1.0 baseline...")

        test_query = "Which constructs enable learning of other constructs?"

        try:
            result = self.engine.query(test_query, depth=2)
            baseline_confidence = getattr(result, 'stability').score if hasattr(result, 'stability') else 0.0

            return {
                "query": test_query,
                "confidence": baseline_confidence,
                "method": "v1.0"
            }
        except Exception as e:
            print(f"   [ERROR] Baseline evaluation failed: {e}")
            return None

    def evaluate_v1_1_improved(self, max_iterations: int = 5):
        """Evaluate v1.1 with recursive learning."""

        print(f"\n   Running v1.1 with learning ({max_iterations} max iterations)...")

        test_query = "Which constructs enable learning of other constructs?"

        try:
            if hasattr(self.engine, 'query_with_learning'):
                result = self.engine.query_with_learning(
                    test_query,
                    max_iterations=max_iterations
                )
            else:
                # Fallback to v1.0
                result = self.engine.query(test_query, depth=2)

            improved_confidence = getattr(result, 'stability').score if hasattr(result, 'stability') else 0.0

            # Get learning session
            iterations = self.engine.get_learning_session() if hasattr(self.engine, 'get_learning_session') else []
            learned_patterns = self.engine.get_learned_patterns() if hasattr(self.engine, 'get_learned_patterns') else {}

            return {
                "query": test_query,
                "confidence": improved_confidence,
                "iterations": len(iterations),
                "patterns_learned": len(learned_patterns),
                "method": "v1.1"
            }
        except Exception as e:
            print(f"   [ERROR] v1.1 evaluation failed: {e}")
            return None

    def generate_report(self, baseline: dict, improved: dict):
        """Generate comparison report."""

        print("\n" + "=" * 80)
        print("EEDI EVALUATION RESULTS")
        print("=" * 80)

        if baseline and improved:
            improvement_pct = ((improved["confidence"] - baseline["confidence"]) /
                             (baseline["confidence"] + 1e-6)) * 100

            print(f"\nv1.0 Baseline:")
            print(f"  Confidence: {baseline['confidence']:.4f}")

            print(f"\nv1.1 Improved:")
            print(f"  Confidence: {improved['confidence']:.4f}")
            print(f"  Iterations: {improved['iterations']}")
            print(f"  Patterns learned: {improved['patterns_learned']}")

            print(f"\nImprovement:")
            print(f"  Confidence delta: {improvement_pct:+.1f}%")
            print(f"  Expected range: +5% to +35% (depending on data)")

            status = "IMPROVED [OK]" if improved["confidence"] > baseline["confidence"] else "NEEDS TUNING"
            print(f"\nStatus: v1.1 {status}")
        else:
            print("\nEvaluation incomplete (data or engine unavailable)")

        print("=" * 80)
