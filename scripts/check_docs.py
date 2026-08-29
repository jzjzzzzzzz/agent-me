#!/usr/bin/env python3
"""Check repository Markdown links and maintained course structure offline."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
OWNED_REPOSITORIES = {"agent-me", "human-api"}
EXPECTED_OWNER = "jzjzzzzzzz"
LESSONS = (
    "00-course-setup",
    "01-grounded-qa",
    "02-retrieval",
    "03-role-design",
    "04-typed-orchestration",
    "05-critic-observability",
    "06-evaluation",
    "07-production-capstone",
)
ENGLISH_SECTIONS = (
    "## Why this lesson matters",
    "## Learning objectives",
    "## Read the implementation",
    "## Hands-on lab",
    "## Exercises",
    "## Check your understanding",
    "## Completion checklist",
    "## Further reading",
)
CHINESE_SECTIONS = (
    "## 为什么重要",
    "## 学习目标",
    "## 阅读实现",
    "## 动手实验",
    "## 练习",
    "## 理解检查",
    "## 完成清单",
    "## 延伸阅读",
)
MERGE_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


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
    for marker in MERGE_MARKERS:
        if any(line.startswith(marker) for line in text.splitlines()):
            errors.append(f"{path.relative_to(ROOT)}: unresolved merge marker {marker}")
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


def validate_course() -> list[str]:
    errors: list[str] = []
    language_roots = (
        (ROOT / "course", ENGLISH_SECTIONS),
        (ROOT / "course" / "translations" / "zh-CN", CHINESE_SECTIONS),
    )
    for course_root, required_sections in language_roots:
        for lesson in LESSONS:
            path = course_root / lesson / "README.md"
            relative = path.relative_to(ROOT)
            if not path.is_file():
                errors.append(f"{relative}: maintained lesson is missing")
                continue
            text = path.read_text(encoding="utf-8")
            headings = tuple(
                line.strip() for line in text.splitlines() if line.startswith("## ")
            )
            for section in required_sections:
                if not any(heading.startswith(section) for heading in headings):
                    errors.append(f"{relative}: missing required section {section}")
            if "**Time:**" not in text and "**时间：**" not in text:
                errors.append(f"{relative}: missing time metadata")
    return errors


def main() -> int:
    files = markdown_files()
    errors = [error for path in files for error in validate_file(path)]
    errors.extend(validate_course())
    if errors:
        print("Documentation check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        f"Documentation check passed ({len(files)} Markdown files, "
        f"{len(LESSONS) * 2} maintained lesson pages)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
