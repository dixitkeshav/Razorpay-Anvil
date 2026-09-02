"""Incident question-answering -- L9. Trusted, already-computed incident
summaries (slice, impact, attribution) form the prompt context; the
operator's question is untrusted user text and is always fenced (see
src.llm.prompts). Same fail-closed contract as src.llm.narrative: a
schema violation or network failure falls back to a deterministic
template that never quotes the question back.
"""

from pydantic import ValidationError

from src.llm.cache import LlmCache
from src.llm.prompts import incident_qa_prompt
from src.llm.schemas import IncidentQAAnswer


def _template_fallback(incidents: list[dict]) -> IncidentQAAnswer:
    if not incidents:
        return IncidentQAAnswer(
            answer="No incidents have been detected in this run.",
            incident_indices=[],
        )

    lines = []
    indices = []
    for inc in incidents:
        raw_slice = inc.get("slice", {})
        slice_desc = ", ".join(
            f"{k}={v}" for k, v in raw_slice.items() if isinstance(v, str | int | float)
        ) if isinstance(raw_slice, dict) else "overall"
        idx = inc.get("incident_index")
        if isinstance(idx, int):
            indices.append(idx)
        attempts = inc.get("affected_attempts")
        attempts_desc = attempts if isinstance(attempts, int) else "an unknown number of"
        lines.append(f"incident {idx}: {slice_desc} ({attempts_desc} attempts affected)")

    return IncidentQAAnswer(
        answer=(
            "Detected incidents on this run: " + "; ".join(lines) +
            ". See the attribution trace for the full statistical breakdown of each."
        )[:800],
        incident_indices=indices,
    )


def answer_question(
    question: str,
    incidents: list[dict],
    cache: LlmCache,
    client=None,
    offline: bool = False,
) -> IncidentQAAnswer:
    prompt = incident_qa_prompt(question, incidents)

    cached = cache.get(prompt)
    if cached is not None:
        try:
            return IncidentQAAnswer.model_validate_json(cached)
        except ValidationError:
            pass

    if offline or client is None:
        return _template_fallback(incidents)

    from src.llm.client import complete

    try:
        raw = complete(client, prompt)
        parsed = IncidentQAAnswer.model_validate_json(raw)
    except Exception:
        return _template_fallback(incidents)

    cache.set(prompt, parsed.model_dump_json())
    return parsed
