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
    "disclosure_permissions",
}


class ImportArchive(BaseModel):
    """Historical authority is inspectable data, never a runnable grant or plan."""

    model_config = ConfigDict(extra="forbid")
    id: str
    owner_id: str
    source_version: Literal[6, 7, 8]
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority: dict[str, list[dict]] = Field(max_length=7)
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
    source_version: Literal[6, 7, 8]
    owner_id: str
    destination_owner_id: str | None = None
    counts: dict[str, int]
    tool_permissions_restored: Literal[False] = False
    executable_plans_restored: Literal[False] = False
    learning_sources_require_review: Literal[True] = True
    provider_permissions_restored: Literal[False] = False


class ImportResult(ImportPreview):
    imported: Literal[True] = True
    archive_id: str


class ImportDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: str
    empty: bool = Field(strict=True)
    max_snapshot_bytes: int = Field(ge=1, le=16 * 1024 * 1024)
    max_request_body_bytes: int = Field(ge=1024, le=10_000_000)


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


class DisclosurePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    enabled: bool = Field(default=False, strict=True)
    target_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    labels: list[Literal["public", "private", "sensitive"]] = Field(
        default_factory=lambda: ["public", "private"], max_length=3
    )
    namespaces: list[Literal["public", "private", "memory"]] = Field(
        default_factory=lambda: ["public", "memory"], max_length=3
    )
    entity_ids: list[str] | None = Field(default=None, max_length=100)
    memory_ids: list[str] | None = Field(default=None, max_length=100)
    document_paths: list[str] | None = Field(default=None, max_length=100)

    @field_validator("entity_ids", "memory_ids", "document_paths")
    @classmethod
    def bounded_names(cls, values):
        if values is not None:
            if len(values) != len(set(values)):
                raise ValueError("Disclosure scope names must be unique")
            for value in values:
                if not value.strip() or len(value) > 300:
                    raise ValueError("Disclosure scope names must be bounded and nonblank")
                try:
                    value.encode("utf-8")
                except UnicodeError:
                    raise ValueError("Disclosure scope names must be valid Unicode") from None
        return values


class DisclosureSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    policy: DisclosurePolicy
