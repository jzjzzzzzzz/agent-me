"""Grounded personal answers: literal atomic values, live evidence checks and inspectable traces."""

from uuid import uuid4

from .retrieval import PersonalRetriever, context_record, field_facet
from .retrieval_models import AskRequest, AtomicClaim, PersonalAnswer, VerifiedClaim


def _claim(item):
    return AtomicClaim(
        **{
            field: getattr(item, field)
            for field in ("kind", "entity_id", "field", "value", "belief", "confidence")
        },
        evidence_id=item.id,
    )


class ClaimVerifier:
    def __init__(self, retriever: PersonalRetriever):
        self.retriever = retriever

    @staticmethod
    def against(claims, authority):
        sources = {item.id: item for item in authority.evidence}
        results = []
        for claim in claims:
            item = sources.get(claim.evidence_id)
            if item is None:
                verdict, reason = "unsupported", "not_in_current_context"
            elif item.purpose != "answer":
                verdict, reason = "unsupported", "presentation_not_fact"
            elif any(
                getattr(claim, field) != getattr(item, field)
                for field in ("kind", "entity_id", "field", "value", "belief", "confidence")
            ):
                verdict, reason = "unsupported", "altered_claim"
            elif item.belief != "known":
                verdict, reason = "uncertain", "uncertain_belief"
            else:
                verdict, reason = "verified", "exact_source_value"
            results.append(VerifiedClaim(claim=claim, verdict=verdict, reason=reason))
        return results

    def verify(self, request: AskRequest, claims: list[AtomicClaim]):
        # Caller-provided evidence text is never authority. Re-run current retrieval.
        return self.against(claims, self.retriever.retrieve(request))


class PersonalAgent:
    def __init__(self, retriever: PersonalRetriever):
        self.retriever = retriever
        self.verifier = ClaimVerifier(retriever)

    def ask(self, request: AskRequest):
        retrieved = self.retriever.retrieve(request)
        drafts = [_claim(item) for item in retrieved.evidence if item.purpose == "answer"]
        authority = self.retriever.retrieve(request)
        checked = self.verifier.against(drafts, authority)
        # Never emit obsolete private text simply to explain that verification rejected it.
        accepted = [item for item in checked if item.verdict != "unsupported"]
        kept_ids = {item.claim.evidence_id for item in accepted}
        sources = [
            item for item in authority.evidence if item.id in kept_ids or item.purpose != "answer"
        ]
        known = any(item.verdict == "verified" for item in accepted)
        uncertain = any(item.verdict == "uncertain" for item in accepted)
        status = (
            "partial"
            if known and uncertain
            else "known"
            if known
            else authority.status
            if accepted or authority.status == "ambiguous"
            else "unknown"
        )
        zh = request.locale == "zh" or (
            request.locale == "auto"
            and any("\u3400" <= char <= "\u9fff" for char in request.question)
        )
        style = "plain"
        for source in sources:
            if source.belief == "known" and (
                source.purpose == "presentation" or field_facet(source.field) == "style"
            ):
                text = source.value.casefold()
                if any(word in text for word in ("bullet", "列表", "项目符号")):
                    style = "bullets"
                elif any(word in text for word in ("concise", "简洁", "先结论")):
                    style = "concise"
        messages = {
            "known": ("以下是可追溯的已确认依据：", "Here is the attributable confirmed evidence:"),
            "partial": (
                "部分信息有依据，另有信息需要保留不确定性：",
                "Some information is confirmed; other evidence remains uncertain:",
            ),
            "unknown": (
                "没有足够的已确认依据来回答。",
                "I do not have sufficient confirmed evidence to answer.",
            ),
            "disputed": (
                "相关信息存在争议，不能当作确定事实：",
                "Relevant information is disputed, not established fact:",
            ),
            "inferred": (
                "相关信息只是推断，尚不能作为确定事实：",
                "Relevant information is inferred, not established fact:",
            ),
            "outdated": (
                "只找到了过期依据，不能作为当前事实：",
                "Only outdated evidence is available, not current fact:",
            ),
            "ambiguous": (
                "对象不明确，请提供实体 ID 或完整名称。",
                "The subject is ambiguous; specify an entity ID or full name.",
            ),
        }
        prefix = messages[status][0 if zh else 1]
        if authority.blocker == "ambiguous_time":
            prefix = (
                "时间范围不明确，请指定 since/until 或 as_of。"
                if zh
                else "The time range is ambiguous; specify since/until or as_of."
            )
        paths = {item.id: item.path for item in sources}
        lines = []
        for item in accepted:
            claim = item.claim
            label = (
                "来源原文"
                if zh and claim.kind == "document_excerpt"
                else "Source quotation"
                if claim.kind == "document_excerpt"
                else claim.field
            )
            state = f" [{claim.belief}]" if item.verdict == "uncertain" else ""
            lines.append(f"{label}{state}: {claim.value} [{paths[claim.evidence_id]}]")
        answer = prefix + (
            "\n" + "\n".join(("- " if style == "bullets" else "") + line for line in lines)
            if lines
            else ""
        )
        chars = sum(len(context_record(item)) for item in sources) + max(0, len(sources) - 1) * 2
        trace = [
            *retrieved.trace,
            dict(
                stage="verify",
                outcome="blocked" if len(accepted) != len(checked) else "completed",
                count=len(accepted),
            ),
            dict(stage="compose", outcome="completed", count=len(accepted)),
        ]
        return PersonalAnswer(
            run_id="personal_" + uuid4().hex,
            intent=retrieved.intent,
            status=status,
            answer=answer,
            claims=accepted,
            evidence=sources,
            context_chars=chars,
            presentation=style,
            trace=trace,
        )
