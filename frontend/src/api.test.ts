import { afterEach, expect, it, vi } from "vitest";
import { ApiError, ask, collaborate, loadProfile } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("returns a typed grounded response", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ answer: "Grounded", mode: "extractive", sources: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await expect(ask("Question")).resolves.toEqual({
    answer: "Grounded",
    mode: "extractive",
    sources: [],
  });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/chat",
    expect.objectContaining({ method: "POST" }),
  );
});

it("uses a safe structured server error", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ detail: "Provider configuration is incomplete.", code: "provider_config" }),
    }),
  );

  const error = await ask("Question").catch((reason: unknown) => reason);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    message: "Provider configuration is incomplete.",
    status: 503,
    code: "provider_config",
  });
});

it("rejects malformed success payloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: "Missing mode and sources" }),
    }),
  );

  await expect(ask("Question")).rejects.toMatchObject({
    message: "Server returned an invalid response.",
    code: "invalid_response",
  });
});


it("returns a typed multi-agent collaboration trace", async () => {
  const payload = {
    run_id: `run_${"a".repeat(32)}`,
    workflow: "planner-researcher-critic-writer",
    mode: "multi-agent-local",
    answer: "Grounded collaboration answer",
    grounded: true,
    sources: [],
    trace: ["planner", "researcher", "critic", "writer"].map((agent, index) => ({
      sequence: index + 1,
      agent,
      outcome: "completed",
      summary: `${agent} completed`,
      metrics: { artifact_count: 1 },
    })),
  };
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload });
  vi.stubGlobal("fetch", fetchMock);

  await expect(collaborate("Question")).resolves.toEqual(payload);
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/collaborate"),
    expect.objectContaining({ body: JSON.stringify({ question: "Question" }) }),
  );
});

it("rejects malformed multi-agent traces", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ mode: "multi-agent-local", trace: [] }),
    }),
  );

  await expect(collaborate("Question")).rejects.toMatchObject({
    message: "Server returned an invalid collaboration trace.",
    code: "invalid_trace",
  });
});


it("validates public profile metadata", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "My Agent",
        description: "My description",
        max_question_chars: 1200,
        external_provider_enabled: true,
      }),
    }),
  );

  await expect(loadProfile()).resolves.toEqual({
    name: "My Agent",
    description: "My description",
    max_question_chars: 1200,
    external_provider_enabled: true,
  });
});

it("rejects a profile without an explicit provider disclosure flag", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "My Agent",
        description: "My description",
        max_question_chars: 1200,
      }),
    }),
  );

  await expect(loadProfile()).rejects.toMatchObject({ code: "invalid_profile" });
});
