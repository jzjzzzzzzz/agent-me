"""Bounded lexical/field/alias/relationship hybrid retrieval over owner-controlled context."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime, timedelta

from .identity import IdentityStore, canonical_alias
from .knowledge import KnowledgeBase
from .memory import Store
from .memory_models import TemporalQuery
from .memory_time import overlaps, utc
from .retrieval_models import AskRequest, PersonalEvidence, RetrievalResult
from .text import normalized_tokens

_STOP = set(
    (
        "a an and are as at be by can do does for from had has have how i in is it me my of on or "
        "the this to was what when where which who why will with you your tell about please know"
    ).split()
)
_FACETS = {
    "name": ("name", "名字", "姓名", "叫什么"),
    "skills": ("skills", "abilities", "技能", "擅长", "能力"),
    "role": ("role", "job", "profession", "职业", "职位"),
    "style": ("style", "format", "respond", "语气", "风格", "回复方式", "回答方式"),
    "goals": ("goals", "objectives", "目标"),
    "project": ("project", "projects", "项目", "在做", "working on"),
}
_KEYS = {
    "name": {"identity.name", "profile.name", "name", "display.name"},
    "skills": {"identity.skills", "profile.skills", "skills"},
    "role": {"identity.role", "profile.role", "role", "job.title", "project.role"},
    "style": {"response.style", "response.format", "style", "conversation.preference"},
}
_OWNER_PREFIXES = (
    "identity.",
    "profile.",
    "goals.",
    "projects.",
    "response.",
    "preferences.",
    "boundaries.",
    "decisions.",
    "events.",
)


def _contains(text, phrase):
    if any("\u3400" <= char <= "\u9fff" for char in phrase):
        return phrase in text
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))


def route_intent(request: AskRequest):
    if request.intent != "auto":
        return request.intent
    text = canonical_alias(request.question)
    phrases = {
        "profile": ("what do you know about me", "who am i", "我的档案", "了解我", "知道我的什么"),
        "preferences": (
            "my preferences",
            "my preference",
            "我的偏好",
            "如何回复我",
            "how should you respond",
        ),
        "relationships": (
            "relationship",
            "relationships",
            "works with",
            "who works on",
            "who does",
            "knows",
            "关系",
            "谁参与",
            "谁负责",
            "认识",
        ),
        "timeline": ("timeline", "history", "when did", "时间线", "历史", "何时", "什么时候"),
        "projects": ("my projects", "current project", "我的项目", "正在做", "working on"),
    }
    for intent, values in phrases.items():
        if any(_contains(text, phrase) for phrase in values):
            return intent
    return "recall"


def field_facet(key):
    key = unicodedata.normalize("NFC", key).casefold()
    for facet, keys in _KEYS.items():
        if key in keys:
            return facet
    if key.startswith(("project.", "projects.")) or key == "project":
        return "project"
    if key.startswith("goals.") or key == "goals":
        return "goals"
    return key


def evidence(**data):
    stable = {
        key: data.get(key)
        for key in (
            "kind",
            "path",
            "revision",
            "entity_id",
            "field",
            "value",
            "belief",
            "sensitivity",
            "confidence",
        )
    }
    data["id"] = (
        "ev_"
        + hashlib.sha256(
            json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:32]
    )
    return PersonalEvidence(**data)


def context_record(item: PersonalEvidence):
    return (
        f"Evidence: {item.id}\nSource: {item.path}\nState: {item.belief}\n"
        f"{item.field}: {item.value}"
    )


class PersonalRetriever:
    def __init__(self, store: Store, *, documents: dict[str, KnowledgeBase] | None = None):
        self.store = store
        self.identity = IdentityStore(store)
        self.documents = documents or {}
        if any(name not in {"public", "private"} for name in self.documents):
            raise ValueError("Document namespaces must be public or private")

    def _scope(self, request, intent):
        allowed = {
            item["id"]: item
            for item in self.identity.entities()
            if item["status"] == "confirmed"
            and (request.allow_sensitive or item["sensitivity"] != "sensitive")
        }
        if request.entity_id:
            return [request.entity_id] if request.entity_id in allowed else [], [], allowed, True
        if request.entity_alias:
            result = self.identity.resolve(
                request.entity_alias, allow_sensitive=request.allow_sensitive
            )
            return (
                [item["id"] for item in result["matches"]]
                if result["status"] == "resolved"
                else [],
                [item["id"] for item in result["matches"]]
                if result["status"] == "ambiguous"
                else [],
                allowed,
                True,
            )
        text = canonical_alias(request.question)
        pairs = {}
        for item in allowed.values():
            for name in [item["name"], *item["aliases"]]:
                alias = canonical_alias(name)
                if len(alias) >= 2 and _contains(text, alias):
                    pairs.setdefault(alias, set()).add(item["id"])
        # A fully spelled name is stronger than a shorter contained alias.
        selected = [
            alias
            for alias in pairs
            if not any(alias != other and alias in other for other in pairs)
        ]
        ambiguous = sorted(
            {item_id for alias in selected if len(pairs[alias]) > 1 for item_id in pairs[alias]}
        )
        if ambiguous:
            return [], ambiguous, allowed, True
        subjects = sorted({item_id for alias in selected for item_id in pairs[alias]})
        self_question = (
            intent in {"profile", "preferences", "projects"}
            or bool(re.search(r"\b(i|me|my|mine)\b", text))
            or "我" in text
        )
        if not subjects and self_question:
            owner = self.identity.owner()["entity_id"]
            if owner and owner not in allowed:
                return [], [], allowed, True
            subjects = [owner] if owner else []
        return subjects, [], allowed, self_question or bool(subjects)

    def retrieve(self, request: AskRequest):
        intent = route_intent(request)
        temporal_blocked = False
        if not any((request.as_of, request.known_at, request.since, request.until)):
            text = canonical_alias(request.question)
            year_matches = re.findall(
                r"\b(?:in|during|year)\s+((?:19|20)\d{2})\b|(?<!\d)((?:19|20)\d{2})年", text
            )
            years = [left or right for left, right in year_matches]
            now = datetime.now(UTC)
            if len(set(years)) > 1:
                temporal_blocked = True
            elif years or "last year" in text or "去年" in text:
                year = int(years[0]) if years else now.year - 1
                request = request.model_copy(
                    update={
                        "since": datetime(year, 1, 1, tzinfo=UTC),
                        "until": datetime(year + 1, 1, 1, tzinfo=UTC),
                    }
                )
            elif "yesterday" in text or "昨天" in text:
                start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                request = request.model_copy(
                    update={"since": start, "until": start + timedelta(days=1)}
                )
        subjects, ambiguity, entities, scoped = self._scope(request, intent)
        trace = [
            dict(stage="route", outcome="completed", count=1),
            dict(
                stage="scope", outcome="blocked" if ambiguity else "completed", count=len(subjects)
            ),
        ]
        owner = self.identity.owner()["entity_id"]
        blocked_owner = scoped and not subjects and owner is not None and owner not in entities
        if (
            temporal_blocked
            or ambiguity
            or blocked_owner
            or ((request.entity_id or request.entity_alias) and not subjects)
        ):
            return RetrievalResult(
                intent=intent,
                status="ambiguous" if ambiguity else "unknown",
                evidence=[],
                entities=[],
                ambiguity=ambiguity,
                context_chars=0,
                trace=trace,
                blocker="ambiguous_identity"
                if ambiguity
                else "ambiguous_time"
                if temporal_blocked
                else "unavailable_identity",
            )
        text = canonical_alias(request.question)
        facets = {
            facet
            for facet, words in _FACETS.items()
            if any(_contains(text, word) for word in words)
        }
        tokens = normalized_tokens(request.question) - _STOP
        for item_id in subjects:
            for alias in [entities[item_id]["name"], *entities[item_id]["aliases"]]:
                tokens -= normalized_tokens(alias)
        residual = set(tokens)
        for facet in facets:
            for word in _FACETS[facet]:
                residual -= normalized_tokens(word)
        residual -= {"current", "preferred", "favorite", "today"}
        selected = self.store.select(
            TemporalQuery(
                as_of=request.as_of,
                known_at=request.known_at,
                allow_sensitive=request.allow_sensitive,
                include_uncertain=True,
            )
        )
        asks_when = intent == "timeline" and (
            bool(re.search(r"\bwhen\b", text)) or "何时" in text or "什么时候" in text
        )
        candidates = []
        for selected_item in selected:
            item = selected_item["record"]
            if request.since or request.until:
                if item["category"] == "episodic":
                    occurrence = utc(item["occurred_at"])
                    if (
                        occurrence is None
                        or (request.since and occurrence < utc(request.since))
                        or (request.until and occurrence >= utc(request.until))
                    ):
                        continue
                elif not overlaps(
                    item,
                    {
                        "kind": item["kind"],
                        "valid_from": request.since,
                        "valid_until": request.until,
                        "occurred_at": None,
                    },
                ):
                    continue
                selected_item = {**selected_item, "effective_belief": item["belief"]}
            owner_unbound = item["entity_id"] is None and (
                item["key"].casefold().startswith(_OWNER_PREFIXES)
                or field_facet(item["key"])
                in {"name", "skills", "role", "style", "goals", "project"}
            )
            if scoped and item["entity_id"] not in subjects:
                if not owner_unbound or item["entity_id"] is not None:
                    continue
                # Global owner facts must not answer a question about somebody else.
                owner = self.identity.owner()["entity_id"]
                if subjects and subjects != [owner] and item["kind"] != "preference":
                    continue
            facet = field_facet(item["key"])
            coverage = len(tokens & normalized_tokens(item["key"] + " " + item["content"])) / max(
                len(tokens), 1
            )
            field_match = facet in facets and (scoped or not residual)
            intentional = (
                (intent == "profile" and (owner_unbound or item["entity_id"] in subjects))
                or (intent == "preferences" and item["kind"] == "preference")
                or (
                    intent == "projects"
                    and (
                        facet == "project"
                        or (
                            item["entity_id"] in entities
                            and entities[item["entity_id"]]["kind"] == "project"
                        )
                    )
                )
                or (intent == "timeline" and item["category"] == "episodic")
                or (item["entity_id"] in subjects and not tokens)
            )
            purpose = (
                "answer"
                if intentional or field_match or coverage >= 0.75
                else "presentation"
                if item["kind"] == "preference" and selected_item["effective_belief"] == "known"
                else None
            )
            if purpose is None:
                continue
            if asks_when and item["category"] == "episodic":
                purpose = "context"
            if request.minimum_confidence is not None and (
                item["confidence"] is None or item["confidence"] < request.minimum_confidence
            ):
                continue
            reasons = (
                (["intent"] if intentional else [])
                + (["field"] if field_match else [])
                + (["lexical"] if coverage else [])
                + (["alias"] if item["entity_id"] in subjects else [])
                + (["preference"] if purpose == "presentation" else [])
            )
            score = min(1.0, max(coverage, 0.9 if field_match else 0.85 if intentional else 0.1))
            candidates.append(
                evidence(
                    kind="memory_value",
                    path=f"memory/{item['id']}@{item['revision']}",
                    revision=item["revision"],
                    entity_id=item["entity_id"],
                    field=item["key"],
                    value=item["content"],
                    source=item["source"],
                    belief=selected_item["effective_belief"],
                    sensitivity=selected_item["effective_sensitivity"],
                    confidence=item["confidence"],
                    observed_at=item["updated_at"],
                    occurred_at=item["occurred_at"],
                    valid_from=item["valid_from"],
                    valid_until=item["valid_until"],
                    score=score,
                    reasons=reasons,
                    purpose=purpose,
                )
            )
            if asks_when and item["category"] == "episodic" and item["occurred_at"] is not None:
                candidates.append(
                    evidence(
                        kind="episode_time",
                        path=f"memory/{item['id']}@{item['revision']}",
                        revision=item["revision"],
                        entity_id=item["entity_id"],
                        field=item["key"] + ".occurred_at",
                        value=item["occurred_at"],
                        source=item["source"],
                        belief=selected_item["effective_belief"],
                        sensitivity=selected_item["effective_sensitivity"],
                        confidence=item["confidence"],
                        occurred_at=item["occurred_at"],
                        observed_at=item["updated_at"],
                        score=0.95,
                        reasons=["intent"],
                    )
                )
        for item_id in subjects:
            item = entities[item_id]
            if ("name" in facets or intent == "profile") and not any(
                (request.as_of, request.known_at, request.since, request.until)
            ):
                candidates.append(
                    evidence(
                        kind="entity_label",
                        path=f"identity/{item_id}@{item['revision']}",
                        revision=item["revision"],
                        entity_id=item_id,
                        field="entity.label",
                        value=item["name"],
                        source="manual",
                        belief="known",
                        sensitivity=item["sensitivity"],
                        observed_at=item["updated_at"],
                        score=0.8,
                        reasons=["alias"],
                    )
                )
            if intent in {"relationships", "projects"} and not any(
                (request.as_of, request.known_at, request.since, request.until)
            ):
                graph = self.identity.neighbours(item_id, allow_sensitive=request.allow_sensitive)
                labels = {entity["id"]: entity["name"] for entity in graph["entities"]}
                for edge in graph["relationships"]:
                    value = (
                        f"{labels[edge['from_entity_id']]} — {edge['predicate']} → "
                        f"{labels[edge['to_entity_id']]}"
                    )
                    backing = next(
                        (
                            row["record"]
                            for row in selected
                            if row["record"]["id"] == edge["evidence_id"]
                        ),
                        None,
                    )
                    if backing is None:
                        continue
                    candidates.append(
                        evidence(
                            kind="relationship",
                            path=f"relationship/{edge['id']}@{edge['revision']}",
                            revision=edge["revision"],
                            entity_id=edge["from_entity_id"],
                            field="relation." + edge["predicate"],
                            value=value,
                            source=f"memory:{edge['evidence_id']}@{edge['evidence_revision']}",
                            belief="known",
                            sensitivity=edge["sensitivity"],
                            confidence=backing["confidence"],
                            observed_at=edge["updated_at"],
                            score=0.95,
                            reasons=["relationship", "alias"],
                        )
                    )
        # Untimed/unbound documents cannot establish historical or owner-specific facts.
        if (
            request.include_documents
            and not scoped
            and not any((request.as_of, request.known_at, request.since, request.until))
        ):
            for namespace, knowledge in self.documents.items():
                for match in knowledge.search(request.question, limit=request.limit):
                    candidates.append(
                        evidence(
                            kind="document_excerpt",
                            path=f"{namespace}/knowledge/{match.document.path}",
                            field="source.excerpt",
                            value=match.excerpt,
                            source=namespace + "/knowledge",
                            belief="known",
                            sensitivity="public" if namespace == "public" else "private",
                            score=match.score,
                            reasons=["lexical"],
                        )
                    )
        candidates = list({item.id: item for item in candidates}.values())
        if request.minimum_confidence is not None:
            candidates = [
                item
                for item in candidates
                if item.confidence is not None and item.confidence >= request.minimum_confidence
            ]
        trace.append(dict(stage="retrieve", outcome="completed", count=len(candidates)))
        groups = {}
        for item in candidates:
            if item.kind == "memory_value" and item.purpose == "answer" and item.belief == "known":
                groups.setdefault(
                    (
                        item.entity_id,
                        field_facet(item.field),
                        item.occurred_at,
                        item.valid_from,
                        item.valid_until,
                    ),
                    [],
                ).append(item)
        disputed = {
            item.id
            for group in groups.values()
            if len({canonical_alias(item.value) for item in group}) > 1
            for item in group
            if field_facet(item.field) not in {"project", "goals"}
        }
        if disputed:
            candidates = [
                evidence(**{**item.model_dump(exclude={"id"}), "belief": "disputed"})
                if item.id in disputed
                else item
                for item in candidates
            ]
        # A historical/expired version of the same field is context, not an
        # unresolved current fact, when an eligible known value already answers it.
        known_fields = {
            (item.entity_id, canonical_alias(item.field))
            for item in candidates
            if item.purpose == "answer" and item.belief == "known"
        }
        candidates = [
            item.model_copy(update={"purpose": "context"})
            if item.belief in {"outdated", "unknown"}
            and (item.entity_id, canonical_alias(item.field)) in known_fields
            else item
            for item in candidates
        ]
        trace.append(dict(stage="conflicts", outcome="completed", count=len(disputed)))
        candidates.sort(
            key=lambda item: (
                item.purpose != "answer",
                item.belief != "known",
                -item.score,
                item.path,
            )
        )
        # Reserve two eligible presentation preferences, but never call them factual support.
        style = [item for item in candidates if item.purpose == "presentation"][:2]
        primary = [item for item in candidates if item.purpose == "answer"]
        context = [item for item in candidates if item.purpose == "context"]
        chosen, used = [], 0
        for item in primary[:1] + style[: max(0, request.limit - 1)] + primary[1:] + context:
            record = context_record(item)
            cost = len(record) + (2 if chosen else 0)
            if len(chosen) >= request.limit or used + cost > request.max_context_chars:
                continue
            chosen.append(item)
            used += cost
        trace.append(dict(stage="budget", outcome="completed", count=len(chosen)))
        answered = [item for item in chosen if item.purpose == "answer"]
        known = any(item.belief == "known" for item in answered)
        unsure = any(item.belief != "known" for item in answered)
        status = (
            "partial"
            if known and unsure
            else "known"
            if known
            else "disputed"
            if any(item.belief == "disputed" for item in answered)
            else "outdated"
            if any(item.belief == "outdated" for item in answered)
            else "inferred"
            if any(item.belief == "inferred" for item in answered)
            else "unknown"
        )
        return RetrievalResult(
            intent=intent,
            status=status,
            evidence=chosen,
            entities=subjects,
            context_chars=used,
            trace=trace,
        )
