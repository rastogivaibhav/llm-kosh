"""Regression tests for v2.1.1 hardening:

- Hash-chained, tamper-evident ledger (prev/row_hash)
- verify_ledger chain verification with legacy compatibility
- Concurrent append safety
- Frontmatter list round-trip
"""
import json
import multiprocessing as mp
from pathlib import Path

import pytest

from llm_kosh.core.utils import (
    GENESIS_HASH,
    append_ledger,
    frontmatter,
    parse_frontmatter,
    row_hash,
)
from llm_kosh.engine.commands import verify_ledger


@pytest.fixture
def cart(tmp_path: Path) -> Path:
    (tmp_path / "LLM_KOSH.json").write_text("{}")
    (tmp_path / "ledger").mkdir()
    return tmp_path


def _rows(cart: Path):
    text = (cart / "ledger" / "events.jsonl").read_text()
    return [json.loads(l) for l in text.splitlines() if l.strip()]


class TestHashChain:
    def test_rows_carry_chain_fields(self, cart):
        append_ledger(cart, "a", {"x": 1})
        append_ledger(cart, "b", {"x": 2})
        rows = _rows(cart)
        assert rows[0]["prev"] == GENESIS_HASH
        assert rows[1]["prev"] == rows[0]["row_hash"]
        for r in rows:
            assert row_hash(r) == r["row_hash"]

    def test_verify_ledger_reports_intact(self, cart):
        for i in range(5):
            append_ledger(cart, "evt", {"i": i})
        result = verify_ledger(cart, quiet=True)
        assert result["chain_intact"] is True
        assert result["chained_rows"] == 5
        assert result["bad_rows"] == 0

    def test_tamper_payload_detected(self, cart):
        for i in range(3):
            append_ledger(cart, "evt", {"i": i})
        path = cart / "ledger" / "events.jsonl"
        lines = path.read_text().splitlines()
        row = json.loads(lines[1])
        row["i"] = 999  # silent payload edit
        lines[1] = json.dumps(row, ensure_ascii=False)
        path.write_text("\n".join(lines) + "\n")
        result = verify_ledger(cart, quiet=True)
        assert result["chain_intact"] is False
        assert any(b["type"] == "row_hash_mismatch" for b in result["chain_breaks"])

    def test_deleted_row_detected(self, cart):
        for i in range(4):
            append_ledger(cart, "evt", {"i": i})
        path = cart / "ledger" / "events.jsonl"
        lines = path.read_text().splitlines()
        del lines[1]  # silent deletion
        path.write_text("\n".join(lines) + "\n")
        result = verify_ledger(cart, quiet=True)
        assert result["chain_intact"] is False
        assert any(b["type"] == "broken_link" for b in result["chain_breaks"])

    def test_legacy_rows_still_valid(self, cart):
        path = cart / "ledger" / "events.jsonl"
        legacy = {"event_id": "evt_legacy", "event": "old", "time": "2025-01-01T00:00:00Z"}
        path.write_text(json.dumps(legacy) + "\n")
        append_ledger(cart, "new", {"i": 1})
        result = verify_ledger(cart, quiet=True)
        assert result["legacy_rows"] == 1
        assert result["chained_rows"] == 1
        assert result["bad_rows"] == 0
        assert result["chain_intact"] is True


def _worker(args):
    root_str, i = args
    root = Path(root_str)
    for j in range(25):
        append_ledger(root, "stress", {"w": i, "j": j})


class TestConcurrency:
    def test_concurrent_appends_no_corruption(self, cart):
        with mp.Pool(4) as pool:
            pool.map(_worker, [(str(cart), i) for i in range(4)])
        rows = _rows(cart)
        assert len(rows) == 100
        result = verify_ledger(cart, quiet=True)
        assert result["bad_rows"] == 0
        # every row individually verifiable even if interleaving reordered links
        for r in rows:
            assert row_hash(r) == r["row_hash"]


class TestFrontmatterRoundTrip:
    def test_list_values_round_trip(self):
        meta, _ = parse_frontmatter(frontmatter({"tags": ["acos", "tracing"]}) + "\nbody")
        assert meta["tags"] == ["acos", "tracing"]

    def test_quoted_and_plain_strings_unaffected(self):
        meta, _ = parse_frontmatter(frontmatter({"title": "Test: colon", "kind": "note"}) + "\nbody")
        assert meta["title"] == "Test: colon"
        assert meta["kind"] == "note"
