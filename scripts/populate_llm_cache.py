"""One-off dev utility: populates fixtures/llm_cache.json with a couple of
real Groq responses for representative, non-adversarial inputs. Not part
of the test suite or any make target -- every automated test exercises
the offline/template path exclusively (see tests/test_injection_defense.py).
Run manually, once, whenever the cache needs refreshing:

    .venv/bin/python scripts/populate_llm_cache.py
"""

from dotenv import load_dotenv

load_dotenv()

from src.llm.cache import LlmCache  # noqa: E402
from src.llm.client import get_client  # noqa: E402
from src.llm.narrative import generate_incident_narrative  # noqa: E402
from src.llm.normalize import normalize_error  # noqa: E402


def main() -> None:
    client = get_client()
    cache = LlmCache()

    print("normalizing a bank-timeout error...")
    result = normalize_error(
        error_code="GATEWAY_ERROR",
        error_description="bank server timeout",
        error_source="bank",
        cache=cache,
        client=client,
        offline=False,
    )
    print(" ->", result)

    print("normalizing a customer-side failure...")
    result = normalize_error(
        error_code="BAD_REQUEST_ERROR",
        error_description="insufficient funds in the account",
        error_source="customer",
        cache=cache,
        client=client,
        offline=False,
    )
    print(" ->", result)

    print("generating an incident narrative for a bank-degradation episode...")
    narrative = generate_incident_narrative(
        {
            "slice": {"method": "upi", "x_issuer": "HDFC"},
            "affected_attempts": 909,
            "detected_state": "DEGRADED",
            "recovered_count": 161,
        },
        cache=cache,
        client=client,
        offline=False,
    )
    print(" ->", narrative)

    cache.save()
    print("saved fixtures/llm_cache.json")


if __name__ == "__main__":
    main()
