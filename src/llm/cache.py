"""Committed LLM response cache — fixtures/llm_cache.json. The repo runs
offline and reproducibly; the demo survives an API outage. See
anvil-build-plan.md §10.
"""

import hashlib
import json
import pathlib

DEFAULT_CACHE_PATH = pathlib.Path("fixtures/llm_cache.json")


def cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


class LlmCache:
    def __init__(self, path: pathlib.Path = DEFAULT_CACHE_PATH):
        self._path = path
        self._data: dict[str, str] = {}
        if path.exists():
            self._data = json.loads(path.read_text())

    def get(self, prompt: str) -> str | None:
        return self._data.get(cache_key(prompt))

    def set(self, prompt: str, response: str) -> None:
        self._data[cache_key(prompt)] = response

    def save(self) -> None:
        self._path.write_text(json.dumps(self._data, indent=2, sort_keys=True) + "\n")
