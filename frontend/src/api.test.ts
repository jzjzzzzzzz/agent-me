import { afterEach, expect, it, vi } from "vitest";
import { ApiError, ask, loadProfile } from "./api";

afterEach(() => vi.unstubAllGlobals());

it("returns a typed grounded response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: "Grounded", mode: "extractive", sources: [] }),
    }),
  );

  await expect(ask("Question")).resolves.toEqual({
    answer: "Grounded",
    mode: "extractive",
    sources: [],
  });
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


it("validates public profile metadata", async () => {
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

  await expect(loadProfile()).resolves.toEqual({
    name: "My Agent",
    description: "My description",
    max_question_chars: 1200,
  });
});
