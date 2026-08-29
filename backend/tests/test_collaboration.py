from app.collaboration import CollaborationOrchestrator
from app.knowledge import Document, Match


def match(path: str = "profile.md", excerpt: str = "The agent plans from user goals.") -> Match:
    return Match(
        document=Document(title="Profile", path=path, text=excerpt),
        excerpt=excerpt,
        score=1.0,
    )


def test_role_handoffs_are_ordered_and_grounded() -> None:
    result = CollaborationOrchestrator().run(
        question="How does the agent plan from user goals?",
        matches=[match()],
    )

    assert result.run_id.startswith("run_")
    assert result.workflow == "planner-researcher-critic-writer"
    assert result.grounded is True
    assert [stage.agent for stage in result.trace] == [
        "planner",
        "researcher",
        "critic",
        "writer",
    ]
    assert [stage.sequence for stage in result.trace] == [1, 2, 3, 4]
    assert "[profile.md]" in result.answer
    assert result.trace[1].metrics == {"evidence_count": 1, "document_count": 1}
    assert result.trace[2].metrics["approved"] is True


def test_critic_blocks_unsupported_synthesis() -> None:
    result = CollaborationOrchestrator().run(question="Unknown fact?", matches=[])

    assert result.grounded is False
    assert result.matches == ()
    assert result.trace[2].agent == "critic"
    assert result.trace[2].outcome == "blocked"
    assert result.trace[3].metrics["citation_count"] == 0
    assert "could not find a grounded answer" in result.answer


def test_run_ids_are_unique_and_server_controlled() -> None:
    orchestrator = CollaborationOrchestrator()
    first = orchestrator.run(question="Plan?", matches=[match()])
    second = orchestrator.run(question="Plan?", matches=[match()])

    assert first.run_id != second.run_id
    assert len(first.run_id) == len("run_") + 32
