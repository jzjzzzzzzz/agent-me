#!/usr/bin/env python3
"""Check repository Markdown links without making network requests."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
OWNED_REPOSITORIES = {"agent-me", "human-api"}
EXPECTED_OWNER = "jzjzzzzzzz"


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
        and "node_modules" not in path.parts
    )


def destination_path(destination: str) -> str:
    value = destination.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return value.split(maxsplit=1)[0].split("#", 1)[0]


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for raw_destination in LINK.findall(text):
        destination = destination_path(raw_destination)
        if not destination or raw_destination.lstrip().startswith("#"):
            continue

        parsed = urlparse(destination)
        if parsed.scheme in {"http", "https"}:
            if parsed.netloc == "github.com":
                parts = [part for part in parsed.path.split("/") if part]
                if (
                    len(parts) >= 2
                    and parts[1] in OWNED_REPOSITORIES
                    and parts[0] != EXPECTED_OWNER
                ):
                    errors.append(
                        f"{path.relative_to(ROOT)}: unexpected GitHub owner in {destination}"
                    )
            continue
        if parsed.scheme in {"mailto", "tel"}:
            continue

        target = (path.parent / unquote(destination)).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            errors.append(
                f"{path.relative_to(ROOT)}: link leaves repository: {destination}"
            )
            continue
        if not target.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: missing local link: {destination}"
            )
    return errors


def main() -> int:
    files = markdown_files()
    errors = [error for path in files for error in validate_file(path)]
    if errors:
        print("Documentation link check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Documentation link check passed ({len(files)} Markdown files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
