"""Opt-in, token-protected single-owner memory. Never used by public chat routes."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .knowledge import Document, KnowledgeBase, Match
from .memory import (
    Confirm,
    EditEntry,
    Entry,
    MemoryExport,
    MemoryMutation,
    MemoryRecord,
    MemoryRevision,
    RestoreMemory,
    Store,
    StoredTurn,
)
from .provider import context_matches, generate_answer
from .schemas import ChatTurn

router = APIRouter(prefix="/api/v1/personal", tags=["private twin"])


class PersonalChat(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=8000)


def authorize(
    config: Settings = Depends(get_settings), authorization: str = Header(default="")
) -> Settings:
    if not config.personal_enabled:
        raise HTTPException(404, "Personal mode is disabled")
    expected = f"Bearer {config.personal_token}"
    if len(config.personal_token) < 32 or not secrets.compare_digest(
        authorization.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(401, "Private workspace token required")
    return config


def store(config: Settings = Depends(authorize)) -> Store:
    return Store(config.personal_data_dir)


@router.get("/entries", response_model=list[MemoryRecord])
def entries(include_superseded: bool = False, db: Store = Depends(store)):
    # Existing clients remain an active-memory view. Archives are an explicit opt-in.
    return db.entries(include_superseded=include_superseded)


@router.post("/entries", response_model=MemoryRecord)
def add(payload: Entry, db: Store = Depends(store)):
    return db.add(payload)


@router.get("/entries/{entry_id}/history", response_model=list[MemoryRevision])
def memory_history(entry_id: str, db: Store = Depends(store)):
    return db.revisions(entry_id)


@router.post("/entries/{entry_id}/restore", response_model=MemoryRecord)
def restore(entry_id: str, payload: RestoreMemory, db: Store = Depends(store)):
    return db.restore(entry_id, payload.revision, payload.expected_revision)


@router.post("/entries/{entry_id}/edit", response_model=MemoryMutation)
def edit(entry_id: str, payload: EditEntry, db: Store = Depends(store)):
    return db.edit(entry_id, payload, payload.expected_revision)


@router.post("/entries/{entry_id}/confirm", response_model=MemoryMutation)
def confirm(entry_id: str, payload: Confirm, db: Store = Depends(store)):
    return db.confirm(
        entry_id, payload.replace_ids, payload.expected_revision, payload.replace_revisions
    )


@router.post("/entries/{entry_id}/delete")
def delete(entry_id: str, db: Store = Depends(store)):
    return db.delete(entry_id)


@router.get("/history", response_model=list[StoredTurn])
def history(db: Store = Depends(store)):
    return db.history()


@router.post("/history/clear")
def clear_history(db: Store = Depends(store)):
    return db.clear_history()


@router.get("/export", response_model=MemoryExport)
def export(db: Store = Depends(store)):
    return db.export()


@router.post("/chat")
async def chat(
    payload: PersonalChat, config: Settings = Depends(authorize), db: Store = Depends(store)
):
    if len(payload.question) > config.max_question_chars:
        raise HTTPException(413, "Question exceeds configured limit")
    knowledge = KnowledgeBase(
        config.knowledge_dir,
        max_document_bytes=config.max_document_bytes,
        max_documents=config.max_knowledge_documents,
        max_corpus_bytes=config.max_knowledge_bytes,
    )
    public = await run_in_threadpool(knowledge.search, payload.question)
    local_knowledge = KnowledgeBase(
        str(db.root / "knowledge"),
        max_document_bytes=config.max_document_bytes,
        max_documents=config.max_knowledge_documents,
        max_corpus_bytes=config.max_knowledge_bytes,
    )
    local = await run_in_threadpool(local_knowledge.search, payload.question)
    # Namespace local paths so they cannot be mistaken for public repository files.
    local = [
        Match(
            Document(m.document.title, "private/knowledge/" + m.document.path, m.document.text),
            m.excerpt,
            m.score,
        )
        for m in local
    ]
    private = await run_in_threadpool(db.context, payload.question)
    matches = sorted(private + local + public, key=lambda m: m.score, reverse=True)
    # Deliberately don't re-inject stored conversations: deleted memories must not return
    # through stale chat history. History is persisted for display, not factual grounding.
    history: list[ChatTurn] = []
    answer, mode = await generate_answer(
        question=payload.question, history=history, matches=matches, settings=config
    )
    await run_in_threadpool(db.save_chat, payload.question, answer)
    response_matches = (
        context_matches(matches, config.max_context_chars)
        if mode == "openai-compatible"
        else matches
    )
    return {
        "answer": answer,
        "mode": mode,
        "sources": [{"path": m.document.path, "excerpt": m.excerpt} for m in response_matches],
    }
