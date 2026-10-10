"""Personal retrieval and exact claim/evidence contracts; no provider or transport dependency."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from .memory_models import Belief, Sensitivity, valid_unicode

Intent = Literal[
    "auto", "recall", "profile", "preferences", "projects", "timeline", "relationships"
]
EvidenceKind = Literal[
    "memory_value", "episode_time", "document_excerpt", "entity_label", "relationship"
]


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=8000)
    intent: Intent = "auto"
    entity_id: str | None = Field(default=None, min_length=1, max_length=100)
    entity_alias: str | None = Field(default=None, min_length=1, max_length=160)
    as_of: AwareDatetime | None = None
    known_at: AwareDatetime | None = None
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None
    allow_sensitive: bool = Field(default=False, strict=True)
    include_documents: bool = Field(default=True, strict=True)
    minimum_confidence: float | None = Field(
        default=None, ge=0, le=1, strict=True, allow_inf_nan=False
    )
    limit: int = Field(default=12, ge=1, le=20, strict=True)
    max_context_chars: int = Field(default=12000, ge=256, le=100000, strict=True)
    locale: Literal["auto", "en", "zh"] = "auto"
    _unicode = field_validator("question", "entity_alias")(
        lambda value: valid_unicode(value) if value is not None else value
    )

    @model_validator(mode="after")
    def one_subject(self):
        if self.entity_id is not None and self.entity_alias is not None:
            raise ValueError("Specify an entity ID or alias, not both")
        if self.since and self.until and self.until <= self.since:
            raise ValueError("Time window must end after it starts")
        if self.as_of and (self.since or self.until):
            raise ValueError("Choose a point in valid time or a validity window")
        return self


class PersonalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    kind: EvidenceKind
    path: str
    revision: int | None = None
    entity_id: str | None = None
    field: str
    value: str
    source: str
    belief: Belief
    sensitivity: Sensitivity
    confidence: float | None = None
    observed_at: str | None = None
    occurred_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    reasons: list[Literal["lexical", "field", "alias", "relationship", "intent", "preference"]]
    purpose: Literal["answer", "presentation", "context"] = "answer"


class RetrievalStage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["route", "scope", "retrieve", "conflicts", "budget", "verify", "compose"]
    outcome: Literal["completed", "blocked"]
    count: int = Field(ge=0)


class RetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: Intent
    status: Literal["known", "partial", "unknown", "disputed", "inferred", "outdated", "ambiguous"]
    evidence: list[PersonalEvidence]
    entities: list[str]
    ambiguity: list[str] = Field(default_factory=list)
    context_chars: int = Field(ge=0)
    trace: list[RetrievalStage]
    blocker: Literal["ambiguous_identity", "unavailable_identity", "ambiguous_time"] | None = None


class AtomicClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: EvidenceKind
    entity_id: str | None = None
    field: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=2000)
    evidence_id: str
    belief: Belief
    confidence: float | None = Field(default=None, ge=0, le=1, strict=True, allow_inf_nan=False)
    _unicode = field_validator("field", "value")(valid_unicode)


class VerifiedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim: AtomicClaim
    verdict: Literal["verified", "uncertain", "unsupported"]
    reason: Literal[
        "exact_source_value",
        "uncertain_belief",
        "not_in_current_context",
        "altered_claim",
        "presentation_not_fact",
    ]


class VerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    request: AskRequest
    claims: list[AtomicClaim] = Field(max_length=20)


class PersonalAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str
    mode: Literal["personal-grounded-local"] = "personal-grounded-local"
    intent: Intent
    status: Literal["known", "partial", "unknown", "disputed", "inferred", "outdated", "ambiguous"]
    answer: str
    claims: list[VerifiedClaim]
    evidence: list[PersonalEvidence]
    context_chars: int
    presentation: Literal["plain", "bullets", "concise"]
    trace: list[RetrievalStage]
