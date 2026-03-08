from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_IMPORT_PREFIXES = (
    "src.output",
    "src.solver",
    "src.utils.csv_parser",
    "src.utils.distance_calculator",
    "src.utils.yaml_parser",
    "src.visualization",
)


def _import_targets(app_path: Path) -> list[str]:
    tree = ast.parse(app_path.read_text())
    targets: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.append(node.module)

    return targets


def test_app_py_uses_application_boundaries_only():
    app_path = Path(__file__).resolve().parents[2] / "app.py"

    forbidden_targets = [
        target
        for target in _import_targets(app_path)
        if target.startswith(FORBIDDEN_IMPORT_PREFIXES)
    ]

    assert forbidden_targets == []
