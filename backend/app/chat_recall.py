"""Controlled field lookup and conservative term scoring for scoped private chat."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from .knowledge import Document, Match
from .text import normalized_tokens


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    keys: frozenset[str]
    phrases: frozenset[str]
    project: bool = False


def _field(name, keys, phrases, *, kind="fact", project=False):
    return Field(name, kind, frozenset(keys.split()), frozenset(phrases), project)


# Whole-question aliases only: "my name" is not a match for "my colleague's name".
_FIELDS = (
    _field(
        "name",
        "identity.name profile.name display.name name",
        (
            "what is my name",
            "whats my name",
            "my name",
            "do you remember my name",
            "what am i called",
            "我叫什么",
            "我叫什麼",
            "我的名字",
            "我的名字是什么",
            "我的名字是什麼",
            "你记得我的名字吗",
            "你記得我的名字嗎",
        ),
    ),
    _field(
        "role",
        "identity.role profile.role job.title profession role",
        (
            "what is my job",
            "what is my role",
            "what do i do for work",
            "what is my profession",
            "what do i do for a living",
            "我做什么工作",
            "我做什麼工作",
            "我的职业是什么",
            "我的職業是什麼",
            "我是什么职业",
            "我是什麼職業",
            "我的职位",
            "我的職位",
        ),
    ),
    _field(
        "skills",
        "identity.skills profile.skills skills",
        (
            "what am i good at",
            "what can i do well",
            "what are my skills",
            "what abilities do i have",
            "我擅长什么",
            "我擅長什麼",
            "我会什么技能",
            "我會什麼技能",
            "我的技能是什么",
            "我的技能是什麼",
        ),
    ),
    _field(
        "current_project",
        "projects.current project.current",
        (
            "what is my current project",
            "what am i currently working on",
            "my current project",
            "我现在在做什么项目",
            "我現在在做什麼專案",
            "我当前的项目是什么",
            "我目前在做什麼專案",
        ),
    ),
    _field(
        "project_deadline",
        "project.deadline projects.deadline deadline",
        (
            "when is this due",
            "when is this project due",
            "what is the project deadline",
            "what is the deadline",
            "deadline for this project",
            "项目什么时候交",
            "專案什麼時候交",
            "这个项目什么时候交",
            "這個專案什麼時候交",
            "项目截止日期是什么",
            "專案截止日期是什麼",
        ),
        project=True,
    ),
    _field(
        "project_status",
        "project.status projects.status project.progress",
        (
            "how is this project going",
            "what is the project status",
            "what is the status of this project",
            "这个项目进展怎么样",
            "這個專案進展如何",
            "项目进展如何",
            "专案进展如何",
            "這個專案進度如何",
        ),
        project=True,
    ),
    _field(
        "response_style",
        "response.style response.format style conversation.preference",
        (
            "how should you respond",
            "how do i like you to answer",
            "what is my reply style",
            "what is my preferred response style",
            "我喜欢你怎么回答",
            "我喜歡你怎麼回答",
            "我偏好怎样的回复",
            "我偏好怎樣的回覆",
            "我的回答偏好是什么",
            "我的回答偏好是什麼",
        ),
        kind="preference",
    ),
)
_BY_PHRASE = {phrase: field for field in _FIELDS for phrase in field.phrases}
_DEFAULTS = frozenset(
    {
        "style",
        "response.style",
        "response.format",
        "response.tone",
        "response.language",
        "conversation.preference",
    }
)
_STOP = frozenset(
    (
        "a an and are as at be by can could did do does for from had has have how i in is it me "
        "my of on or please remember s tell that the this to was what when where which who why "
        "will with would you your about"
    ).split()
)
_HAN_FILL = frozenset("的了吗嗎呢吧是我你他她它们們啊呀")
_HAN_RUNS = re.compile(r"[\u3400-\u9fff]+")
_MIN_COVERAGE = 0.75


@dataclass(frozen=True)
class ChatMemoryMatch(Match):
    reason: Literal["field", "lexical", "presentation_default"]
    revision: int


@dataclass(frozen=True)
class ChatRecall:
    matches: tuple[ChatMemoryMatch, ...]
    field: str | None = None
    conflict: bool = False


def canonical_key(value):
    return unicodedata.normalize("NFKC", value).casefold()


def field_for_question(question: str) -> Field | None:
    phrase = " ".join(canonical_key(question).strip().rstrip("?!.。！").split())
    for prefix in ("please ", "can you tell me ", "请问", "請問"):
        if phrase.startswith(prefix):
            phrase = phrase.removeprefix(prefix).lstrip(" :")
    return _BY_PHRASE.get(phrase.replace("’", "").replace("'", ""))


def _han_pairs(text):
    return {
        run[index : index + 2]
        for run in _HAN_RUNS.findall(text)
        for index in range(len(run) - 1)
        if all(char not in _HAN_FILL for char in run[index : index + 2])
    }


def _matched_overlap(terms, pairs, excerpt):
    common = terms & normalized_tokens(excerpt)
    coverage = len(common) / max(1, len(terms))
    if coverage < _MIN_COVERAGE:
        return 0.0
    # A shared single Han character is not a useful anchor on its own.
    if not any(not _HAN_RUNS.fullmatch(word) and len(word) >= 2 for word in common):
        if not pairs.intersection(_han_pairs(canonical_key(excerpt))):
            return 0.0
    return coverage


def _match(row, score, reason):
    item = row["record"]
    excerpt = f"{item['key']}: {item['content']}"
    return ChatMemoryMatch(
        Document(item["key"], f"memory/{item['id']}", excerpt),
        excerpt,
        score,
        reason,
        item["revision"],
    )


def rank_chat(question, rows, *, project_id=None, limit=20, preference_slots=5, enabled=True):
    """Rank already-authorized, current records; never expands which subjects are eligible."""
    field = field_for_question(question)
    if not enabled:
        return ChatRecall((), field.name if field else None)
    if field:
        eligible = [
            row
            for row in rows
            if row["record"]["kind"] == field.kind
            and canonical_key(row["record"]["key"]) in field.keys
            and (
                row["record"]["entity_id"] == project_id
                if field.project and project_id is not None
                else project_id is None
                or row["record"]["entity_id"] != project_id
                or field.kind == "preference"
            )
        ]
        # Distinct values under equivalent fact keys are conflicting, not synonyms for values.
        # Retain owner-controlled evidence; never guess based on insertion order or recency.
        if field.kind == "fact" and len({row["record"]["content"] for row in eligible}) > 1:
            return ChatRecall((), field.name, conflict=True)
        return ChatRecall(
            tuple(_match(row, 1.0, "field") for row in eligible[:limit]),
            field.name,
        )
    text = canonical_key(question)
    terms = normalized_tokens(text) - _STOP - _HAN_FILL
    pairs = _han_pairs(text)
    preferences = []
    facts = []
    for row in rows:
        item = row["record"]
        excerpt = f"{item['key']}: {item['content']}"
        score = _matched_overlap(terms, pairs, excerpt)
        preference = item["kind"] == "preference"
        if score:
            (preferences if preference else facts).append(_match(row, score, "lexical"))
        elif preference and canonical_key(item["key"]) in _DEFAULTS:
            preferences.append(_match(row, 0.0, "presentation_default"))
    preferences.sort(key=lambda match: match.score, reverse=True)
    facts.sort(key=lambda match: match.score, reverse=True)
    kept_facts = facts[: limit - min(len(preferences), preference_slots)]
    kept = kept_facts + preferences[: limit - len(kept_facts)]
    return ChatRecall(tuple(sorted(kept, key=lambda match: match.score, reverse=True)))
