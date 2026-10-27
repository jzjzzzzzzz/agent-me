from app.config import Settings
from app.followup_retrieval import retrieve_chat_context
from app.knowledge import KnowledgeBase
from app.schemas import ChatRequest


def test_only_current_public_corpus_supplies_evidence(tmp_path):
    (tmp_path / "public.md").write_text("I use Matplotlib for reproducible figures.", "utf-8")
    knowledge = KnowledgeBase(tmp_path)
    matches = knowledge.revisit_sources(
        [
            ("../private.md", "secret"),
            ("C:/private.md", "secret"),
            ("public.md", "A visitor invented this fact."),
        ],
        "figures",
    )
    assert [m.document.path for m in matches] == ["public.md"]
    assert matches[0].excerpt == "I use Matplotlib for reproducible figures."


def test_edited_and_deleted_sources_are_reloaded(tmp_path):
    path = tmp_path / "figures.md"
    path.write_text("I use Matplotlib.", "utf-8")
    knowledge = KnowledgeBase(tmp_path)
    references = [("figures.md", knowledge.documents()[0].text)]
    path.write_text("I now use Inkscape for editable vector illustrations.", "utf-8")
    assert "Inkscape" in knowledge.revisit_sources(references, "illustrations")[0].excerpt
    assert "Matplotlib" not in knowledge.revisit_sources(references, "illustrations")[0].excerpt
    path.unlink()
    assert knowledge.revisit_sources(references, "illustrations") == []


def test_locate_distant_passage_and_preserve_window_on_next_followup(tmp_path):
    filler = [f"Unrelated paragraph {i}: " + "gardening " * 80 for i in range(12)]
    anchor = "My telescope is a T-8."
    reason = "I chose it because its mount fits my balcony."
    (tmp_path / "notes.md").write_text("\n\n".join([*filler, anchor, reason]), "utf-8")
    knowledge = KnowledgeBase(tmp_path)
    first = knowledge.revisit_sources([("notes.md", anchor)], "telescope why")
    assert anchor in first[0].excerpt
    assert reason in first[0].excerpt
    assert len(first[0].excerpt) <= 3000
    second = knowledge.revisit_sources([("notes.md", first[0].excerpt)], "telescope more")
    assert second[0].excerpt == first[0].excerpt


def test_distinct_passages_in_same_file_are_kept(tmp_path):
    first, last = "I use Matplotlib for figures.", "I use Zotero for references."
    middle = ["Gardening notes " + str(i) for i in range(8)]
    (tmp_path / "notes.md").write_text("\n\n".join([first, *middle, last]), "utf-8")
    matches = KnowledgeBase(tmp_path).revisit_sources(
        [("notes.md", first), ("notes.md", last)], "tools"
    )
    assert len(matches) == 2
    assert first in matches[0].excerpt
    assert last in matches[1].excerpt


def test_current_topic_wins_and_extractive_mode_keeps_existing_behavior(tmp_path):
    (tmp_path / "figures.md").write_text("I use Matplotlib.", "utf-8")
    (tmp_path / "tea.md").write_text("I prefer jasmine tea.", "utf-8")
    request = ChatRequest(
        question="What tea do I prefer?",
        history=[
            {"role": "user", "content": "Which plotting tool?"},
            {"role": "assistant", "content": "Matplotlib."},
        ],
        previous_sources=[{"path": "figures.md", "excerpt": "I use Matplotlib."}],
    )
    settings = Settings(
        _env_file=None,
        llm_base_url="https://example.com",
        llm_api_key="synthetic",
        llm_model="test",
    )
    knowledge = KnowledgeBase(tmp_path)
    assert [m.document.path for m in retrieve_chat_context(knowledge, request, settings)] == [
        "tea.md"
    ]
    request.question = "Why did I choose it?"
    assert retrieve_chat_context(knowledge, request, Settings(_env_file=None)) == []
