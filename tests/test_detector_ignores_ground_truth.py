"""Lint tests enforcing CLAUDE.md rules #2 and #3:

- No module under src/detection/, src/attribution/, or src/policy/ may
  reference x_episode_id (ground truth is invisible to the pipeline).
- The same modules may not import src/llm/ (the LLM is downstream of every
  money decision, never upstream of detection/attribution/policy).

These are dynamically parametrized over whatever .py files exist in the
guarded directories, so they keep protecting new code as later phases add
attribution and policy modules — enforced by tests, not convention.
"""

import pathlib

import pytest

GUARDED_DIRS = ["src/detection", "src/attribution", "src/policy"]


def _python_files() -> list[pathlib.Path]:
    root = pathlib.Path(__file__).resolve().parents[1]
    files = []
    for guarded in GUARDED_DIRS:
        d = root / guarded
        if d.exists():
            files.extend(sorted(d.rglob("*.py")))
    return files


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p))
def test_module_does_not_reference_ground_truth(path):
    text = path.read_text()
    assert "x_episode_id" not in text, f"{path} references ground truth (x_episode_id)"


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: str(p))
def test_module_does_not_import_llm_layer(path):
    text = path.read_text()
    assert "src.llm" not in text, f"{path} imports/references the LLM layer (src.llm)"
