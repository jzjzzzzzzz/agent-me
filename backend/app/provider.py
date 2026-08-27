import httpx

from .config import Settings
from .knowledge import Match
from .schemas import ChatTurn


def extractive_answer(matches: list[Match]) -> str:
    if not matches:
        return "I could not find a grounded answer in the configured knowledge files."
    return matches[0].excerpt


async def generate_answer(
    *, question: str, history: list[ChatTurn], matches: list[Match], settings: Settings
) -> tuple[str, str]:
    configured = all((settings.llm_base_url, settings.llm_api_key, settings.llm_model))
    if not configured:
        return extractive_answer(matches), "extractive"

    context = "\n\n".join(
        f"Source: {match.document.path}\n{match.excerpt}" for match in matches
    )[: settings.max_context_chars]
    system = (
        "Answer only from the supplied context. If the context is insufficient, say so. "
        "Do not invent personal facts. Cite source paths in brackets.\n\nContext:\n" + context
    )
    messages = [{"role": "system", "content": system}]
    messages.extend(turn.model_dump() for turn in history)
    messages.append({"role": "user", "content": question})

    endpoint = settings.llm_base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            endpoint,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={"model": settings.llm_model, "messages": messages, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
    return str(data["choices"][0]["message"]["content"]), "openai-compatible"
