"""Owner-approved local tool contracts. Memory is data, never execution authority."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

ToolName = Literal["tasks.create", "tasks.complete", "notes.create"]
DataLabel = Literal["public", "private", "sensitive"]


class TaskCreateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    due_at: AwareDatetime | None = None
    project_id: str | None = Field(default=None, min_length=1, max_length=100)


class TaskCompleteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str = Field(min_length=1, max_length=100)
    expected_revision: int = Field(ge=1, strict=True)


class NoteCreateArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=8000)
    project_id: str | None = Field(default=None, min_length=1, max_length=100)


class ToolInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tool: ToolName
    arguments: dict = Field(max_length=8)
    idempotency_key: str = Field(min_length=1, max_length=100)
    sensitivity: DataLabel = "private"
    source_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20
    )
    intent: Literal["recommend", "act"] = "act"


class PermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = Field(strict=True)
    labels: list[DataLabel] = Field(default_factory=lambda: ["public", "private"], max_length=3)
    entity_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, max_length=100
    )


class ToolPermission(PermissionInput):
    tool: ToolName
    owner_id: str
    scope: Literal["workspace_tasks", "workspace_notes"]
    revision: int = Field(ge=1)


class ActionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    plan_id: str
    stage: Literal["intent", "plan", "approval", "execution", "rollback", "cancellation"]
    outcome: Literal[
        "recommended",
        "planned",
        "approved",
        "completed",
        "blocked",
        "failed",
        "rolled_back",
        "cancelled",
    ]
    code: str
    created_at: datetime


class ActionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    owner_id: str
    invocation: ToolInvocation
    permission_revision: int
    source_revisions: dict[str, int]
    entity_revisions: dict[str, int]
    digest: str
    request_digest: str
    revision: int = Field(ge=1)
    status: Literal[
        "recommended", "planned", "approved", "completed", "failed", "rolled_back", "cancelled"
    ]
    attempts: int = Field(ge=0)
    result: dict | None = None
    undo: dict | None = None
    approved_digest: str | None = None
    created_at: datetime
    updated_at: datetime


class TaskRecord(TaskCreateArgs):
    id: str
    owner_id: str
    created_by: str
    sensitivity: DataLabel
    source_ids: list[str]
    status: Literal["open", "completed"]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class NoteRecord(NoteCreateArgs):
    id: str
    owner_id: str
    created_by: str
    sensitivity: DataLabel
    source_ids: list[str]
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision: int = Field(ge=1, strict=True)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PermissionUpdate(PermissionInput):
    expected_revision: int = Field(ge=1, strict=True)
