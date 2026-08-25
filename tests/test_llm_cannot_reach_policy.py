"""Phase 9 gate + CLAUDE.md rule #2: src/detection/, src/attribution/, and
src/policy/ have no import path to src/llm/ — direct OR transitive. This
walks the actual import graph (via ast, not a text grep), so a violation
hidden behind two or three hops of intermediate modules is still caught.

tests/test_detector_ignores_ground_truth.py already does a cheap textual
"src.llm" grep on each file in those directories; this test is the
stronger, authoritative version CLAUDE.md names explicitly — it also
catches the case that grep can't: module A (outside the guarded
directories) imports src.llm, and a guarded module imports module A.
"""

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARDED_PACKAGES = ["src.detection", "src.attribution", "src.policy"]


def _module_name(path: pathlib.Path) -> str:
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _imports_of(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def _build_import_graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for path in (ROOT / "src").rglob("*.py"):
        graph[_module_name(path)] = _imports_of(path)
    return graph


def _reachable_src_modules(graph: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        mod = stack.pop()
        if mod in seen:
            continue
        seen.add(mod)
        for dep in graph.get(mod, ()):
            if dep == "src" or dep.startswith("src."):
                stack.append(dep)
    return seen


def test_no_transitive_import_path_from_guarded_layers_to_llm():
    graph = _build_import_graph()

    for guarded_pkg in GUARDED_PACKAGES:
        guarded_modules = [
            m for m in graph if m == guarded_pkg or m.startswith(guarded_pkg + ".")
        ]
        assert guarded_modules, f"no modules found under {guarded_pkg} -- test setup is broken"

        for mod in guarded_modules:
            reachable = _reachable_src_modules(graph, mod)
            llm_hits = {m for m in reachable if m == "src.llm" or m.startswith("src.llm.")}
            assert not llm_hits, f"{mod} has an import path to {llm_hits}"


def test_llm_package_exists_and_is_nontrivial():
    """Guard against this test passing vacuously because src/llm/ is empty."""
    llm_files = list((ROOT / "src" / "llm").glob("*.py"))
    non_init = [f for f in llm_files if f.name != "__init__.py"]
    assert len(non_init) >= 3
