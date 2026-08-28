export type AnswerMode = "extractive" | "openai-compatible";
export type Source = { title: string; path: string; excerpt: string; score: number };
export type ChatResponse = { answer: string; mode: AnswerMode; sources: Source[] };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

function isSource(value: unknown): value is Source {
  if (!value || typeof value !== "object") return false;
  const source = value as Record<string, unknown>;
  return (
    typeof source.title === "string" &&
    typeof source.path === "string" &&
    typeof source.excerpt === "string" &&
    typeof source.score === "number"
  );
}

function parseChatResponse(value: unknown): ChatResponse {
  if (!value || typeof value !== "object") {
    throw new ApiError("Server returned an invalid response.", 502, "invalid_response");
  }
  const response = value as Record<string, unknown>;
  if (
    typeof response.answer !== "string" ||
    (response.mode !== "extractive" && response.mode !== "openai-compatible") ||
    !Array.isArray(response.sources) ||
    !response.sources.every(isSource)
  ) {
    throw new ApiError("Server returned an invalid response.", 502, "invalid_response");
  }
  return response as ChatResponse;
}

async function responseError(response: Response): Promise<ApiError> {
  let detail = `Request failed (${response.status})`;
  let code: string | undefined;
  try {
    const body = (await response.json()) as { detail?: unknown; code?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) detail = body.detail;
    if (typeof body.code === "string") code = body.code;
  } catch {
    // Non-JSON proxy errors use the safe status fallback above.
  }
  return new ApiError(detail, response.status, code);
}

export async function ask(question: string, signal?: AbortSignal): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok) throw await responseError(response);
  return parseChatResponse(await response.json());
}
