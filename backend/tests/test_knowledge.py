from concurrent.futures import ThreadPoolExecutor
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


def test_search_ignores_stop_words_instead_of_treating_them_as_evidence(
    tmp_path: Path,
) -> None:
    (tmp_path / "profile.md").write_text(
        "The example agent builds reliable developer tools.", encoding="utf-8"
    )

    assert KnowledgeBase(str(tmp_path)).search("the and") == []
    assert KnowledgeBase(str(tmp_path)).search("What is the capital of France?") == []
    assert KnowledgeBase(str(tmp_path)).search("Is the example agent a doctor?") == []


def test_search_blocks_a_hard_negative_with_shared_vocabulary(tmp_path: Path) -> None:
    (tmp_path / "profile.md").write_text(
        "The example agent verifies project work with automated tests.", encoding="utf-8"
    )

    matches = KnowledgeBase(str(tmp_path)).search(
        "Does the example agent use automated tests to diagnose medical conditions?"
    )

    assert matches == []


def test_search_minimum_score_is_inclusive_and_validated(tmp_path: Path) -> None:
    (tmp_path / "profile.md").write_text("Alpha Python", encoding="utf-8")
    knowledge = KnowledgeBase(str(tmp_path))

    assert len(knowledge.search("Alpha Python Rust", min_score=2 / 3)) == 1
    assert knowledge.search("Alpha Python Rust", min_score=0.67) == []
    with pytest.raises(ValueError, match="min_score"):
        knowledge.search("Alpha", min_score=1.1)


def test_documents_cache_is_reused_and_invalidated_by_corpus_changes(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile.md"
    profile.write_text("# Profile\n\nFirst version.", encoding="utf-8")
    knowledge = KnowledgeBase(str(tmp_path))

    first = knowledge.documents()
    second = knowledge.documents()

    assert first is not second
    assert first[0] is second[0]

    profile.write_text("# Profile\n\nA longer second version.", encoding="utf-8")
    changed = knowledge.documents()
    assert changed[0].text.endswith("A longer second version.")
    assert changed[0] is not first[0]

    extra = tmp_path / "extra.md"
    extra.write_text("# Extra\n\nAnother document.", encoding="utf-8")
    assert [document.path for document in knowledge.documents()] == ["extra.md", "profile.md"]

    profile.unlink()
    assert [document.path for document in knowledge.documents()] == ["extra.md"]


def test_concurrent_document_reads_publish_one_consistent_cache(tmp_path: Path) -> None:
    (tmp_path / "profile.md").write_text("# Profile\n\nStable content.", encoding="utf-8")
    knowledge = KnowledgeBase(str(tmp_path))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: knowledge.documents(), range(32)))

    assert all([document.path for document in result] == ["profile.md"] for result in results)
    assert len({id(result[0]) for result in results}) == 1
