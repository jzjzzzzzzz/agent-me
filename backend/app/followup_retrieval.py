"""Revisit current public sources for follow-ups without another model request."""

from .config import Settings
from .knowledge import KnowledgeBase, Match
from .schemas import ChatRequest


def retrieve_chat_context(
    knowledge: KnowledgeBase, request: ChatRequest, settings: Settings
) -> list[Match]:
    matches = knowledge.search(request.question)
    if (
        matches
        or not request.history
        or not request.previous_sources
        or settings.provider_state != "openai-compatible"
    ):
        return matches

    previous_question = next(
        (turn.content for turn in reversed(request.history) if turn.role == "user"), ""
    )
    return knowledge.revisit_sources(
        [(source.path, source.excerpt) for source in request.previous_sources],
        previous_question + "\n" + request.question,
    )
