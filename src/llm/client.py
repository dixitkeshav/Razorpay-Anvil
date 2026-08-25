"""Groq client — the only place a network call to an LLM provider is
made. src/detection/, src/attribution/, and src/policy/ may not import
this module, directly or transitively — enforced by
tests/test_llm_cannot_reach_policy.py.
"""

import os

from groq import Groq


def is_offline() -> bool:
    return os.environ.get("ANVIL_LLM_OFFLINE", "0") == "1"


def get_client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def get_model() -> str:
    return os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def complete(client: Groq, prompt: str, model: str | None = None) -> str:
    response = client.chat.completions.create(
        model=model or get_model(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content
