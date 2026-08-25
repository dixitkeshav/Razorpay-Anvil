"""Incident narrative generation — L9. Trusted, already-computed incident
data (slice, impact, decision counts) forms the prompt; any exception,
schema violation, or bad cache entry falls back to the deterministic
template below. Same fail-closed contract as src.llm.normalize.
"""

from pydantic import ValidationError

from src.llm.cache import LlmCache
from src.llm.prompts import incident_narrative_prompt
from src.llm.schemas import IncidentNarrative


def _template_fallback(incident_summary: dict) -> IncidentNarrative:
    # Defense in depth: incident_summary is documented as trusted,
    # already-computed data, but the template still doesn't trust that
    # blindly -- a future bug upstream could leak untrusted text into a
    # field assumed safe, and the fallback path (which never calls the
    # model) shouldn't become the leak vector. Only interpolate
    # affected_attempts if it's actually the int it's supposed to be. See
    # docs/JOURNAL.md.
    raw_slice = incident_summary.get("slice", {})
    slice_desc = ", ".join(
        f"{k}={v}" for k, v in raw_slice.items() if isinstance(v, str | int | float)
    ) if isinstance(raw_slice, dict) else ""
    raw_attempts = incident_summary.get("affected_attempts")
    attempts = raw_attempts if isinstance(raw_attempts, int) else "an unknown number of"
    return IncidentNarrative(
        headline=f"Incident detected in slice {slice_desc or 'overall'}",
        summary=(
            f"Anvil detected a success-rate degradation affecting {attempts} attempts. "
            "Automated recovery actions were evaluated per the policy engine."
        ),
        recommended_reading="See the Recovery Ledger for the full per-attempt decision trail.",
    )


def generate_incident_narrative(
    incident_summary: dict,
    cache: LlmCache,
    client=None,
    offline: bool = False,
) -> IncidentNarrative:
    prompt = incident_narrative_prompt(incident_summary)

    cached = cache.get(prompt)
    if cached is not None:
        try:
            return IncidentNarrative.model_validate_json(cached)
        except ValidationError:
            pass

    if offline or client is None:
        return _template_fallback(incident_summary)

    from src.llm.client import complete

    try:
        raw = complete(client, prompt)
        parsed = IncidentNarrative.model_validate_json(raw)
    except Exception:
        return _template_fallback(incident_summary)

    cache.set(prompt, parsed.model_dump_json())
    return parsed
