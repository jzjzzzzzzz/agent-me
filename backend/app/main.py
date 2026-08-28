from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .knowledge import KnowledgeBase, KnowledgeLoadError
from .provider import ProviderError, generate_answer
from .schemas import ChatRequest, ChatResponse, ProfileResponse, Source

app = FastAPI(title="Agent-Me Starter API", version="1.0.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


_PROVIDER_ERROR_MESSAGES = {
    "provider_configuration_incomplete": "Provider configuration is incomplete.",
    "provider_response_invalid": "Answer provider returned an invalid response.",
    "provider_response_too_large": "Answer provider response exceeds the configured limit.",
    "provider_timeout": "Answer provider timed out.",
    "provider_rate_limited": "Answer provider is rate-limiting requests.",
    "provider_request_failed": "Answer provider rejected the request.",
    "provider_unavailable": "Answer provider is temporarily unavailable.",
}


@app.exception_handler(ProviderError)
async def provider_error(_: Request, error: ProviderError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "detail": _PROVIDER_ERROR_MESSAGES.get(
                error.code, "Answer provider is temporarily unavailable."
            ),
            "code": error.code,
        },
    )


@app.exception_handler(KnowledgeLoadError)
async def knowledge_load_error(_: Request, error: KnowledgeLoadError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Knowledge base is temporarily unavailable.",
            "code": error.code,
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/ready", responses={503: {"description": "No knowledge documents are loaded"}})
async def ready(
    config: Settings = Depends(get_settings),
) -> JSONResponse:
    documents = KnowledgeBase(
        config.knowledge_dir, max_document_bytes=config.max_document_bytes
    ).documents()
    is_ready = bool(documents) and config.provider_state != "misconfigured"
    content: dict[str, object] = {
        "status": "ready" if is_ready else "not_ready",
        "knowledge_documents": len(documents),
        "answer_mode": config.provider_state,
    }
    return JSONResponse(status_code=200 if is_ready else 503, content=content)


@app.get("/api/v1/profile", response_model=ProfileResponse)
async def profile(config: Settings = Depends(get_settings)) -> ProfileResponse:
    return ProfileResponse(name=config.app_name, description=config.app_description)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, config: Settings = Depends(get_settings)) -> ChatResponse:
    if len(payload.question) > config.max_question_chars:
        raise HTTPException(status_code=413, detail="question exceeds configured limit")
    if sum(len(turn.content) for turn in payload.history) > config.max_history_chars:
        raise HTTPException(status_code=413, detail="history exceeds configured limit")
    matches = KnowledgeBase(
        config.knowledge_dir, max_document_bytes=config.max_document_bytes
    ).search(payload.question)
    answer, mode = await generate_answer(
        question=payload.question,
        history=payload.history,
        matches=matches,
        settings=config,
    )
    return ChatResponse(
        answer=answer,
        mode=mode,
        sources=[
            Source(
                title=match.document.title,
                path=match.document.path,
                excerpt=match.excerpt,
                score=match.score,
            )
            for match in matches
        ],
    )
