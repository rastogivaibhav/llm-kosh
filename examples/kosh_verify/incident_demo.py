from __future__ import annotations

import tempfile
from pathlib import Path

from llm_kosh.verify import seed_incident_cartridge


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="kosh_verify_demo_"))
    kv = seed_incident_cartridge(root)
    report = kv.verify(
        "Why did checkout fail and what evidence contradicts the explanation?",
        temporal_context="2026-05-01T13:30:00+00:00",
        depth=5,
        dialectic=True,
    )
    print(report.to_json(indent=2))
    print("\n--- provenance summary ---")
    print(kv.explain_provenance(report))


if __name__ == "__main__":
    main()
