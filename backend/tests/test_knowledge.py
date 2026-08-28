from pathlib import Path

import pytest

from app.knowledge import KnowledgeBase, KnowledgeLoadError


def test_documents_are_relative_sorted_and_utf8(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.md").write_text("# Beta\n\nSecond", encoding="utf-8")
    (tmp_path / "a.md").write_text("# Alpha\n\n你好", encoding="utf-8")

    documents = KnowledgeBase(str(tmp_path)).documents()

    assert [item.path for item in documents] == ["a.md", "nested/b.md"]
    assert [item.title for item in documents] == ["Alpha", "Beta"]
    assert documents[0].text.endswith("你好")


def test_oversized_document_is_rejected_without_exposing_its_path(tmp_path: Path) -> None:
    (tmp_path / "private-name.md").write_text("0123456789", encoding="utf-8")

    with pytest.raises(KnowledgeLoadError) as captured:
        KnowledgeBase(str(tmp_path), max_document_bytes=5).documents()

    assert captured.value.code == "knowledge_document_too_large"
    assert "private-name" not in str(captured.value)


def test_symbolic_linked_document_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-private.md"
    outside.write_text("private", encoding="utf-8")
    link = tmp_path / "linked.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symbolic links are unavailable on this platform")

    with pytest.raises(KnowledgeLoadError) as captured:
        KnowledgeBase(str(tmp_path)).documents()

    assert captured.value.code == "knowledge_symlink_rejected"


def test_search_preserves_content_below_a_markdown_heading(tmp_path: Path) -> None:
    (tmp_path / "profile.md").write_text(
        "# Profile\n\n## Project planning\nStart with user goals and write Python prototypes.\n",
        encoding="utf-8",
    )

    matches = KnowledgeBase(str(tmp_path)).search("project planning Python")

    assert len(matches) == 1
    assert matches[0].document.path == "profile.md"
    assert matches[0].excerpt == (
        "Project planning\nStart with user goals and write Python prototypes."
    )
    assert matches[0].score == 1.0


def test_search_order_and_limit_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("Alpha Python", encoding="utf-8")
    (tmp_path / "a.md").write_text("Alpha Python", encoding="utf-8")

    matches = KnowledgeBase(str(tmp_path)).search("Alpha Python", limit=1)

    assert [match.document.path for match in matches] == ["a.md"]
