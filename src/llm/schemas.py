"""Structured LLM outputs — L9. Every LLM response is validated against
one of these schemas before use; a schema violation falls back to a
template narrative (src.llm.normalize / src.llm.narrative). No field on
these schemas is ever read by src/policy/ or src/ledger/ — L9 is
downstream of every money decision and terminal. Enforced by
tests/test_llm_cannot_reach_policy.py.
"""

from pydantic import BaseModel, Field


class NormalizedError(BaseModel):
    customer_message: str = Field(max_length=280)
    category: str  # "bank" | "gateway" | "customer" | "business"
    confidence: float = Field(ge=0.0, le=1.0)


class IncidentNarrative(BaseModel):
    headline: str = Field(max_length=120)
    summary: str = Field(max_length=800)
    recommended_reading: str = Field(max_length=280)
