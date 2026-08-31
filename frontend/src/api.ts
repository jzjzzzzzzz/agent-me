export type AnswerMode = "extractive" | "openai-compatible";
export type Source = { title: string; path: string; excerpt: string; score: number };
export type ChatResponse = { answer: string; mode: AnswerMode; sources: Source[] };
export type CollaborationAgent = "planner" | "researcher" | "critic" | "writer";
export type CollaborationOutcome = "completed" | "blocked";
export type CollaborationStage = {
  sequence: number;
  agent: CollaborationAgent;
  outcome: CollaborationOutcome;
  summary: string;
  metrics: Record<string, boolean | number>;
};
export type CollaborationResponse = {
  run_id: string;
  workflow: "planner-researcher-critic-writer";
  mode: "multi-agent-local";
  answer: string;
  grounded: boolean;
  sources: Source[];
  trace: CollaborationStage[];
};
export type ProfileResponse = {
  name: string;
  description: string;
  max_question_chars: number;
  external_provider_enabled: boolean;
};

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

// Use same-origin API requests by default. The development and container web
// servers proxy /api to the backend, while deployments can still opt into an
// explicit cross-origin API with VITE_API_BASE_URL.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/+$/, "");

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

function isCollaborationStage(value: unknown): value is CollaborationStage {
  if (!value || typeof value !== "object") return false;
  const stage = value as Record<string, unknown>;
  const metrics = stage.metrics;
  return (
    typeof stage.sequence === "number" &&
    Number.isInteger(stage.sequence) &&
    stage.sequence >= 1 &&
    (stage.agent === "planner" ||
      stage.agent === "researcher" ||
      stage.agent === "critic" ||
      stage.agent === "writer") &&
    (stage.outcome === "completed" || stage.outcome === "blocked") &&
    typeof stage.summary === "string" &&
    !!metrics &&
    typeof metrics === "object" &&
    !Array.isArray(metrics) &&
    Object.values(metrics).every(
      (metric) =>
        typeof metric === "boolean" || (typeof metric === "number" && Number.isFinite(metric)),
    )
  );
}

function parseProfileResponse(value: unknown): ProfileResponse {
  if (!value || typeof value !== "object") {
    throw new ApiError("Server returned an invalid profile.", 502, "invalid_profile");
  }
  const profile = value as Record<string, unknown>;
  if (
    typeof profile.name !== "string" ||
    typeof profile.description !== "string" ||
    typeof profile.max_question_chars !== "number" ||
    !Number.isInteger(profile.max_question_chars) ||
    profile.max_question_chars < 1 ||
    typeof profile.external_provider_enabled !== "boolean"
  ) {
    throw new ApiError("Server returned an invalid profile.", 502, "invalid_profile");
  }
  return profile as ProfileResponse;
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

function parseCollaborationResponse(value: unknown): CollaborationResponse {
  if (!value || typeof value !== "object") {
    throw new ApiError("Server returned an invalid collaboration trace.", 502, "invalid_trace");
  }
  const response = value as Record<string, unknown>;
  const expectedAgents: CollaborationAgent[] = ["planner", "researcher", "critic", "writer"];
  if (
    typeof response.run_id !== "string" ||
    !/^run_[0-9a-f]{32}$/.test(response.run_id) ||
    response.workflow !== "planner-researcher-critic-writer" ||
    response.mode !== "multi-agent-local" ||
    typeof response.answer !== "string" ||
    typeof response.grounded !== "boolean" ||
    !Array.isArray(response.sources) ||
    !response.sources.every(isSource) ||
    !Array.isArray(response.trace) ||
    response.trace.length !== 4 ||
    !response.trace.every(
      (stage, index) =>
        isCollaborationStage(stage) &&
        stage.sequence === index + 1 &&
        stage.agent === expectedAgents[index],
    )
  ) {
    throw new ApiError("Server returned an invalid collaboration trace.", 502, "invalid_trace");
  }
  return response as CollaborationResponse;
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

export async function collaborate(
  question: string,
  signal?: AbortSignal,
): Promise<CollaborationResponse> {
  const response = await fetch(`${API_BASE}/api/v1/collaborate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!response.ok) throw await responseError(response);
  return parseCollaborationResponse(await response.json());
}


export async function loadProfile(signal?: AbortSignal): Promise<ProfileResponse> {
  const response = await fetch(`${API_BASE}/api/v1/profile`, { signal });
  if (!response.ok) throw await responseError(response);
  return parseProfileResponse(await response.json());
}
