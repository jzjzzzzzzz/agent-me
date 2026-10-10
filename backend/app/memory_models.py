"""Typed personal-memory and controlled-learning contracts, independent of transports."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from .agency_models import ActionEvent, ActionPlan, NoteRecord, TaskRecord, ToolPermission
from .owner_models import AuditEvent, ImportArchive, ReplayKey

Sensitivity = Literal["public", "private", "sensitive"]
Belief = Literal["known", "inferred", "disputed", "outdated", "unknown"]
EntityKind = Literal["person", "project", "organization", "event", "idea", "preference", "decision"]


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
    entity_id: str | None = Field(default=None, min_length=1, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1, strict=True, allow_inf_nan=False)
    belief: Belief = "known"
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    occurred_at: AwareDatetime | None = None
    _unicode = field_validator("key", "content")(valid_unicode)

    @model_validator(mode="after")
    def valid_time(self):
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("Validity end must be after its start")
        if self.occurred_at is not None and self.kind not in {"event", "decision"}:
            raise ValueError("Occurrence time belongs to episodic event or decision memory")
        return self


class MemoryRecord(Entry):
    """Owner-reviewed memory with server-controlled provenance and lifecycle fields."""

    id: str
    source: str
    status: Literal["pending", "confirmed", "superseded"]
    created_at: datetime
    updated_at: datetime
    revision: int = Field(ge=1)
    superseded_by: str | None
    owner_id: str
    category: Literal["episodic", "semantic", "preference"]


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
    entity_id: str | None = Field(default=None, min_length=1, max_length=100)
    entity_alias: str | None = Field(default=None, min_length=1, max_length=160)
    _unicode = field_validator("name")(valid_unicode)

    @model_validator(mode="after")
    def one_subject(self):
        if self.entity_id is not None and self.entity_alias is not None:
            raise ValueError("Specify an entity ID or alias, not both")
        return self


class RegisteredSource(SourceInput):
    id: str
    approved: bool
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    owner_id: str


class IngestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=80_000)
    mode: Literal["fields", "notes"] = "fields"
    expected_source_revision: int | None = Field(default=None, ge=1, strict=True)
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    occurred_at: AwareDatetime | None = None
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


class EntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    kind: EntityKind
    name: str = Field(min_length=1, max_length=160)
    aliases: list[Annotated[str, Field(min_length=1, max_length=160)]] = Field(
        default_factory=list, max_length=20
    )
    sensitivity: Sensitivity = "private"
    _unicode = field_validator("name")(valid_unicode)

    @field_validator("aliases")
    @classmethod
    def valid_aliases(cls, values):
        for value in values:
            valid_unicode(value)
        return values


class EntityRecord(EntityInput):
    id: str
    owner_id: str
    source: Literal["manual"] = "manual"
    status: Literal["pending", "confirmed"]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class ResolveEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    kind: EntityKind | None = None
    allow_sensitive: bool = Field(default=False, strict=True)
    _unicode = field_validator("name")(valid_unicode)


class EntityResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["resolved", "ambiguous", "unknown"]
    matches: list[EntityRecord]


class EntityRevision(EntityRecord):
    change: Literal["created", "edited", "confirmed"]


class RelationshipInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    from_entity_id: str = Field(min_length=1, max_length=100)
    to_entity_id: str = Field(min_length=1, max_length=100)
    predicate: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    evidence_id: str = Field(min_length=1, max_length=100)
    sensitivity: Sensitivity = "private"


class RelationshipRecord(RelationshipInput):
    id: str
    owner_id: str
    evidence_revision: int = Field(ge=1)
    status: Literal["pending", "confirmed"]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class RelationshipRevision(RelationshipRecord):
    change: Literal["created", "confirmed"]


class IdentityContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[EntityRecord]
    relationships: list[RelationshipRecord]


class RetentionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    pending_days: int | None = Field(default=None, ge=1, le=365_000, strict=True)
    superseded_days: int | None = Field(default=None, ge=1, le=365_000, strict=True)
    expired_days: int | None = Field(default=None, ge=1, le=365_000, strict=True)
    history_days: int | None = Field(default=None, ge=1, le=365_000, strict=True)
    run_days: int | None = Field(default=None, ge=1, le=365_000, strict=True)


class RetentionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    policy: RetentionPolicy


class RetentionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: Literal["entries", "turns", "ingestion_runs"]
    id: str
    revision: int | None = None
    fingerprint: str | None = None


class RetentionCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: int = 0
    turns: int = 0
    ingestion_runs: int = 0


class RetentionPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of: AwareDatetime | None = None


class RetentionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    owner_id: str
    status: Literal["planned", "applied"]
    policy_revision: int = Field(ge=1)
    as_of: AwareDatetime
    created_at: datetime
    targets: list[RetentionTarget] = Field(max_length=1000)
    deleted_counts: RetentionCounts = Field(default_factory=RetentionCounts)


class TemporalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    as_of: AwareDatetime | None = None
    known_at: AwareDatetime | None = None
    allow_sensitive: bool = Field(default=False, strict=True)
    include_uncertain: bool = Field(default=False, strict=True)
    entity_id: str | None = Field(default=None, min_length=1, max_length=100)


class SelectedMemory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    record: MemoryRecord
    effective_belief: Belief
    effective_sensitivity: Sensitivity
    historical: bool


class LearningPolicy(BaseModel):
    """Owner policy can narrow learning/review, never bypass owner acceptance."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source_kinds: list[Literal["document", "project", "conversation", "event"]] = Field(
        default_factory=lambda: ["document", "project", "conversation", "event"], max_length=4
    )
    labels: list[Sensitivity] = Field(
        default_factory=lambda: ["public", "private", "sensitive"], max_length=3
    )
    max_candidates: int = Field(default=100, ge=1, le=100, strict=True)
    blocked_key_prefixes: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20
    )
    require_revision_labels: list[Sensitivity] = Field(default_factory=list, max_length=3)
    require_revision_key_prefixes: list[Annotated[str, Field(min_length=1, max_length=100)]] = (
        Field(default_factory=list, max_length=20)
    )

    @field_validator("blocked_key_prefixes", "require_revision_key_prefixes")
    @classmethod
    def prefixes(cls, values):
        for value in values:
            valid_unicode(value)
            if not value.strip():
                raise ValueError("Policy prefixes cannot be blank")
        return values


class LearningSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    policy: LearningPolicy


class ConsolidationMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    revision: int = Field(ge=1)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ConsolidationFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    entity_id: str | None = Field(default=None, min_length=1, max_length=100)
    key_prefix: str | None = Field(default=None, min_length=1, max_length=100)
    kinds: list[Literal["fact", "preference", "event", "decision"]] | None = Field(
        default=None, max_length=4
    )

    @field_validator("key_prefix")
    @classmethod
    def prefix(cls, value):
        if value is not None:
            valid_unicode(value)
            if not value.strip():
                raise ValueError("Selection prefix cannot be blank")
        return value


class ConsolidationGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keeper_id: str
    members: list[ConsolidationMember] = Field(min_length=2, max_length=1000)


class ConsolidationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    owner_id: str
    status: Literal["planned", "applied"]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    groups: list[ConsolidationGroup] = Field(max_length=100)
    created_at: AwareDatetime
    merged_count: int = Field(default=0, ge=0)


class MemoryExport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[7] = 7
    owner_id: str
    owner_entity_id: str | None = None
    entries: list[MemoryRecord]
    history: list[StoredTurn]
    revisions: list[MemoryRevision]
    sources: list[RegisteredSource]
    ingestion_runs: list[IngestionRun]
    origins: list[CandidateOrigin]
    forgotten: list[ForgottenDigest]
    entities: list[EntityRecord]
    entity_revisions: list[EntityRevision]
    relationships: list[RelationshipRecord]
    relationship_revisions: list[RelationshipRevision]
    retention_policy: RetentionSettings
    retention_plans: list[RetentionPlan]
    tool_permissions: list[ToolPermission]
    action_plans: list[ActionPlan]
    tasks: list[TaskRecord]
    notes: list[NoteRecord]
    action_events: list[ActionEvent]
    learning_policy: LearningSettings
    consolidation_plans: list[ConsolidationPlan]
    audit_events: list[AuditEvent]
    import_archives: list[ImportArchive]
    ingestion_replay_keys: list[ReplayKey]
