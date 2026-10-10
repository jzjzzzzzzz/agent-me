"""Typed know/recommend/act routing. Routing never constitutes execution approval."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .agency import Agency
from .agency_models import ActionPlan, ToolInvocation
from .personal_agent import PersonalAgent
from .retrieval import PersonalRetriever
from .retrieval_models import AskRequest, PersonalAnswer


class KnowledgeIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["ask"]
    request: AskRequest


class RecommendIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["recommend"]
    invocation: ToolInvocation


class ActIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["act"]
    invocation: ToolInvocation


class AgentIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    intent: Annotated[KnowledgeIntent | RecommendIntent | ActIntent, Field(discriminator="kind")]


class AgentOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["knowledge", "recommendation", "action_plan"]
    result: PersonalAnswer | ActionPlan


class AgentRuntime:
    def __init__(self, retriever: PersonalRetriever):
        self.agent = PersonalAgent(retriever)
        self.agency = Agency(retriever.store)

    def route(self, payload: AgentIntent):
        intent = payload.intent
        if isinstance(intent, KnowledgeIntent):
            return AgentOutcome(kind="knowledge", result=self.agent.ask(intent.request))
        recommendation = isinstance(intent, RecommendIntent)
        invocation = ToolInvocation.model_validate(
            {**intent.invocation.model_dump(), "intent": "recommend" if recommendation else "act"}
        )
        return AgentOutcome(
            kind="recommendation" if recommendation else "action_plan",
            result=self.agency.plan(invocation),
        )
