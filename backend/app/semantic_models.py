"""Explicit request consent and untrusted literal-span classification proposals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .memory_models import IngestionInput, valid_unicode


class SemanticIngestion(IngestionInput):
    mode: Literal["notes"] = (
        "notes"  # Source format; the run's extractor identifies model assistance.
    )
    expected_source_revision: int = Field(ge=1, strict=True)
    expected_disclosure_revision: int = Field(ge=1, strict=True)
    reviewed_target_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    allow_provider: bool = Field(default=False, strict=True)
    allow_sensitive: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def valid_window(self):
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("Validity end must follow its start")
        return self

    def ingestion(self):
        return IngestionInput.model_validate(
            {field: getattr(self, field) for field in IngestionInput.model_fields}
        )


class SpanProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["fact", "preference", "event", "decision"]
    key: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=2000)
    start: int | None = Field(default=None, ge=0, strict=True)
    _unicode = field_validator("key", "quote")(valid_unicode)

    @model_validator(mode="after")
    def literal_edges(self):
        if (
            self.quote != self.quote.strip()
            or not self.quote.strip()
            or self.key != self.key.strip()
        ):
            raise ValueError("Keys and quotations must have explicit nonblank trimmed boundaries")
        return self


class SpanProposals(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidates: list[SpanProposal] = Field(max_length=100)
