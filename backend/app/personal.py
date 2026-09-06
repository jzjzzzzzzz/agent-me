"""Opt-in, token-protected single-owner memory. Never used by public chat routes."""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from .config import Settings, get_settings
from .knowledge import Document, KnowledgeBase, Match
from .provider import generate_answer
from .schemas import ChatTurn
from .text import normalized_tokens

router = APIRouter(prefix="/api/v1/personal", tags=["private twin"])


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["fact", "preference", "event", "decision"] = "fact"
    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)


class Confirm(BaseModel):
    replace_ids: list[str] = Field(default_factory=list, max_length=100)


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


class Store:
    def __init__(self, directory: str):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "twin.sqlite3"
        if self.path.is_symlink():
            raise ValueError("Database must not be a symbolic link")
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS entries (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, key TEXT NOT NULL,
                    content TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA secure_delete=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def entries(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM entries ORDER BY rowid")]

    def add(self, entry: Entry, source: str = "manual"):
        now = datetime.now(UTC).isoformat()
        item = dict(
            id=uuid4().hex,
            **entry.model_dump(),
            source=source,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        with self.connect() as db:
            db.execute(
                "INSERT INTO entries VALUES (:id,:kind,:key,:content,:source,:status,"
                ":created_at,:updated_at)",
                item,
            )
        return item

    def edit(self, entry_id: str, entry: Entry):
        with self.connect() as db:
            cur = db.execute(
                "UPDATE entries SET kind=?,key=?,content=?,status='pending',updated_at=? "
                "WHERE id=?",
                (entry.kind, entry.key, entry.content, datetime.now(UTC).isoformat(), entry_id),
            )
            if not cur.rowcount:
                raise HTTPException(404, "Memory not found")
        return {"status": "pending"}

    def confirm(self, entry_id: str, replace_ids: list[str]):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
            if not item:
                raise HTTPException(404, "Memory not found")
            conflicts = [
                r[0]
                for r in db.execute(
                    "SELECT id FROM entries WHERE kind=? AND key=? "
                    "AND status='confirmed' AND id!=?",
                    (item["kind"], item["key"], entry_id),
                )
            ]
            if set(conflicts) != set(replace_ids):
                raise HTTPException(
                    409,
                    {
                        "message": "Confirm replacement of conflicting memories",
                        "conflict_ids": conflicts,
                    },
                )
            for old_id in conflicts:
                db.execute("DELETE FROM entries WHERE id=?", (old_id,))
            db.execute(
                "UPDATE entries SET status='confirmed',updated_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), entry_id),
            )
        return {"status": "confirmed"}

    def delete(self, entry_id: str):
        with self.connect() as db:
            db.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        return {"deleted": True}

    def history(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM turns ORDER BY rowid DESC LIMIT 100").fetchall()
            return [dict(r) for r in reversed(rows)]

    def clear_history(self):
        with self.connect() as db:
            db.execute("DELETE FROM turns")
        return {"deleted": True}

    def save_chat(self, question: str, answer: str):
        turn_id = uuid4().hex
        with self.connect() as db:
            now = datetime.now(UTC).isoformat()
            db.executemany(
                "INSERT INTO turns VALUES (?,?,?,?)",
                [(turn_id, "user", question, now), (uuid4().hex, "assistant", answer, now)],
            )
        # Explicit syntax only: do not silently infer personal facts from casual conversation.
        for prefix in ("记住：", "记住:", "Remember:", "remember:"):
            if question.startswith(prefix):
                value = question[len(prefix) :].strip()
                if value:
                    self.add(
                        Entry(
                            kind="preference", key="conversation.preference", content=value[:2000]
                        ),
                        source=f"turn:{turn_id}",
                    )
                break

    def context(self, question: str):
        tokens = normalized_tokens(question)
        matches = []
        for item in self.entries():
            if item["status"] != "confirmed":
                continue
            excerpt = f"{item['key']}: {item['content']}"
            overlap = len(tokens & normalized_tokens(excerpt)) / max(len(tokens), 1)
            # Preferences are always supplied, but do not outrank relevant factual evidence.
            if overlap or item["kind"] == "preference":
                doc = Document(title=item["key"], path=f"memory/{item['id']}", text=excerpt)
                matches.append(Match(document=doc, excerpt=excerpt, score=overlap))
        return sorted(matches, key=lambda m: m.score, reverse=True)[:20]


def store(config: Settings = Depends(authorize)) -> Store:
    return Store(config.personal_data_dir)


@router.get("/entries")
def entries(db: Store = Depends(store)):
    return db.entries()


@router.post("/entries")
def add(payload: Entry, db: Store = Depends(store)):
    return db.add(payload)


@router.post("/entries/{entry_id}/edit")
def edit(entry_id: str, payload: Entry, db: Store = Depends(store)):
    return db.edit(entry_id, payload)


@router.post("/entries/{entry_id}/confirm")
def confirm(entry_id: str, payload: Confirm, db: Store = Depends(store)):
    return db.confirm(entry_id, payload.replace_ids)


@router.post("/entries/{entry_id}/delete")
def delete(entry_id: str, db: Store = Depends(store)):
    return db.delete(entry_id)


@router.get("/history")
def history(db: Store = Depends(store)):
    return db.history()


@router.post("/history/clear")
def clear_history(db: Store = Depends(store)):
    return db.clear_history()


@router.get("/export")
def export(db: Store = Depends(store)):
    with db.connect() as connection:
        turns = [dict(r) for r in connection.execute("SELECT * FROM turns ORDER BY rowid")]
    return {"version": 1, "entries": db.entries(), "history": turns}


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
    return {
        "answer": answer,
        "mode": mode,
        "sources": [{"path": m.document.path, "excerpt": m.excerpt} for m in matches],
    }
