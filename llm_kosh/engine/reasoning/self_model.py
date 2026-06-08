from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from llm_kosh.engine.reasoning.trace import QueryTrace
from llm_kosh.engine.reasoning.healer import QueryParams
from llm_kosh.engine.reasoning.lyapunov_critic import LyapunovCritic

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SEVEN_DAYS = 7 * 86_400.0
_DEPTH_CAP = 8
_PREFIX_ROTATION = ["0", "1", "2", "3"]


# ---------------------------------------------------------------------------
# Component 1: ReasoningPattern
# ---------------------------------------------------------------------------

@dataclass
class ReasoningPattern:
    """A detected pattern in reasoning behaviour across multiple traces."""

    pattern_type: str
    description: str
    supporting_trace_ids: List[str]
    confidence: float          # 0.0–1.0, how many observations support it
    first_seen: float          # Unix timestamp
    last_seen: float           # Unix timestamp

    def to_dict(self) -> dict:
        return {
            "pattern_type": self.pattern_type,
            "description": self.description,
            "supporting_trace_ids": list(self.supporting_trace_ids),
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReasoningPattern":
        return cls(
            pattern_type=data["pattern_type"],
            description=data["description"],
            supporting_trace_ids=list(data.get("supporting_trace_ids", [])),
            confidence=float(data.get("confidence", 0.0)),
            first_seen=float(data.get("first_seen", 0.0)),
            last_seen=float(data.get("last_seen", 0.0)),
        )


# ---------------------------------------------------------------------------
# Component 2: BiasProfile
# ---------------------------------------------------------------------------

_DEFAULT_BIASES = {
    "recency_bias": 0.0,
    "high_confidence_bias": 0.0,
    "domain_bias": 0.0,
    "compression_preference": 0.0,
}


@dataclass
class BiasProfile:
    """Tracks scored biases in reasoning behaviour."""

    biases: Dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_BIASES))

    def dominant_bias(self) -> Optional[str]:
        """Return the key with the highest score if it exceeds 0.3, else None."""
        if not self.biases:
            return None
        key = max(self.biases, key=lambda k: self.biases[k])
        return key if self.biases[key] > 0.3 else None

    def to_dict(self) -> dict:
        return {"biases": dict(self.biases)}

    @classmethod
    def from_dict(cls, data: dict) -> "BiasProfile":
        raw = data.get("biases", {})
        biases = dict(_DEFAULT_BIASES)
        biases.update({k: float(v) for k, v in raw.items()})
        return cls(biases=biases)


# ---------------------------------------------------------------------------
# Component 3: SelfModel
# ---------------------------------------------------------------------------

class SelfModel:
    """
    Persistent reasoning bias tracker.

    Stored as JSON at ``{root}/.self_model.json``.
    """

    def __init__(self, root: Path) -> None:
        self._path = Path(root) / ".self_model.json"
        self.patterns: List[ReasoningPattern] = []
        self.bias_profile: BiasProfile = BiasProfile(biases=dict(_DEFAULT_BIASES))
        self._trace_count: int = 0
        self._bottleneck_counts: Dict[str, int] = {}
        # Internal sliding window for pattern detection
        self._recent_statuses: List[str] = []          # last N stability_status values
        self._recent_escape_flags: List[bool] = []     # last 10 escape_triggered values
        # Track anchor prefix distribution for domain_bias
        self._seen_anchor_prefixes: Dict[str, int] = {}
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def observe(self, trace: QueryTrace) -> None:
        """Update patterns and bias profile from a new trace."""
        self._trace_count += 1
        self._update_biases(trace)
        self._update_patterns(trace)
        self.save()

    def get_bias_profile(self) -> BiasProfile:
        return self.bias_profile

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        data = {
            "patterns": [p.to_dict() for p in self.patterns],
            "bias_profile": self.bias_profile.to_dict(),
            "trace_count": self._trace_count,
            "bottleneck_counts": dict(self._bottleneck_counts),
            "recent_statuses": list(self._recent_statuses),
            "recent_escape_flags": list(self._recent_escape_flags),
            "seen_anchor_prefixes": dict(self._seen_anchor_prefixes),
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self.patterns = [ReasoningPattern.from_dict(p) for p in data.get("patterns", [])]
            self.bias_profile = BiasProfile.from_dict(data.get("bias_profile", {}))
            self._trace_count = int(data.get("trace_count", 0))
            self._bottleneck_counts = {str(k): int(v) for k, v in data.get("bottleneck_counts", {}).items()}
            self._recent_statuses = list(data.get("recent_statuses", []))
            self._recent_escape_flags = list(data.get("recent_escape_flags", []))
            self._seen_anchor_prefixes = {str(k): int(v) for k, v in data.get("seen_anchor_prefixes", {}).items()}
        except Exception:
            # Corrupt or unreadable — start fresh without crashing
            self.patterns = []
            self.bias_profile = BiasProfile(biases=dict(_DEFAULT_BIASES))
            self._trace_count = 0
            self._bottleneck_counts = {}
            self._recent_statuses = []
            self._recent_escape_flags = []
            self._seen_anchor_prefixes = {}

    # ------------------------------------------------------------------
    # Internal: bias updates
    # ------------------------------------------------------------------

    def _update_biases(self, trace: QueryTrace) -> None:
        b = self.bias_profile.biases
        now = time.time()

        # Step 1: Decay ALL bias scores by 0.005 per observation
        for key in list(b.keys()):
            b[key] = max(0.0, b[key] - 0.005)

        # Step 2: Apply increments based on trace signals
        # recency_bias
        query_t = trace.query_time if trace.query_time is not None else trace.executed_at
        if (now - query_t) < _SEVEN_DAYS and len(trace.anchor_ids) > 0:
            b["recency_bias"] = min(1.0, b["recency_bias"] + 0.1)

        # high_confidence_bias
        if (
            trace.stability_status == "stable"
            and trace.lyapunov_dimensions.get("degeneracy", 0.0) < 0.5
        ):
            b["high_confidence_bias"] = min(1.0, b["high_confidence_bias"] + 0.1)

        # domain_bias — track anchor prefixes
        if trace.anchor_ids:
            new_prefixes = [aid[:4] for aid in trace.anchor_ids if len(aid) >= 4]
            total_new = len(new_prefixes)
            if total_new > 0:
                seen_count = sum(
                    1 for p in new_prefixes if self._seen_anchor_prefixes.get(p, 0) > 0
                )
                if seen_count / total_new > 0.6:
                    b["domain_bias"] = min(1.0, b["domain_bias"] + 0.1)
            # Update seen prefix counts
            for p in new_prefixes:
                self._seen_anchor_prefixes[p] = self._seen_anchor_prefixes.get(p, 0) + 1

        # compression_preference
        if (
            trace.stability_score > 0.7
            and trace.bundle_summary.get("max_degeneracy", 0) <= 1
        ):
            b["compression_preference"] = min(1.0, b["compression_preference"] + 0.1)

        # Step 3: Clamp all to [0.0, 1.0]
        for key in list(b.keys()):
            b[key] = max(0.0, min(1.0, b[key]))

        # Update bottleneck counts
        if trace.lyapunov_dimensions:
            bottleneck_dim = min(
                trace.lyapunov_dimensions, key=lambda k: trace.lyapunov_dimensions[k]
            )
            self._bottleneck_counts[bottleneck_dim] = (
                self._bottleneck_counts.get(bottleneck_dim, 0) + 1
            )

    # ------------------------------------------------------------------
    # Internal: pattern updates
    # ------------------------------------------------------------------

    def _update_patterns(self, trace: QueryTrace) -> None:
        now = time.time()

        # --- Sliding windows ---
        self._recent_statuses.append(trace.stability_status)
        if len(self._recent_statuses) > 20:
            self._recent_statuses.pop(0)

        self._recent_escape_flags.append(trace.escape_triggered)
        if len(self._recent_escape_flags) > 10:
            self._recent_escape_flags.pop(0)

        # --- Pattern: stability_plateau (same status in 3+ consecutive traces) ---
        if len(self._recent_statuses) >= 3:
            last3 = self._recent_statuses[-3:]
            if len(set(last3)) == 1:
                plateau_status = last3[0]
                self._upsert_pattern(
                    pattern_type="stability_plateau",
                    description=f"stability_status '{plateau_status}' repeated in last 3+ consecutive traces",
                    trace_id=trace.trace_id,
                    now=now,
                    confidence=min(1.0, len(self._recent_statuses) / 10.0),
                )

        # --- Pattern: frequent_escape (escape_triggered in >40% of recent 10 traces) ---
        if len(self._recent_escape_flags) >= 1:
            escape_ratio = sum(1 for f in self._recent_escape_flags if f) / len(
                self._recent_escape_flags
            )
            if escape_ratio > 0.4:
                self._upsert_pattern(
                    pattern_type="frequent_escape",
                    description=f"escape_triggered in {escape_ratio:.0%} of recent {len(self._recent_escape_flags)} traces",
                    trace_id=trace.trace_id,
                    now=now,
                    confidence=min(1.0, escape_ratio),
                )

    def _upsert_pattern(
        self,
        pattern_type: str,
        description: str,
        trace_id: str,
        now: float,
        confidence: float,
    ) -> None:
        """Insert or update a pattern in self.patterns."""
        for p in self.patterns:
            if p.pattern_type == pattern_type:
                p.last_seen = now
                p.confidence = confidence
                p.description = description
                if trace_id not in p.supporting_trace_ids:
                    p.supporting_trace_ids.append(trace_id)
                return
        self.patterns.append(
            ReasoningPattern(
                pattern_type=pattern_type,
                description=description,
                supporting_trace_ids=[trace_id],
                confidence=confidence,
                first_seen=now,
                last_seen=now,
            )
        )


# ---------------------------------------------------------------------------
# Component 4: SelfModelController
# ---------------------------------------------------------------------------

class SelfModelController:
    """Counteracts known biases by adjusting QueryParams."""

    def adapt_params(self, base_params: QueryParams, self_model: SelfModel) -> QueryParams:
        """Return a new QueryParams adjusted to counteract observed biases."""
        biases = self_model.bias_profile.biases

        depth = base_params.depth
        temporal_offset = base_params.temporal_offset_secs
        anchor_prefix = base_params.anchor_prefix_filter

        # domain_bias > 0.5 → rotate anchor prefix
        if biases.get("domain_bias", 0.0) > 0.5:
            anchor_prefix = _PREFIX_ROTATION[self_model._trace_count % 4]

        # high_confidence_bias > 0.5 → force depth += 1 to explore more paths
        if biases.get("high_confidence_bias", 0.0) > 0.5:
            depth = min(depth + 1, _DEPTH_CAP)

        # compression_preference > 0.4 → depth += 1 to force mechanistic exploration
        if biases.get("compression_preference", 0.0) > 0.4:
            depth = min(depth + 1, _DEPTH_CAP)

        # recency_bias > 0.6 → look 1 day further back (never negative)
        if biases.get("recency_bias", 0.0) > 0.6:
            temporal_offset = max(0.0, temporal_offset - 86_400.0)

        return QueryParams(
            score_threshold=base_params.score_threshold,
            depth=depth,
            temporal_offset_secs=temporal_offset,
            force_contradiction_surface=base_params.force_contradiction_surface,
            demote_hypothetical=base_params.demote_hypothetical,
            anchor_prefix_filter=anchor_prefix,
        )


# ---------------------------------------------------------------------------
# Component 5: get_adapted_weights
# ---------------------------------------------------------------------------

def get_adapted_weights(self_model: SelfModel, base_weights: dict) -> dict:
    """
    Adapt LyapunovCritic weights based on self-model observations.

    If any Lyapunov dimension has been the bottleneck (lowest scorer) in
    more than 60% of observed traces, boost its weight by 0.05.
    """
    weights = dict(base_weights)
    trace_count = self_model._trace_count
    if trace_count == 0:
        return weights

    bottleneck_counts = self_model._bottleneck_counts
    for dim, count in bottleneck_counts.items():
        if count / trace_count > 0.6:
            if dim in weights:
                weights[dim] = min(1.0, weights[dim] + 0.05)
            break  # boost only the most-bottlenecked dimension

    return weights
