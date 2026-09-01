from app.collaboration import (
    CollaborationOrchestrator,
    Plan,
    PlannerAgent,
    WriterAgent,
    WrittenAnswer,
)
from app.knowledge import Document, Match


def match(path: str = "profile.md", excerpt: str = "The agent plans from user goals.") -> Match:
    return Match(
        document=Document(title="Profile", path=path, text=excerpt),
        excerpt=excerpt,
        score=1.0,
    )


class StubRetriever:
    def __init__(self, matches: list[Match]) -> None:
        self.matches = matches
        self.queries: list[str] = []

    def search(self, question: str, *, limit: int = 4) -> list[Match]:
        self.queries.append(question)
        return self.matches[:limit]


class RewritingPlanner(PlannerAgent):
    def run(self, question: str) -> Plan:
        return Plan(
            retrieval_query="rewritten retrieval query",
            tasks=("Retrieve evidence for the rewritten query.",),
            query_term_count=3,
        )


class UnsupportedWriter(WriterAgent):
    def run(self, evidence, critique) -> WrittenAnswer:
        return WrittenAnswer(content="An unsupported answer.", citation_count=0)


def test_role_handoffs_are_ordered_and_grounded() -> None:
    retriever = StubRetriever([match()])
    result = CollaborationOrchestrator(retriever=retriever).run(
        question="How does the agent plan from user goals?"
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
    assert retriever.queries == ["How does the agent plan from user goals?"]


def test_critic_blocks_unsupported_synthesis() -> None:
    result = CollaborationOrchestrator(retriever=StubRetriever([])).run(question="Unknown fact?")

    assert result.grounded is False
    assert result.matches == ()
    assert result.trace[2].agent == "critic"
    assert result.trace[2].outcome == "blocked"
    assert result.trace[3].metrics["citation_count"] == 0
    assert "could not find a grounded answer" in result.answer


def test_run_ids_are_unique_and_server_controlled() -> None:
    orchestrator = CollaborationOrchestrator(retriever=StubRetriever([match()]))
    first = orchestrator.run(question="Plan?")
    second = orchestrator.run(question="Plan?")

    assert first.run_id != second.run_id
    assert len(first.run_id) == len("run_") + 32


def test_planner_output_controls_the_researcher_query() -> None:
    retriever = StubRetriever([match()])
    result = CollaborationOrchestrator(
        retriever=retriever,
        planner=RewritingPlanner(),
    ).run(question="original user question")

    assert retriever.queries == ["rewritten retrieval query"]
    assert result.trace[0].metrics == {"task_count": 1, "query_term_count": 3}


def test_collaboration_metrics_use_normalized_unicode_terms() -> None:
    retriever = StubRetriever([match(excerpt="Le résumé décrit une expérience fiable.")])

    result = CollaborationOrchestrator(retriever=retriever).run(
        question="RE\u0301SUME\u0301 expérience"
    )

    assert result.trace[0].metrics["query_term_count"] == 2
    assert result.trace[2].metrics["query_coverage"] == 1.0


def test_verified_workflow_appends_a_typed_verifier_stage() -> None:
    result = CollaborationOrchestrator(retriever=StubRetriever([match()])).run(
        question="How does the agent plan from user goals?",
        verify=True,
    )

    assert result.workflow == "planner-researcher-critic-writer-verifier"
    assert result.grounded is True
    assert [stage.agent for stage in result.trace] == [
        "planner",
        "researcher",
        "critic",
        "writer",
        "verifier",
    ]
    assert result.trace[-1].outcome == "completed"
    assert result.trace[-1].metrics == {
        "approved": True,
        "citation_paths_valid": True,
        "expected_citation_count": 1,
        "reported_citation_count": 1,
    }


def test_verified_workflow_blocks_an_answer_that_loses_its_citation() -> None:
    result = CollaborationOrchestrator(
        retriever=StubRetriever([match()]),
        writer=UnsupportedWriter(),
    ).run(question="How does the agent plan from user goals?", verify=True)

    assert result.workflow == "planner-researcher-critic-writer-verifier"
    assert result.grounded is False
    assert result.answer == (
        "I could not return a verified answer from the configured knowledge files."
    )
    assert result.trace[-1].agent == "verifier"
    assert result.trace[-1].outcome == "blocked"
    assert result.trace[-1].metrics["approved"] is False


def test_verified_workflow_approves_the_safe_insufficient_evidence_response() -> None:
    result = CollaborationOrchestrator(retriever=StubRetriever([])).run(
        question="Unknown fact?",
        verify=True,
    )

    assert result.grounded is False
    assert result.trace[2].outcome == "blocked"
    assert result.trace[-1].outcome == "completed"
    assert result.trace[-1].metrics["expected_citation_count"] == 0
