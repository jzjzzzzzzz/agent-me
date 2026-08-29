import importlib.util
from pathlib import Path

CHECK_DOCS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_docs.py"
CHECK_DOCS_SPEC = importlib.util.spec_from_file_location("check_docs", CHECK_DOCS_PATH)
assert CHECK_DOCS_SPEC is not None and CHECK_DOCS_SPEC.loader is not None
check_docs = importlib.util.module_from_spec(CHECK_DOCS_SPEC)
CHECK_DOCS_SPEC.loader.exec_module(check_docs)


def test_heading_anchors_follow_github_slug_rules() -> None:
    text = (
        "# API: v2.0 — What's New?\n"
        "## Привет non-latin 你好\n"
        "## This'll be a _Helpful_ Section\n"
        "## heading with an _ underscore\n"
        "## I ♥ unicode\n"
        "## 😄 emoji\n"
        "## Trimmed heading   \n"
        "## Repeat\n"
        "## Repeat\n"
        "## Repeat\n"
        "## Echo\n"
        "## Echo\n"
        "## Echo 1\n"
        "## Echo-1\n"
        "## Echo\n"
        "Setext heading\n"
        "---------------\n"
        "```markdown\n"
        "# Not a heading\n"
        "```\n"
    )

    assert check_docs.heading_anchors(text) == {
        "api-v20--whats-new",
        "привет-non-latin-你好",
        "thisll-be-a-helpful-section",
        "heading-with-an-_-underscore",
        "i--unicode",
        "-emoji",
        "trimmed-heading",
        "repeat",
        "repeat-1",
        "repeat-2",
        "echo",
        "echo-1",
        "echo-1-1",
        "echo-1-2",
        "echo-2",
        "setext-heading",
    }


def test_valid_same_file_cross_file_and_percent_encoded_fragments_pass(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.md"
    target = tmp_path / "guide.md"
    source.write_text(
        "# Local heading\n\n"
        "[same file](#local-heading)\n"
        "[cross file](guide.md#api-v20--whats-new)\n"
        "[encoded Unicode](guide.md#%E4%BD%A0%E5%A5%BD-%E4%B8%96%E7%95%8C)\n"
        "[duplicate](guide.md#repeat-1)\n"
        "[external](https://example.com/guide.md#missing)\n"
        "[image](diagram.png#missing)\n",
        encoding="utf-8",
    )
    target.write_text(
        "# API: v2.0 — What's New?\n\n## 你好 世界\n\n## Repeat\n\n## Repeat\n",
        encoding="utf-8",
    )
    (tmp_path / "diagram.png").write_bytes(b"image")
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)

    assert check_docs.validate_file(source) == []


def test_missing_fragments_name_source_destination_and_fragment(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source.md"
    target = tmp_path / "guide.md"
    source.write_text(
        "# Present\n\n[missing same](#missing-same)\n[missing cross](guide.md#missing-cross)\n",
        encoding="utf-8",
    )
    target.write_text("# Present\n", encoding="utf-8")
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)

    assert check_docs.validate_file(source) == [
        "source.md: missing Markdown anchor in source.md: #missing-same",
        "source.md: missing Markdown anchor in guide.md: #missing-cross",
    ]


def test_existing_file_owner_traversal_and_merge_marker_checks_remain(
    tmp_path: Path, monkeypatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "source.md"
    source.write_text(
        "<<<<<<< ours\n"
        "[missing](missing.md)\n"
        "[outside](../../outside.md)\n"
        "[owner](https://github.com/not-the-owner/agent-me)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    source_name = str(Path("docs") / "source.md")

    assert check_docs.validate_file(source) == [
        f"{source_name}: unresolved merge marker <<<<<<<",
        f"{source_name}: missing local link: missing.md",
        f"{source_name}: link leaves repository: ../../outside.md",
        f"{source_name}: unexpected GitHub owner in https://github.com/not-the-owner/agent-me",
    ]
