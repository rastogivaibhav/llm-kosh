"""
Causal discourse marker extraction.
Detects temporal/causal language patterns in text to infer
ordering relationships between facts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class DiscourseMark:
    """A detected temporal or causal discourse marker."""
    marker: str
    position: int
    marker_type: str  # "sequence" | "causality" | "precedence" | "simultaneity"


# Regex patterns per discourse type
_PATTERNS: dict[str, list[str]] = {
    "sequence": [
        r"\bthen\b", r"\bnext\b", r"\bsubsequently\b", r"\bfollowing\b",
        r"\blater\b", r"\bafterward(?:s)?\b", r"\bthe next\b",
        r"\bafter that\b", r"\bfinally\b", r"\blastly\b", r"\bultimately\b",
    ],
    "causality": [
        r"\bbecause\b", r"\bcaused\b", r"\bas a result\b", r"\bas a consequence\b",
        r"\bdue to\b", r"\bowing to\b", r"\bthus\b", r"\bhence\b",
        r"\btherefore\b", r"\bconsequently\b",
    ],
    "precedence": [
        r"\bbefore\b", r"\bprior to\b", r"\bearlier\b", r"\bpreviously\b",
        r"\binitially\b", r"\bfirst\b",
    ],
    "simultaneity": [
        r"\bmeanwhile\b", r"\bduring\b", r"\bwhile\b", r"\bwhilst\b",
        r"\bat the same time\b", r"\bsimultaneously\b",
    ],
}

# Map marker type → (EdgeType string, confidence)
_EDGE_MAP: dict[str, tuple[str, float]] = {
    "sequence":    ("ENABLES", 0.75),
    "causality":   ("CAUSES",  0.85),
    "precedence":  ("ENABLES", 0.70),
    "simultaneity": ("",       0.0),   # no ordering edge for simultaneous events
}


def extract_discourse_markers(text: str) -> List[DiscourseMark]:
    """Return all discourse markers found in text, sorted by position."""
    marks: List[DiscourseMark] = []
    for marker_type, patterns in _PATTERNS.items():
        for pattern in patterns:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                marks.append(DiscourseMark(
                    marker=m.group().lower(),
                    position=m.start(),
                    marker_type=marker_type,
                ))
    return sorted(marks, key=lambda x: x.position)


def infer_temporal_edge(
    target_text: str,
) -> Tuple[str, float]:
    """
    Look for discourse markers at the start of target_text that signal
    a causal/temporal relationship with whatever came before.

    Returns (edge_type_str, confidence) or ("", 0.0) if none found.
    Only markers in the first 120 characters are considered (opening clause).
    """
    marks = extract_discourse_markers(target_text[:120])
    for mark in marks:
        edge_type, confidence = _EDGE_MAP[mark.marker_type]
        if edge_type:
            return edge_type, confidence
    return "", 0.0


def should_auto_create_edge(
    source_text: str,
    target_text: str,
) -> Tuple[bool, str, float]:
    """
    Decide whether to auto-create a causal edge from source to target.

    Returns (should_create, edge_type, confidence).
    Only creates edges when confidence >= 0.70.
    """
    edge_type, confidence = infer_temporal_edge(target_text)
    if edge_type and confidence >= 0.70:
        return True, edge_type, confidence
    return False, "", 0.0
