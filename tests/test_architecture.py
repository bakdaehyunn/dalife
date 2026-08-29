from __future__ import annotations

import ast
from pathlib import Path


PACKAGE = Path(__file__).parents[1] / "src" / "darchivebot"


def module_dependencies(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    dependencies: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("darchivebot."):
            dependencies.add(node.module.removeprefix("darchivebot.").split(".", 1)[0])
    return dependencies


def test_internal_module_graph_has_no_cycles():
    paths = {path.stem: path for path in PACKAGE.glob("*.py") if path.stem != "__init__"}
    graph = {name: module_dependencies(path) & paths.keys() for name, path in paths.items()}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visiting:
            raise AssertionError(f"circular import detected at {name}")
        if name in visited:
            return
        visiting.add(name)
        for dependency in graph[name]:
            visit(dependency)
        visiting.remove(name)
        visited.add(name)

    for module in graph:
        visit(module)


def test_sqlite_is_confined_to_persistence():
    offenders: list[str] = []
    for path in PACKAGE.rglob("*.py"):
        if "persistence" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name == "sqlite3" for alias in node.names):
                offenders.append(str(path.relative_to(PACKAGE)))
            if isinstance(node, ast.ImportFrom) and node.module == "sqlite3":
                offenders.append(str(path.relative_to(PACKAGE)))
    assert offenders == []


def test_semantic_graph_uses_shared_ontology_not_jsonld_exporter():
    dependencies = module_dependencies(PACKAGE / "semantic_graph.py")
    assert "ontology" in dependencies
    assert "graph" not in dependencies


def test_repository_boundaries_do_not_expose_sqlite_rows():
    public_contracts = [PACKAGE / "ports.py", *sorted((PACKAGE / "persistence").glob("*_repository.py"))]
    for path in public_contracts:
        source = path.read_text(encoding="utf-8")
        assert "sqlite3.Row" not in source, path


def test_archive_store_is_a_thin_sql_free_compatibility_facade():
    source = (PACKAGE / "storage.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) < 100
    for sql_keyword in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE"):
        assert sql_keyword not in source

