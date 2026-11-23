"""Owner-chat memory proposals. No model, network or transcript replay."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .memory_models import Entry

CaptureOutcome = Literal["created", "existing", "superseded", "forgotten", "ignored"]


class ChatCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: str
    outcome: CaptureOutcome
    memory_id: str | None = None


class TurnCapture(Entry):
    """The content is a verbatim, contiguous excerpt of a stored owner message."""

    sensitivity: Literal["private", "sensitive"] = "private"


@dataclass(frozen=True)
class Proposal:
    entry: Entry | None
    explicit: bool = False


_COMMAND = re.compile(r"^(?P<verb>remember|correct|记住|記住|更正)\s*[:：]", re.IGNORECASE)
_TYPED = re.compile(
    r"^(fact|preference|event|decision|事实|事實|偏好|事件|决策|決策)"
    r"[ \t]+([a-z][a-z0-9_.-]{0,99})[ \t]*[=＝][ \t]*(.+)$",
    re.IGNORECASE,
)
_KINDS = {
    "事实": "fact",
    "事實": "fact",
    "偏好": "preference",
    "事件": "event",
    "决策": "decision",
    "決策": "decision",
}
_CUES = {
    "preference": re.compile(
        r"^(?:以后|以後|今后|今後|从今以后|從今以後|我的长期偏好|我的長期偏好|"
        r"from now on\b|my (?:long-term|standing) preference\b)",
        re.IGNORECASE,
    ),
    "decision": re.compile(
        r"^(?:我正式决定|我正式決定|我们决定|我們決定|"
        r"i have decided\b|we have decided\b)",
        re.IGNORECASE,
    ),
}
_TEMPORARY = re.compile(
    r"这次|這次|这封|這封|今天|临时|臨時|仅限|僅限|假如|如果|"
    r"\b(?:this time|today|just this|for this (?:reply|email)|temporarily|suppose|"
    r"what if|if)\b",
    re.IGNORECASE,
)


def propose(question: str, *, suggest: bool, project_id: str | None) -> Proposal:
    """Treat only exact user text as evidence and never infer subject or effective dates."""
    question = question.strip()
    command = _COMMAND.match(question)
    if command:
        body = question[command.end() :].strip()
        typed = _TYPED.fullmatch(body)
        if typed:
            kind, key, content = typed.groups()
            kind = _KINDS.get(kind, kind.lower())
            content = content.strip()
        elif command["verb"].casefold() in {"correct", "更正"} or "=" in body or "＝" in body:
            return Proposal(None, explicit=True)
        else:
            kind, key, content = "preference", "conversation.preference", body
        if not content or len(content) > 2000:
            return Proposal(None, explicit=True)
        return Proposal(
            Entry(kind=kind, key=key.lower(), content=content, entity_id=project_id),
            explicit=True,
        )
    if not suggest or not 1 <= len(question) <= 600 or re.search(r"[?？\n\r]", question):
        return Proposal(None)
    if _TEMPORARY.search(question):
        return Proposal(None)
    for kind, cue in _CUES.items():
        if cue.match(question):
            # Distinct suggestions must not silently compete for the same canonical field.
            # The owner can edit the generated field or use an explicit typed command.
            suffix = hashlib.sha256(question.encode("utf-8")).hexdigest()[:20]
            return Proposal(
                Entry(
                    kind=kind,
                    key=f"conversation.{kind}.{suffix}",
                    content=question,
                    entity_id=project_id,
                )
            )
    return Proposal(None)
