"""Error normalization — L9. `error_description` is attacker-controlled
(CLAUDE.md's Untrusted input section) and flows into the prompt only
through the untrusted fence in src.llm.prompts, with structured
Pydantic-validated output. A schema violation, a cache-entry that fails
validation, or any exception from the network call all fall back to the
deterministic template below — never raw or malformed model output.
"""

from pydantic import ValidationError

from src.llm.cache import LlmCache
from src.llm.prompts import error_normalization_prompt
from src.llm.schemas import NormalizedError

_CATEGORY_BY_SOURCE = {
    "bank": "bank",
    "gateway": "gateway",
    "customer": "customer",
    "business": "business",
}


def _template_fallback(
    error_code: str | None, error_source: str | None
) -> NormalizedError:
    category = _CATEGORY_BY_SOURCE.get(error_source or "", "gateway")
    return NormalizedError(
        customer_message=(
            f"Your payment could not be completed ({error_code or 'unknown error'}). "
            "Please try again."
        ),
        category=category,
        confidence=0.5,
    )


def normalize_error(
    error_code: str | None,
    error_description: str | None,
    error_source: str | None,
    cache: LlmCache,
    client=None,
    offline: bool = False,
) -> NormalizedError:
    prompt = error_normalization_prompt(error_code, error_description, error_source)

    cached = cache.get(prompt)
    if cached is not None:
        try:
            return NormalizedError.model_validate_json(cached)
        except ValidationError:
            pass  # a bad cache entry -- fall through rather than propagate it

    if offline or client is None:
        return _template_fallback(error_code, error_source)

    from src.llm.client import complete

    try:
        raw = complete(client, prompt)
        parsed = NormalizedError.model_validate_json(raw)
    except Exception:
        # covers JSON/schema violations and any network or API failure --
        # all fail closed to the same safe template, never propagate a
        # malformed or unvalidated model response.
        return _template_fallback(error_code, error_source)

    cache.set(prompt, parsed.model_dump_json())
    return parsed
