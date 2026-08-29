#!/usr/bin/env python3
"""Check repository Markdown links and maintained course structure offline."""

from __future__ import annotations

import html
import re
import sys
import unicodedata
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
REMOVED_SLUG_CATEGORIES = {
    "Cc",
    "Cf",
    "Cn",
    "Co",
    "No",
    "Pd",
    "Pe",
    "Pf",
    "Pi",
    "Po",
    "Ps",
}
ATX_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+(.*)|[ \t]*)$")
SETEXT_HEADING = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
INLINE_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
REFERENCE_LINK = re.compile(r"!?\[([^\]]*)\]\[[^\]]*\]")
CODE_SPAN = re.compile(r"(`+)(.*?)\1")
INLINE_MARKUP = re.compile(r"(?<![\w\\])([*_~]{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)")
HTML_TAG = re.compile(r"</?[^>]+>")
ESCAPED_MARKUP = re.compile(r"\\([\\`*{}\[\]()#+\-.!_>~|])")


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part.startswith(".") for part in path.relative_to(ROOT).parts)
        and "node_modules" not in path.parts
    )


def destination_path(destination: str) -> str:
    return destination_parts(destination)[0]


def destination_parts(destination: str) -> tuple[str, str]:
    value = destination.strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    value = value.split(maxsplit=1)[0]
    path, separator, fragment = value.partition("#")
    return path, fragment if separator else ""


def heading_text(value: str) -> str:
    value = INLINE_LINK.sub(r"\1", value)
    value = REFERENCE_LINK.sub(r"\1", value)
    value = CODE_SPAN.sub(r"\2", value)
    value = HTML_TAG.sub("", value)
    previous = None
    while value != previous:
        previous = value
        value = INLINE_MARKUP.sub(r"\2", value)
    return html.unescape(ESCAPED_MARKUP.sub(r"\1", value))


def github_slug(value: str) -> str:
    result: list[str] = []
    for character in heading_text(value).lower():
        category = unicodedata.category(character)
        if character == " ":
            result.append("-")
        elif character == "-" or character.isalpha():
            result.append(character)
        elif category in REMOVED_SLUG_CATEGORIES or category.startswith(("S", "Z")):
            continue
        else:
            result.append(character)
    return "".join(result)


def markdown_headings(text: str) -> list[str]:
    lines = text.splitlines()
    headings: list[str] = []
    outside_fence = [True] * len(lines)
    fence_character = ""
    fence_length = 0

    for index, line in enumerate(lines):
        fence = FENCE.match(line)
        if fence_character:
            outside_fence[index] = False
            stripped = line.lstrip()
            if (
                stripped.startswith(fence_character * fence_length)
                and not stripped.strip(fence_character).strip()
            ):
                fence_character = ""
                fence_length = 0
            continue
        if fence:
            marker = fence.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            outside_fence[index] = False
            continue

        if (
            index
            and SETEXT_HEADING.match(line)
            and outside_fence[index - 1]
            and lines[index - 1].strip()
            and not ATX_HEADING.match(lines[index - 1])
        ):
            headings.append(lines[index - 1].strip())
            continue

        match = ATX_HEADING.match(line)
        if match:
            heading = match.group(1) or ""
            heading = re.sub(r"[ \t]+#+[ \t]*$", "", heading)
            headings.append(heading.rstrip())

    return headings


def heading_anchors(text: str) -> set[str]:
    occurrences: dict[str, int] = {}
    anchors: set[str] = set()
    for heading in markdown_headings(text):
        original = github_slug(heading)
        anchor = original
        while anchor in occurrences:
            occurrences[original] = occurrences.get(original, 0) + 1
            anchor = f"{original}-{occurrences[original]}"
        occurrences[anchor] = 0
        anchors.add(anchor)
    return anchors


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for marker in MERGE_MARKERS:
        if any(line.startswith(marker) for line in text.splitlines()):
            errors.append(f"{path.relative_to(ROOT)}: unresolved merge marker {marker}")
    for raw_destination in LINK.findall(text):
        destination, fragment = destination_parts(raw_destination)
        if not destination and not fragment:
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

        target = (
            path.resolve()
            if not destination
            else (path.parent / unquote(destination)).resolve()
        )
        try:
            target_relative = target.relative_to(ROOT)
        except ValueError:
            errors.append(
                f"{path.relative_to(ROOT)}: link leaves repository: {destination}"
            )
            continue
        if not target.exists():
            errors.append(
                f"{path.relative_to(ROOT)}: missing local link: {destination}"
            )
            continue
        if fragment and target.suffix.lower() == ".md" and target.is_file():
            decoded_fragment = unquote(fragment)
            target_text = (
                text if target == path.resolve() else target.read_text(encoding="utf-8")
            )
            if decoded_fragment not in heading_anchors(target_text):
                errors.append(
                    f"{path.relative_to(ROOT)}: missing Markdown anchor in "
                    f"{target_relative}: #{decoded_fragment}"
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
