"""Phase 7 gate: the Recovery Ledger is append-only. See docs/PHASES.md.
"""

import pydantic
import pytest

from src.ledger.models import LedgerEntry
from src.ledger.store import LedgerStore
from src.policy.models import Action


def _append(store: LedgerStore, key: str, action: Action = Action.RETRY) -> LedgerEntry:
    return store.append(
        payment_id="pay_1",
        idempotency_key=key,
        action=action,
        rationale=["test"],
        execution_status="success",
        execution_detail=None,
        amount=1000,
        created_at=1_800_000_000,
    )


def test_no_update_or_delete_method_exists():
    store = LedgerStore()
    for forbidden in ("update", "delete", "remove", "clear", "truncate", "set", "modify"):
        assert not hasattr(store, forbidden), f"LedgerStore must not expose {forbidden}()"


def test_entries_are_frozen():
    store = LedgerStore()
    entry = _append(store, "key-1")
    with pytest.raises(pydantic.ValidationError):
        entry.execution_status = "tampered"


def test_append_only_grows_in_order():
    store = LedgerStore()
    e0 = _append(store, "key-0")
    e1 = _append(store, "key-1")
    e2 = _append(store, "key-2")

    assert len(store) == 3
    entries = store.read_all()
    assert [e.sequence for e in entries] == [0, 1, 2]
    assert [e.entry_id for e in entries] == [e0.entry_id, e1.entry_id, e2.entry_id]


def test_read_all_returns_a_copy_not_the_internal_list():
    store = LedgerStore()
    _append(store, "key-0")
    entries = store.read_all()
    entries.pop()
    entries.append("garbage")

    assert len(store) == 1
    assert store.read_all()[0].idempotency_key == "key-0"


def test_persisted_file_only_ever_grows(tmp_path):
    path = tmp_path / "ledger.jsonl"

    store1 = LedgerStore(path)
    _append(store1, "key-0")
    _append(store1, "key-1")
    assert path.read_text().count("\n") == 2

    # a fresh store over the same file loads prior history, and appending
    # more only adds -- never truncates or rewrites what's already there
    store2 = LedgerStore(path)
    assert len(store2) == 2
    _append(store2, "key-2")
    assert len(store2) == 3
    assert path.read_text().count("\n") == 3

    store3 = LedgerStore(path)
    assert len(store3) == 3
    assert [e.idempotency_key for e in store3.read_all()] == ["key-0", "key-1", "key-2"]
