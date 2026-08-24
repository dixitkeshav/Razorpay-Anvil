"""Append-only Recovery Ledger — L7.

No update or delete method exists on this class — enforced by
construction, not convention. `read_all()` returns a copy, so a caller
mutating the returned list cannot affect ledger state. The optional
on-disk file is only ever opened in append mode, never write/truncate
mode, so a restart cannot lose or reorder history.
"""

import pathlib
import threading
import uuid

from src.ledger.models import LedgerEntry
from src.policy.models import Action


class LedgerStore:
    def __init__(self, path: str | pathlib.Path | None = None):
        self._path = pathlib.Path(path) if path else None
        self._entries: list[LedgerEntry] = []
        self._by_idempotency_key: dict[str, LedgerEntry] = {}
        self._lock = threading.Lock()
        if self._path and self._path.exists():
            self._load()

    def _load(self) -> None:
        with self._path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = LedgerEntry.model_validate_json(line)
                self._entries.append(entry)
                self._by_idempotency_key[entry.idempotency_key] = entry

    def append(
        self,
        payment_id: str,
        idempotency_key: str,
        action: Action,
        rationale: list[str],
        execution_status: str,
        execution_detail: dict | None,
        amount: int,
        created_at: int,
    ) -> LedgerEntry:
        with self._lock:
            entry = LedgerEntry(
                sequence=len(self._entries),
                entry_id=str(uuid.uuid4()),
                payment_id=payment_id,
                idempotency_key=idempotency_key,
                action=action,
                rationale=rationale,
                execution_status=execution_status,
                execution_detail=execution_detail,
                amount=amount,
                created_at=created_at,
            )
            self._entries.append(entry)
            self._by_idempotency_key[idempotency_key] = entry
            if self._path:
                with self._path.open("a") as f:
                    f.write(entry.model_dump_json() + "\n")
            return entry

    def find_by_idempotency_key(self, key: str) -> LedgerEntry | None:
        return self._by_idempotency_key.get(key)

    def read_all(self) -> list[LedgerEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
