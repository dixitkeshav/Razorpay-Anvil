"""Recovery Ledger entry — append-only, immutable. Track 03 bar item 7.

Frozen at the model level (`ConfigDict(frozen=True)`) so that even a
caller holding a live reference to an entry cannot mutate history —
immutability is enforced by the type itself, not by convention.
"""

from pydantic import BaseModel, ConfigDict

from src.policy.models import Action


class LedgerEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    entry_id: str
    payment_id: str
    idempotency_key: str
    action: Action
    rationale: list[str]
    execution_status: str  # "success" | "failed" | "not_executed"
    execution_detail: dict | None
    amount: int
    created_at: int
