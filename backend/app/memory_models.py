"""Typed personal-memory and controlled-learning contracts, independent of transports."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Sensitivity = Literal["public", "private", "sensitive"]


def valid_unicode(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Text must contain valid Unicode") from None
    return value


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    kind: Literal["fact", "preference", "event", "decision"] = "fact"
    key: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2000)
    sensitivity: Sensitivity = "private"
    _unicode = field_validator("key", "content")(valid_unicode)


class MemoryRecord(Entry):
    """Owner-reviewed memory with server-controlled provenance and lifecycle fields."""

    id: str
    source: str
    status: Literal["pending", "confirmed", "superseded"]
    created_at: datetime
    updated_at: datetime
    revision: int = Field(ge=1)
    superseded_by: str | None


class MemoryRevision(MemoryRecord):
    change: Literal["baseline", "created", "edited", "confirmed", "superseded", "corroborated"]


class StoredTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class EditEntry(Entry):
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class RestoreMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class MemoryMutation(BaseModel):
    status: Literal["pending", "confirmed"]
    revision: int = Field(ge=1)


class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int | None = Field(default=None, ge=1, strict=True)
    replace_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=100
    )
    replace_revisions: (
        dict[
            Annotated[str, Field(min_length=1, max_length=100)],
            Annotated[int, Field(ge=1, strict=True)],
        ]
        | None
    ) = Field(default=None, max_length=100)

    @field_validator("replace_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(not item.strip() for item in value):
            raise ValueError("Replacement IDs must be nonblank and unique")
        return value


class SourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    kind: Literal["document", "project", "conversation", "event"]
    name: str = Field(min_length=1, max_length=160)
    sensitivity: Sensitivity = "private"
    _unicode = field_validator("name")(valid_unicode)


class RegisteredSource(SourceInput):
    id: str
    approved: bool
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class IngestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=80_000)
    mode: Literal["fields", "notes"] = "fields"
    expected_source_revision: int | None = Field(default=None, ge=1, strict=True)
    _unicode = field_validator("content")(valid_unicode)


class IngestionStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["source", "extraction", "deduplication", "conflicts", "storage"]
    outcome: Literal["completed", "failed"]
    count: int = Field(ge=0)


class IngestionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=0)
    outcome: Literal["created", "duplicate", "known", "forgotten"]
    memory_id: str | None = None
    conflict_ids: list[str] = Field(default_factory=list)


class IngestionRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source_id: str
    source_revision: int = Field(ge=1)
    document_hash: str
    extractor: str
    mode: Literal["fields", "notes"]
    status: Literal["completed", "failed"]
    attempts: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    replayed: bool = False
    error_code: Literal["extraction_invalid", "storage_failed"] | None = None
    items: list[IngestionItem]
    trace: list[IngestionStage]


class CandidateOrigin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    memory_id: str
    memory_revision: int = Field(ge=1)
    source_id: str
    source_revision: int = Field(ge=1)
    document_hash: str
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    excerpt: str
    run_id: str
    created_at: datetime


class ForgottenDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str
    forgotten_at: datetime


class MemoryExport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[3] = 3
    entries: list[MemoryRecord]
    history: list[StoredTurn]
    revisions: list[MemoryRevision]
    sources: list[RegisteredSource]
    ingestion_runs: list[IngestionRun]
    origins: list[CandidateOrigin]
    forgotten: list[ForgottenDigest]
