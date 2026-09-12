from __future__ import annotations

from llm_kosh.core.utils import _ledger_lock


def test_preexisting_empty_ledger_lock_is_initialized_before_locking(tmp_path) -> None:
    lock_path = tmp_path / "ledger" / ".events.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.touch()

    with _ledger_lock(lock_path):
        assert lock_path.stat().st_size >= 1

    assert lock_path.read_bytes()[:1] == b"\0"
