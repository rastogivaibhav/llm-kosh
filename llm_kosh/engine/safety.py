from typing import List, Tuple

from llm_kosh.core.constants import SECRET_PATTERNS


def scan_secrets(text: str) -> List[Tuple[str, str]]:
    """Return list of (label, matched_value) for any secrets found."""
    findings: List[Tuple[str, str]] = []
    for label, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            val = m.groupdict().get("val") or m.group(0)
            findings.append((label, val))
    return findings


def redact_text(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    findings: List[Tuple[str, str]] = []
    out = text
    for label, pat in SECRET_PATTERNS:
        def _sub(m):
            val = m.groupdict().get("val") or m.group(0)
            findings.append((label, val))
            whole = m.group(0)
            if "val" in m.groupdict() and m.group("val"):
                return whole.replace(m.group("val"), f"«REDACTED:{label}»")
            return f"«REDACTED:{label}»"
        out = pat.sub(_sub, out)
    return out, findings


DEFAULT_POLICY = {
    "default_visibility": "private",
    "blocked_terms": ["client secret", "api key", "password", "private key"],
    "allowed_export_visibility": ["public", "shareable", "work-safe"],
    "require_redaction": True,
    "intake": {
        "auto_apply_receipts": False,
        "auto_apply_folder_notes": False,
        "require_review_for_corrections": True,
        "require_review_for_private": True
    },
    "daemon": {
        "watched_directories": []
    }
}

def policy_path(root) -> str:
    return root / "LLM_KOSH_POLICY.json"

def load_policy(root) -> dict:
    from llm_kosh.core.utils import read_json
    p = policy_path(root)
    if not p.exists():
        legacy = root / "CARTRIDGE_POLICY.json"
        if legacy.exists():
            p = legacy
    if p.exists():
        pol = dict(DEFAULT_POLICY)
        pol.update(read_json(p, {}))
        return pol
    return dict(DEFAULT_POLICY)
