#!/usr/bin/env python3
"""Fail when public release metadata drifts across the reference stack."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def app_version(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if (
            any(
                isinstance(target, ast.Name) and target.id == "__version__"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def main() -> int:
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    errors: list[str] = []
    if not SEMVER.fullmatch(expected):
        errors.append(
            f"VERSION: expected a stable MAJOR.MINOR.PATCH value, found {expected!r}"
        )

    backend = load_toml(ROOT / "backend" / "pyproject.toml")
    backend_project = backend["project"]
    assert isinstance(backend_project, dict)
    backend_name = backend_project["name"]
    values: dict[str, object] = {
        "backend/pyproject.toml": backend_project["version"],
        "backend/app/__init__.py": app_version(
            ROOT / "backend" / "app" / "__init__.py"
        ),
    }

    uv_lock = load_toml(ROOT / "backend" / "uv.lock")
    packages = uv_lock.get("package", [])
    assert isinstance(packages, list)
    editable = next(
        (
            package
            for package in packages
            if isinstance(package, dict)
            and package.get("name") == backend_name
            and package.get("source") == {"editable": "."}
        ),
        None,
    )
    values["backend/uv.lock"] = editable.get("version") if editable else None

    frontend = json.loads(
        (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    package_lock = json.loads(
        (ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8")
    )
    values["frontend/package.json"] = frontend.get("version")
    values["frontend/package-lock.json (root)"] = package_lock.get("version")
    values["frontend/package-lock.json (package)"] = (
        package_lock.get("packages", {}).get("", {}).get("version")
    )

    for source, actual in values.items():
        if actual != expected:
            errors.append(f"{source}: expected {expected!r}, found {actual!r}")

    main_source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    if "version=__version__" not in main_source:
        errors.append("backend/app/main.py: FastAPI metadata must use app.__version__")

    if errors:
        print("Version consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Version consistency check passed ({expected}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
