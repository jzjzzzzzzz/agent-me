import { afterEach, expect, it, vi } from "vitest";
import { collaborate, type CollaborationPolicy } from "./api";
import baseline from "./__fixtures__/collaboration/baseline.json";
import verified from "./__fixtures__/collaboration/verified.json";

afterEach(() => vi.unstubAllGlobals());

const contracts: [CollaborationPolicy, typeof baseline | typeof verified][] = [
  ["baseline", baseline],
  ["verified", verified],
];

it.each(contracts)("parses the shared %s response through mocked fetch", async (policy, payload) => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload });
  vi.stubGlobal("fetch", fetchMock);

  await expect(collaborate("Synthetic question", policy)).resolves.toEqual(payload);
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/collaborate",
    expect.objectContaining({
      body: JSON.stringify({ question: "Synthetic question", workflow: policy }),
    }),
  );
});

it.each(contracts)("rejects reordered stages derived from %s", async (policy, fixture) => {
  const payload = structuredClone(fixture);
  [payload.trace[0].agent, payload.trace[1].agent] =
    [payload.trace[1].agent, payload.trace[0].agent];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));

  await expect(collaborate("Synthetic question", policy)).rejects.toMatchObject({
    code: "invalid_trace",
  });
});

it.each(contracts)("rejects unsupported metrics derived from %s", async (policy, fixture) => {
  const payload = {
    ...fixture,
    trace: fixture.trace.map((stage, index) => index === 0
      ? { ...stage, metrics: { task_count: { unsupported: "nested object" } } }
      : stage),
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));

  await expect(collaborate("Synthetic question", policy)).rejects.toMatchObject({
    code: "invalid_trace",
  });
});
