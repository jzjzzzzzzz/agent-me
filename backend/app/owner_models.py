"""Content-free audit and portable owner-control contracts."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    owner_id: str
    actor: Literal["core", "api", "cli"]
    operation: str = Field(pattern=r"^[a-z][a-z0-9_.]{0,79}$")
    outcome: Literal["succeeded", "denied", "failed"]
    counts: dict[
        Annotated[str, Field(pattern=r"^[a-z_]{1,40}$")], Annotated[int, Field(ge=0, strict=True)]
    ] = Field(default_factory=dict, max_length=10)
    created_at: AwareDatetime


class ReplayKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    key: str = Field(pattern=r"^[0-9a-f]{64}$")


ARCHIVE_KEYS = {
    "tool_permissions",
    "action_plans",
    "action_events",
    "retention_plans",
    "consolidation_plans",
    "source_approvals",
}


class ImportArchive(BaseModel):
    """Historical authority is inspectable data, never a runnable grant or plan."""

    model_config = ConfigDict(extra="forbid")
    id: str
    owner_id: str
    source_version: Literal[6, 7]
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: dict[str, list[dict]] = Field(max_length=6)
    created_at: AwareDatetime

    @field_validator("authority")
    @classmethod
    def registered_keys(cls, value):
        if not set(value) <= ARCHIVE_KEYS:
            raise ValueError("Archive has unregistered authority categories")
        return value


class ImportPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_version: Literal[6, 7]
    owner_id: str
    counts: dict[str, int]
    tool_permissions_restored: Literal[False] = False
    executable_plans_restored: Literal[False] = False
    learning_sources_require_review: Literal[True] = True


class ImportResult(ImportPreview):
    imported: Literal[True] = True
    archive_id: str


class RevisionDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class WorkspacePurge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_owner_id: str = Field(min_length=1, max_length=100)
    confirmation: Literal["erase-personal-workspace"]


class ActionDelete(RevisionDelete):
    purge_output: bool = Field(default=False, strict=True)
    expected_output_revision: int | None = Field(default=None, ge=1, strict=True)


class SourceDelete(RevisionDelete):
    forget_memories: bool = Field(default=False, strict=True)
