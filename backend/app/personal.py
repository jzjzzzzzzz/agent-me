"""Opt-in, token-protected single-owner memory. Never used by public chat routes."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from .agency import Agency
from .agency_models import (
    ActionEvent,
    ActionPlan,
    ApprovalInput,
    NoteRecord,
    PermissionInput,
    PermissionUpdate,
    TaskRecord,
    ToolInvocation,
    ToolName,
    ToolPermission,
)
from .agent_runtime import AgentIntent, AgentOutcome, AgentRuntime, KnowledgeIntent
from .audit import AuditLog
from .config import Settings, get_settings
from .consolidation import ConsolidationManager
from .identity import IdentityStore
from .knowledge import Document, KnowledgeBase, Match
from .learning import LearningPipeline
from .learning_policy import LearningPolicyManager
from .memory import Store
from .memory_models import (
    CandidateOrigin,
    Confirm,
    ConsolidationFilter,
    ConsolidationPlan,
    EditEntry,
    EntityInput,
    EntityRecord,
    EntityResolution,
    EntityRevision,
    Entry,
    IdentityContext,
    IngestionInput,
    IngestionRun,
    LearningPolicy,
    LearningSettings,
    MemoryExport,
    MemoryMutation,
    MemoryRecord,
    MemoryRevision,
    RegisteredSource,
    RelationshipInput,
    RelationshipRecord,
    RelationshipRevision,
    ResolveEntity,
    RestoreMemory,
    RetentionPlan,
    RetentionPolicy,
    RetentionPreview,
    RetentionSettings,
    SelectedMemory,
    SourceInput,
    StoredTurn,
    TemporalQuery,
    valid_unicode,
)
from .owner_control import OwnerControl
from .owner_models import (
    ActionDelete,
    AuditEvent,
    ImportArchive,
    ImportPreview,
    ImportResult,
    RevisionDelete,
    SourceDelete,
    WorkspacePurge,
)
from .personal_agent import ClaimVerifier, PersonalAgent
from .portability import PortableMemory
from .provider import context_matches, generate_answer
from .retention import RetentionManager
from .retrieval import PersonalRetriever
from .retrieval_models import (
    AskRequest,
    PersonalAnswer,
    RetrievalResult,
    VerifiedClaim,
    VerifyRequest,
)
from .schemas import ChatTurn

router = APIRouter(prefix="/api/v1/personal", tags=["private twin"])


class PersonalChat(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=8000)
    allow_sensitive: bool = Field(default=False, strict=True)
    _unicode = field_validator("question")(valid_unicode)


class SourceReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool = Field(strict=True)
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


class IdentityReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class CreateEntity(EntityInput):
    distinct: bool = Field(default=False, strict=True)


class EditEntity(EntityInput):
    expected_revision: int = Field(ge=1, strict=True)


class ConfigureRetention(IdentityReview):
    policy: RetentionPolicy


class ConfigureLearning(IdentityReview):
    policy: LearningPolicy


class ReviewedDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    snapshot: dict = Field(max_length=40)


class ImportApproval(ImportPayload):
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class OwnerBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str | None = Field(default=None, min_length=1, max_length=100)


def personal_retriever(db: Store, config: Settings):
    options = dict(
        max_document_bytes=config.max_document_bytes,
        max_documents=config.max_knowledge_documents,
        max_corpus_bytes=config.max_knowledge_bytes,
    )
    return PersonalRetriever(
        db,
        documents={
            "public": KnowledgeBase(config.knowledge_dir, **options),
            "private": KnowledgeBase(str(db.root / "knowledge"), **options),
        },
    )


def bounded_request(payload: AskRequest, config: Settings):
    if len(payload.question) > config.max_question_chars:
        raise HTTPException(413, "Question exceeds configured limit")
    return payload.model_copy(
        update={"max_context_chars": min(payload.max_context_chars, config.max_context_chars)}
    )


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


def store(request: Request, config: Settings = Depends(authorize)) -> Store:
    db = Store(config.personal_data_dir)
    request.state.personal_store = db
    return db


@router.get("/audit", response_model=list[AuditEvent])
def audit_events(limit: int = 100, db: Store = Depends(store)):
    return AuditLog(db).events(limit)


@router.post("/audit/clear")
def clear_audit(db: Store = Depends(store)):
    return AuditLog(db).clear()


@router.post("/portability/preview", response_model=ImportPreview)
def preview_import(payload: ImportPayload, db: Store = Depends(store)):
    return PortableMemory(db).preview(payload.snapshot)


@router.post("/portability/import", response_model=ImportResult)
def import_snapshot(payload: ImportApproval, db: Store = Depends(store)):
    return PortableMemory(db).apply(payload.snapshot, payload.digest)


@router.get("/portability/archives", response_model=list[ImportArchive])
def import_archives(db: Store = Depends(store)):
    return OwnerControl(db).archives()


@router.post("/portability/archives/{archive_id}/delete")
def delete_import_archive(archive_id: str, db: Store = Depends(store)):
    return OwnerControl(db).delete_archive(archive_id)


@router.post("/tasks/{item_id}/delete")
def delete_task(item_id: str, payload: RevisionDelete, db: Store = Depends(store)):
    return OwnerControl(db).delete_output("tasks", item_id, payload.expected_revision)


@router.post("/notes/{item_id}/delete")
def delete_note(item_id: str, payload: RevisionDelete, db: Store = Depends(store)):
    return OwnerControl(db).delete_output("notes", item_id, payload.expected_revision)


@router.post("/actions/{item_id}/delete")
def delete_action(item_id: str, payload: ActionDelete, db: Store = Depends(store)):
    return OwnerControl(db).delete_action(item_id, **payload.model_dump())


@router.post("/sources/{source_id}/delete")
def delete_source(source_id: str, payload: SourceDelete, db: Store = Depends(store)):
    return OwnerControl(db).delete_source(source_id, **payload.model_dump())


@router.post("/workspace/purge")
def purge_workspace(payload: WorkspacePurge, db: Store = Depends(store)):
    return OwnerControl(db).purge(payload)


@router.get("/learning/policy", response_model=LearningSettings)
def learning_policy(db: Store = Depends(store)):
    return LearningPolicyManager(db).settings()


@router.post("/learning/policy", response_model=LearningSettings)
def configure_learning(payload: ConfigureLearning, db: Store = Depends(store)):
    return LearningPolicyManager(db).configure(payload.policy, payload.expected_revision)


@router.post("/consolidation/preview", response_model=ConsolidationPlan)
def preview_consolidation(
    payload: ConsolidationFilter = ConsolidationFilter(), db: Store = Depends(store)
):
    return ConsolidationManager(db).preview(payload)


@router.get("/consolidation/plans", response_model=list[ConsolidationPlan])
def consolidation_plans(db: Store = Depends(store)):
    return ConsolidationManager(db).plans()


@router.post("/consolidation/{plan_id}/apply", response_model=ConsolidationPlan)
def apply_consolidation(plan_id: str, payload: ReviewedDigest, db: Store = Depends(store)):
    return ConsolidationManager(db).apply(plan_id, payload.digest)


@router.post("/agent", response_model=AgentOutcome)
def route_agent(
    payload: AgentIntent, config: Settings = Depends(authorize), db: Store = Depends(store)
):
    if isinstance(payload.intent, KnowledgeIntent):
        payload = AgentIntent(
            intent=KnowledgeIntent(
                kind="ask", request=bounded_request(payload.intent.request, config)
            )
        )
    return AgentRuntime(personal_retriever(db, config)).route(payload)


@router.get("/tools/permissions", response_model=list[ToolPermission])
def tool_permissions(db: Store = Depends(store)):
    return Agency(db).permissions()


@router.post("/tools/permissions/{name}", response_model=ToolPermission)
def configure_tool(name: ToolName, payload: PermissionUpdate, db: Store = Depends(store)):
    return Agency(db).configure(
        name,
        PermissionInput.model_validate(payload.model_dump(exclude={"expected_revision"})),
        payload.expected_revision,
    )


@router.get("/actions", response_model=list[ActionPlan])
def action_plans(db: Store = Depends(store)):
    return Agency(db).plans()


@router.post("/actions", response_model=ActionPlan)
def create_action(payload: ToolInvocation, db: Store = Depends(store)):
    return Agency(db).plan(payload)


@router.post("/actions/{plan_id}/approve", response_model=ActionPlan)
def approve_action(plan_id: str, payload: ApprovalInput, db: Store = Depends(store)):
    return Agency(db).approve(plan_id, payload.expected_revision, payload.digest)


@router.post("/actions/{plan_id}/execute", response_model=ActionPlan)
def execute_action(plan_id: str, db: Store = Depends(store)):
    return Agency(db).execute(plan_id)


@router.post("/actions/{plan_id}/rollback", response_model=ActionPlan)
def rollback_action(plan_id: str, db: Store = Depends(store)):
    return Agency(db).rollback(plan_id)


@router.post("/actions/{plan_id}/cancel", response_model=ActionPlan)
def cancel_action(plan_id: str, db: Store = Depends(store)):
    return Agency(db).cancel(plan_id)


@router.get("/actions/{plan_id}/events", response_model=list[ActionEvent])
def action_events(plan_id: str, db: Store = Depends(store)):
    return Agency(db).events(plan_id)


@router.get("/tasks", response_model=list[TaskRecord])
def list_tasks(db: Store = Depends(store)):
    return Agency(db).tasks()


@router.get("/notes", response_model=list[NoteRecord])
def list_notes(db: Store = Depends(store)):
    return Agency(db).notes()


@router.post("/ask", response_model=PersonalAnswer)
def ask_personal(
    payload: AskRequest, config: Settings = Depends(authorize), db: Store = Depends(store)
):
    return PersonalAgent(personal_retriever(db, config)).ask(bounded_request(payload, config))


@router.post("/retrieve", response_model=RetrievalResult)
def retrieve_personal(
    payload: AskRequest, config: Settings = Depends(authorize), db: Store = Depends(store)
):
    return personal_retriever(db, config).retrieve(bounded_request(payload, config))


@router.post("/verify", response_model=list[VerifiedClaim])
def verify_personal(
    payload: VerifyRequest, config: Settings = Depends(authorize), db: Store = Depends(store)
):
    return ClaimVerifier(personal_retriever(db, config)).verify(
        bounded_request(payload.request, config), payload.claims
    )


@router.get("/identity/owner")
def owner_identity(db: Store = Depends(store)):
    return IdentityStore(db).owner()


@router.post("/identity/owner")
def bind_owner_identity(payload: OwnerBinding, db: Store = Depends(store)):
    return IdentityStore(db).bind_owner(payload.entity_id)


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


@router.get("/entries/{entry_id}/origins", response_model=list[CandidateOrigin])
def memory_origins(entry_id: str, db: Store = Depends(store)):
    return LearningPipeline(db).origins(entry_id)


@router.post("/memory/select", response_model=list[SelectedMemory])
def select_memory(payload: TemporalQuery, db: Store = Depends(store)):
    return db.select(payload)


@router.get("/identity/entities", response_model=list[EntityRecord])
def list_entities(db: Store = Depends(store)):
    return IdentityStore(db).entities()


@router.post("/identity/entities", response_model=EntityRecord)
def create_entity(payload: CreateEntity, db: Store = Depends(store)):
    return IdentityStore(db).add(
        EntityInput.model_validate(payload.model_dump(exclude={"distinct"})),
        distinct=payload.distinct,
    )


@router.post("/identity/entities/{entity_id}/edit", response_model=EntityRecord)
def edit_entity(entity_id: str, payload: EditEntity, db: Store = Depends(store)):
    return IdentityStore(db).edit(
        entity_id,
        EntityInput.model_validate(
            payload.model_dump(exclude={"expected_revision"}, exclude_unset=True)
        ),
        payload.expected_revision,
    )


@router.post("/identity/entities/{entity_id}/confirm", response_model=EntityRecord)
def confirm_entity(entity_id: str, payload: IdentityReview, db: Store = Depends(store)):
    return IdentityStore(db).confirm(entity_id, payload.expected_revision)


@router.get("/identity/entities/{entity_id}/history", response_model=list[EntityRevision])
def entity_history(entity_id: str, db: Store = Depends(store)):
    return IdentityStore(db).history(entity_id)


@router.post("/identity/entities/{entity_id}/delete")
def delete_entity(entity_id: str, db: Store = Depends(store)):
    return IdentityStore(db).delete(entity_id)


@router.post("/identity/resolve", response_model=EntityResolution)
def resolve_entity(payload: ResolveEntity, db: Store = Depends(store)):
    return IdentityStore(db).resolve(
        payload.name, kind=payload.kind, allow_sensitive=payload.allow_sensitive
    )


@router.get("/identity/entities/{entity_id}/neighbours", response_model=IdentityContext)
def entity_neighbours(entity_id: str, allow_sensitive: bool = False, db: Store = Depends(store)):
    return IdentityStore(db).neighbours(entity_id, allow_sensitive=allow_sensitive)


@router.get("/identity/relationships", response_model=list[RelationshipRecord])
def list_relationships(db: Store = Depends(store)):
    return IdentityStore(db).relationships()


@router.post("/identity/relationships", response_model=RelationshipRecord)
def create_relationship(payload: RelationshipInput, db: Store = Depends(store)):
    return IdentityStore(db).relate(payload)


@router.post("/identity/relationships/{relation_id}/confirm", response_model=RelationshipRecord)
def confirm_relationship(relation_id: str, payload: IdentityReview, db: Store = Depends(store)):
    return IdentityStore(db).confirm(relation_id, payload.expected_revision, relationship=True)


@router.get(
    "/identity/relationships/{relation_id}/history", response_model=list[RelationshipRevision]
)
def relationship_history(relation_id: str, db: Store = Depends(store)):
    return IdentityStore(db).history(relation_id, relationship=True)


@router.post("/identity/relationships/{relation_id}/delete")
def delete_relationship(relation_id: str, db: Store = Depends(store)):
    return IdentityStore(db).delete(relation_id, relationship=True)


@router.get("/retention/policy", response_model=RetentionSettings)
def retention_policy(db: Store = Depends(store)):
    return RetentionManager(db).settings()


@router.post("/retention/policy", response_model=RetentionSettings)
def configure_retention(payload: ConfigureRetention, db: Store = Depends(store)):
    return RetentionManager(db).configure(payload.policy, payload.expected_revision)


@router.post("/retention/preview", response_model=RetentionPlan)
def preview_retention(payload: RetentionPreview, db: Store = Depends(store)):
    return RetentionManager(db).preview(as_of=payload.as_of)


@router.get("/retention/plans", response_model=list[RetentionPlan])
def retention_plans(db: Store = Depends(store)):
    return RetentionManager(db).plans()


@router.post("/retention/plans/{plan_id}/apply", response_model=RetentionPlan)
def apply_retention(plan_id: str, db: Store = Depends(store)):
    return RetentionManager(db).apply(plan_id)


@router.get("/learning/sources", response_model=list[RegisteredSource])
def learning_sources(db: Store = Depends(store)):
    return LearningPipeline(db).sources()


@router.post("/learning/sources", response_model=RegisteredSource)
def register_source(payload: SourceInput, db: Store = Depends(store)):
    return LearningPipeline(db).register(payload)


@router.post("/learning/sources/{source_id}/review", response_model=RegisteredSource)
def review_source(source_id: str, payload: SourceReview, db: Store = Depends(store)):
    return LearningPipeline(db).approve(
        source_id, approved=payload.approved, expected_revision=payload.expected_revision
    )


@router.post("/learning/sources/{source_id}/ingest", response_model=IngestionRun)
def ingest_source(source_id: str, payload: IngestionInput, db: Store = Depends(store)):
    return LearningPipeline(db).ingest(source_id, payload)


@router.get("/learning/runs", response_model=list[IngestionRun])
def learning_runs(db: Store = Depends(store)):
    return LearningPipeline(db).runs()


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
    workspace_owner = await run_in_threadpool(lambda: db.owner_id)
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
    private = await run_in_threadpool(
        db.context, payload.question, allow_sensitive=payload.allow_sensitive
    )
    matches = sorted(private + local + public, key=lambda m: m.score, reverse=True)
    # Deliberately don't re-inject stored conversations: deleted memories must not return
    # through stale chat history. History is persisted for display, not factual grounding.
    history: list[ChatTurn] = []
    answer, mode = await generate_answer(
        question=payload.question, history=history, matches=matches, settings=config
    )
    await run_in_threadpool(
        db.save_chat, payload.question, answer, expected_owner_id=workspace_owner
    )
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
