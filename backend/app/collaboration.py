from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias
from uuid import uuid4

from .knowledge import Match
from .text import normalized_tokens

AgentName: TypeAlias = Literal["planner", "researcher", "critic", "writer", "verifier"]
StageOutcome: TypeAlias = Literal["completed", "blocked"]
MetricValue: TypeAlias = bool | int | float
WorkflowName: TypeAlias = Literal[
    "planner-researcher-critic-writer",
    "planner-researcher-critic-writer-verifier",
]

_INSUFFICIENT_EVIDENCE = "I could not find a grounded answer in the configured knowledge files."
_VERIFICATION_FAILED = "I could not return a verified answer from the configured knowledge files."


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
class Verification:
    approved: bool
    citation_paths_valid: bool
    expected_citation_count: int
    reported_citation_count: int


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
    workflow: WorkflowName
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
            query_term_count=len(normalized_tokens(retrieval_query)),
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
        query_tokens = normalized_tokens(question)
        evidence_tokens = normalized_tokens("\n".join(match.excerpt for match in evidence.matches))
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


class VerifierAgent:
    """Checks public answer invariants without exposing hidden reasoning."""

    name: AgentName = "verifier"

    def run(
        self,
        evidence: EvidenceBundle,
        critique: Critique,
        written: WrittenAnswer,
    ) -> Verification:
        paths = tuple(dict.fromkeys(match.document.path for match in evidence.matches))
        expected_count = len(paths) if critique.grounded else 0
        citation_paths_valid = (
            all(f"[{path}]" in written.content for path in paths)
            if critique.grounded
            else written.content == _INSUFFICIENT_EVIDENCE
        )
        approved = (
            written.citation_count == expected_count
            and citation_paths_valid
            and bool(written.content.strip())
        )
        return Verification(
            approved=approved,
            citation_paths_valid=citation_paths_valid,
            expected_citation_count=expected_count,
            reported_citation_count=written.citation_count,
        )


class CollaborationOrchestrator:
    """Runs explicit role handoffs and returns auditable operational artifacts.

    Trace summaries describe workflow operations and counts. They are deliberately
    not model chain-of-thought or hidden reasoning.
    """

    baseline_workflow: WorkflowName = "planner-researcher-critic-writer"
    verified_workflow: WorkflowName = "planner-researcher-critic-writer-verifier"

    def __init__(
        self,
        *,
        retriever: Retriever,
        planner: PlannerAgent | None = None,
        researcher: ResearcherAgent | None = None,
        critic: CriticAgent | None = None,
        writer: WriterAgent | None = None,
        verifier: VerifierAgent | None = None,
    ) -> None:
        self.planner = planner or PlannerAgent()
        self.researcher = researcher or ResearcherAgent(retriever)
        self.critic = critic or CriticAgent()
        self.writer = writer or WriterAgent()
        self.verifier = verifier or VerifierAgent()

    def run(self, *, question: str, verify: bool = False) -> CollaborationResult:
        plan = self.planner.run(question)
        evidence = self.researcher.run(plan)
        critique = self.critic.run(question, evidence)
        written = self.writer.run(evidence, critique)

        document_count = len({match.document.path for match in evidence.matches})
        trace: tuple[StageTrace, ...] = (
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
        verification: Verification | None = None
        if verify:
            verification = self.verifier.run(evidence, critique, written)
            trace += (
                StageTrace(
                    sequence=5,
                    agent=self.verifier.name,
                    outcome="completed" if verification.approved else "blocked",
                    summary=(
                        "Verified citation paths and answer metadata."
                        if verification.approved
                        else "Blocked the answer because verification invariants failed."
                    ),
                    metrics={
                        "approved": verification.approved,
                        "citation_paths_valid": verification.citation_paths_valid,
                        "expected_citation_count": verification.expected_citation_count,
                        "reported_citation_count": verification.reported_citation_count,
                    },
                ),
            )

        verification_approved = verification is None or verification.approved
        return CollaborationResult(
            run_id=f"run_{uuid4().hex}",
            workflow=self.verified_workflow if verify else self.baseline_workflow,
            answer=written.content if verification_approved else _VERIFICATION_FAILED,
            grounded=critique.grounded and verification_approved,
            matches=evidence.matches,
            trace=trace,
        )
