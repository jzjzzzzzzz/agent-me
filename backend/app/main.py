from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .knowledge import KnowledgeBase
from .provider import generate_answer
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/ready", responses={503: {"description": "No knowledge documents are loaded"}})
async def ready(
    config: Settings = Depends(get_settings),
) -> JSONResponse:
    documents = KnowledgeBase(config.knowledge_dir).documents()
    content: dict[str, object] = {
        "status": "ready" if documents else "not_ready",
        "knowledge_documents": len(documents),
    }
    return JSONResponse(status_code=200 if documents else 503, content=content)


@app.get("/api/v1/profile", response_model=ProfileResponse)
async def profile(config: Settings = Depends(get_settings)) -> ProfileResponse:
    return ProfileResponse(name=config.app_name, description=config.app_description)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, config: Settings = Depends(get_settings)) -> ChatResponse:
    if len(payload.question) > config.max_question_chars:
        raise HTTPException(status_code=413, detail="question exceeds configured limit")
    matches = KnowledgeBase(config.knowledge_dir).search(payload.question)
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
