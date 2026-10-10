"""Owner-reviewed deletion scope; input never supplies table names or SQL."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .memory_models import valid_unicode

EraseKind = Literal["task", "note", "action", "source", "archive"]
EraseTable = Literal[
    "tasks",
    "notes",
    "action_plans",
    "action_events",
    "entries",
    "revisions",
    "sources",
    "ingestion_runs",
    "origins",
    "relationships",
    "relationships_revisions",
    "memory_digests",
    "forgotten",
    "import_archives",
]


class ErasureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: EraseKind
    id: str = Field(min_length=1, max_length=100)
    expected_owner_id: str = Field(min_length=1, max_length=100)
    expected_revision: int | None = Field(default=None, ge=1, strict=True)
    purge_output: bool = Field(default=False, strict=True)
    expected_output_revision: int | None = Field(default=None, ge=1, strict=True)
    forget_memories: bool = Field(default=False, strict=True)
    _unicode = field_validator("id", "expected_owner_id")(valid_unicode)

    @model_validator(mode="after")
    def exact_choices(self):
        if self.kind != "archive" and self.expected_revision is None:
            raise ValueError("A reviewed target revision is required")
        if self.kind == "archive" and self.expected_revision is not None:
            raise ValueError("Archives have no live revision")
        if self.kind != "action" and self.purge_output:
            raise ValueError("Only an action can optionally purge its output")
        if not self.purge_output and self.expected_output_revision is not None:
            raise ValueError("Output revision requires explicit output erasure")
        if self.kind != "source" and self.forget_memories:
            raise ValueError("Only source erasure can forget derived memories")
        return self


class ErasureRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    table: EraseTable
    key: str = Field(pattern=r"^[0-9a-f]{64}$")
    id: str
    revision: int | None = None
    label: str


class ErasurePreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ErasureRequest
    target: ErasureRef
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    removed: list[ErasureRef]
    updated: list[ErasureRef]
    added: list[ErasureRef]
    retained: list[ErasureRef]


class ErasureApproval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: ErasureRequest
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ErasureChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: EraseKind
    record: ErasureRef


class ErasureCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owner_id: str
    items: list[ErasureChoice]


class ErasureResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deleted: Literal[True] = True
    request: ErasureRequest
    digest: str
    removed_counts: dict[str, int]
    retained_counts: dict[str, int]
    forgotten_memories: int = Field(default=0, ge=0)
