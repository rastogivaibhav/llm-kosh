import datetime as dt
import re
from typing import List, Tuple

UTC = dt.timezone.utc
APP_VERSION = "1.0.0"

KINDS = {
    "project", "decision", "prompt", "note", "file", "conversation",
    "receipt", "correction", "gap", "suggestion",
}
VISIBILITIES = ["private", "personal", "work-safe", "shareable", "public", "blocked", "quarantine"]
SHAREABLE_VIS = {"public", "work-safe", "shareable"}
DEFAULT_ROOT_NAME = "AI-Cartridge"

# Secret detectors used by the pack redaction gate.
SECRET_PATTERNS: List[Tuple[str, "re.Pattern"]] = [
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("stripe_live_key", re.compile(r"\b(?:sk|pk|rk)_live_[0-9A-Za-z]{16,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\.[0-9A-Za-z_\-]{10,}\b")),
    ("keyword_secret", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|secret[_-]?key|password|passwd|pwd|access[_-]?token|auth[_-]?token|bearer|client[_-]?secret)\b\s*[:=]\s*(?P<val>[^\s'\";]{6,})"
    )),
]

RECEIPT_SECTIONS = {
    "new decisions": "decision",
    "corrections": "correction",
    "generated files": "file",
    "open gaps": "gap",
    "suggested memory updates": "suggestion",
}
