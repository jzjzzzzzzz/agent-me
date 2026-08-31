from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class CollaborationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    workflow: Literal["baseline", "verified"] = "baseline"

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question must not be blank")
        return normalized


class Source(BaseModel):
    title: str
    path: str
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    mode: Literal["extractive", "openai-compatible"]
    sources: list[Source]


class CollaborationStage(BaseModel):
    sequence: int = Field(ge=1)
    agent: Literal["planner", "researcher", "critic", "writer", "verifier"]
    outcome: Literal["completed", "blocked"]
    summary: str
    metrics: dict[str, bool | int | float]


class CollaborationResponse(BaseModel):
    run_id: str = Field(pattern=r"^run_[0-9a-f]{32}$")
    workflow: Literal[
        "planner-researcher-critic-writer",
        "planner-researcher-critic-writer-verifier",
    ]
    mode: Literal["multi-agent-local"] = "multi-agent-local"
    answer: str
    grounded: bool
    sources: list[Source]
    trace: list[CollaborationStage]


class ProfileResponse(BaseModel):
    name: str
    description: str
    max_question_chars: int
    external_provider_enabled: bool
