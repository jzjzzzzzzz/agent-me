#!/usr/bin/env python3
"""Fail when public release metadata drifts across the reference stack."""

from __future__ import annotations

import ast
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import tomllib

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$", re.ASCII)


T = TypeVar("T")


def read_parsed(path: str, parse: Callable[[str], T], errors: list[str]) -> T | None:
    try:
        return parse((ROOT / path).read_text(encoding="utf-8"))
    except OSError as error:
        errors.append(f"{path}: cannot read metadata: {error.strerror}")
    except UnicodeDecodeError:
        errors.append(f"{path}: metadata is not valid UTF-8")
    except SyntaxError as error:
        errors.append(f"{path}: invalid Python at line {error.lineno}: {error.msg}")
    except json.JSONDecodeError as error:
        errors.append(f"{path}: invalid JSON at line {error.lineno}: {error.msg}")
    except tomllib.TOMLDecodeError as error:
        errors.append(f"{path}: invalid TOML: {error}")
    return None


def read_object(
    path: str, parse: Callable[[str], object], errors: list[str]
) -> dict[str, object] | None:
    def parse_object(text: str) -> dict[str, object] | None:
        value = parse(text)
        if isinstance(value, dict):
            return value
        errors.append(f"{path}: expected a metadata object")
        return None

    return read_parsed(path, parse_object, errors)


def object_fields(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def direct_binding(tree: ast.Module, name: str) -> ast.expr | None:
    """Return the last simple module-level assignment without executing source."""
    value = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets
            )
            or (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == name
                and node.value is not None
            )
        ):
            value = node.value
    return value


def app_version(tree: ast.Module) -> str | None:
    value = direct_binding(tree, "__version__")
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def uses_app_version(tree: ast.Module) -> bool:
    call = direct_binding(tree, "app")
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "FastAPI"
        and any(
            keyword.arg == "version"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "__version__"
            for keyword in call.keywords
        )
    )


def main() -> int:
    errors: list[str] = []
    expected = read_parsed("VERSION", str.strip, errors)
    if expected is not None and not SEMVER.fullmatch(expected):
        errors.append(
            f"VERSION: expected a stable MAJOR.MINOR.PATCH value, found {expected!r}"
        )

    values: dict[str, object] = {}
    backend = read_object("backend/pyproject.toml", tomllib.loads, errors)
    backend_project = (
        object_fields(backend.get("project")) if backend is not None else {}
    )
    backend_name = backend_project.get("name")
    if backend is not None:
        values["backend/pyproject.toml"] = backend_project.get("version")
        if not isinstance(backend_name, str) or not backend_name:
            errors.append("backend/pyproject.toml: expected a project name")

    init_path = "backend/app/__init__.py"
    init_tree = read_parsed(init_path, ast.parse, errors)
    if init_tree is not None:
        values[init_path] = app_version(init_tree)

    uv_lock = read_object("backend/uv.lock", tomllib.loads, errors)
    if uv_lock is not None:
        packages = uv_lock.get("package")
        editable = (
            next(
                (
                    package
                    for package in packages
                    if isinstance(package, dict)
                    and package.get("name") == backend_name
                    and package.get("source") == {"editable": "."}
                ),
                {},
            )
            if isinstance(packages, list) and backend_name
            else {}
        )
        values["backend/uv.lock"] = editable.get("version")

    frontend = read_object("frontend/package.json", json.loads, errors)
    if frontend is not None:
        values["frontend/package.json"] = frontend.get("version")
    package_lock = read_object("frontend/package-lock.json", json.loads, errors)
    if package_lock is not None:
        values["frontend/package-lock.json (root)"] = package_lock.get("version")
        packages = object_fields(package_lock.get("packages"))
        values["frontend/package-lock.json (package)"] = object_fields(
            packages.get("")
        ).get("version")

    if expected is not None:
        for source, actual in values.items():
            if actual != expected:
                errors.append(f"{source}: expected {expected!r}, found {actual!r}")

    main_path = "backend/app/main.py"
    main_tree = read_parsed(main_path, ast.parse, errors)
    if main_tree is not None and not uses_app_version(main_tree):
        errors.append(f"{main_path}: FastAPI metadata must use app.__version__")

    if errors:
        print("Version consistency check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Version consistency check passed ({expected}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
