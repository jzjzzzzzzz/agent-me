from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias
from uuid import uuid4

from .knowledge import Match

AgentName: TypeAlias = Literal["planner", "researcher", "critic", "writer"]
StageOutcome: TypeAlias = Literal["completed", "blocked"]
MetricValue: TypeAlias = bool | int | float

_TOKEN = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]", re.IGNORECASE)
_INSUFFICIENT_EVIDENCE = "I could not find a grounded answer in the configured knowledge files."


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(value)}


@dataclass(frozen=True)
class Plan:
    retrieval_query: str
    tasks: tuple[str, ...]
    query_term_count: int


@dataclass(frozen=True)
class EvidenceBundle:
    matches: tuple[Match, ...]


@dataclass(frozen=True)
class Critique:
    grounded: bool
    query_coverage: float


@dataclass(frozen=True)
class WrittenAnswer:
    content: str
    citation_count: int


@dataclass(frozen=True)
class StageTrace:
    sequence: int
    agent: AgentName
    outcome: StageOutcome
    summary: str
    metrics: dict[str, MetricValue]


@dataclass(frozen=True)
class CollaborationResult:
    run_id: str
    workflow: str
    answer: str
    grounded: bool
    matches: tuple[Match, ...]
    trace: tuple[StageTrace, ...]


class Retriever(Protocol):
    def search(self, question: str, *, limit: int = 4) -> list[Match]: ...


class PlannerAgent:
    name: AgentName = "planner"

    def run(self, question: str) -> Plan:
        retrieval_query = question.strip()
        return Plan(
            retrieval_query=retrieval_query,
            tasks=(
                "Retrieve evidence from the configured knowledge base.",
                "Check whether the evidence supports the requested answer.",
                "Write a concise answer with source-path citations.",
            ),
            query_term_count=len(_tokens(retrieval_query)),
        )


class ResearcherAgent:
    name: AgentName = "researcher"

    def __init__(self, retriever: Retriever) -> None:
        self.retriever = retriever

    def run(self, plan: Plan) -> EvidenceBundle:
        return EvidenceBundle(matches=tuple(self.retriever.search(plan.retrieval_query)))


class CriticAgent:
    name: AgentName = "critic"

    def run(self, question: str, evidence: EvidenceBundle) -> Critique:
        query_tokens = _tokens(question)
        evidence_tokens = _tokens("\n".join(match.excerpt for match in evidence.matches))
        covered = query_tokens & evidence_tokens
        coverage = len(covered) / max(len(query_tokens), 1)
        return Critique(
            grounded=bool(evidence.matches),
            query_coverage=round(coverage, 4),
        )


class WriterAgent:
    name: AgentName = "writer"

    def run(self, evidence: EvidenceBundle, critique: Critique) -> WrittenAnswer:
        if not critique.grounded:
            return WrittenAnswer(content=_INSUFFICIENT_EVIDENCE, citation_count=0)

        primary = evidence.matches[0].excerpt
        paths = tuple(dict.fromkeys(match.document.path for match in evidence.matches))
        citations = ", ".join(f"[{path}]" for path in paths)
        return WrittenAnswer(
            content=f"{primary}\n\nSources: {citations}",
            citation_count=len(paths),
        )


class CollaborationOrchestrator:
    """Runs explicit role handoffs and returns auditable operational artifacts.

    Trace summaries describe workflow operations and counts. They are deliberately
    not model chain-of-thought or hidden reasoning.
    """

    workflow = "planner-researcher-critic-writer"

    def __init__(
        self,
        *,
        retriever: Retriever,
        planner: PlannerAgent | None = None,
        researcher: ResearcherAgent | None = None,
        critic: CriticAgent | None = None,
        writer: WriterAgent | None = None,
    ) -> None:
        self.planner = planner or PlannerAgent()
        self.researcher = researcher or ResearcherAgent(retriever)
        self.critic = critic or CriticAgent()
        self.writer = writer or WriterAgent()

    def run(self, *, question: str) -> CollaborationResult:
        plan = self.planner.run(question)
        evidence = self.researcher.run(plan)
        critique = self.critic.run(question, evidence)
        written = self.writer.run(evidence, critique)

        document_count = len({match.document.path for match in evidence.matches})
        trace = (
            StageTrace(
                sequence=1,
                agent=self.planner.name,
                outcome="completed",
                summary="Created an evidence-first execution plan.",
                metrics={
                    "task_count": len(plan.tasks),
                    "query_term_count": plan.query_term_count,
                },
            ),
            StageTrace(
                sequence=2,
                agent=self.researcher.name,
                outcome="completed",
                summary="Collected ranked excerpts from the local knowledge base.",
                metrics={
                    "evidence_count": len(evidence.matches),
                    "document_count": document_count,
                },
            ),
            StageTrace(
                sequence=3,
                agent=self.critic.name,
                outcome="completed" if critique.grounded else "blocked",
                summary=(
                    "Approved the evidence for grounded synthesis."
                    if critique.grounded
                    else "Blocked unsupported synthesis because no matching evidence was found."
                ),
                metrics={
                    "approved": critique.grounded,
                    "query_coverage": critique.query_coverage,
                },
            ),
            StageTrace(
                sequence=4,
                agent=self.writer.name,
                outcome="completed",
                summary=(
                    "Produced a cited answer from approved evidence."
                    if critique.grounded
                    else "Returned the insufficient-evidence response."
                ),
                metrics={
                    "answer_chars": len(written.content),
                    "citation_count": written.citation_count,
                },
            ),
        )
        return CollaborationResult(
            run_id=f"run_{uuid4().hex}",
            workflow=self.workflow,
            answer=written.content,
            grounded=critique.grounded,
            matches=evidence.matches,
            trace=trace,
        )
