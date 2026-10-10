import { afterEach, describe, expect, it, vi } from "vitest";
import { answerFixture, historyFixture, memoryFixture, originFixture, runFixture, sourceFixture } from "./__fixtures__/review";
import { createPersonalClient, ingestionWithinLimits, PersonalApiError } from "./personalApi";

const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => vi.unstubAllGlobals());
const client = () => createPersonalClient("synthetic-token", new AbortController().signal);

it("loads authenticated no-store arrays without leaking the token into the URL", async () => {
  const fetcher = vi.fn(async (url: string) => response(
    url.endsWith("/learning/sources") ? [sourceFixture] : url.includes("/entries?") ? [memoryFixture]
      : url.endsWith("/learning/runs") ? [runFixture] : [],
  ));
  vi.stubGlobal("fetch", fetcher);
  const loaded = await client().load();
  expect(loaded.memories).toEqual([memoryFixture]);
  expect(loaded.sources).toEqual([sourceFixture]);
  expect(fetcher).toHaveBeenCalledTimes(4);
  for (const [url, options] of fetcher.mock.calls as unknown as [string, RequestInit][]) {
    expect(url).not.toContain("synthetic-token");
    expect(options).toMatchObject({ method: "GET", cache: "no-store", headers: { Authorization: "Bearer synthetic-token" } });
    expect(options.signal).toBeInstanceOf(AbortSignal);
  }
});

it("binds source approval, ingestion, confirmation, edits and deletion to reviewed revisions", async () => {
  const fetcher = vi.fn(async (url: string) => response(
    url.endsWith("/review") ? { ...sourceFixture, approved: true, revision: 2 } : url.endsWith("/ingest") ? runFixture
      : url.endsWith("/delete") ? { deleted: true } : { status: "confirmed", revision: 2 },
  ));
  vi.stubGlobal("fetch", fetcher);
  const api = client();
  await api.reviewSource(sourceFixture);
  await api.ingest({ ...sourceFixture, revision: 2 }, "fact identity.name: Alex Example", "fields");
  await api.confirm(memoryFixture, { "memory-old": 3 });
  await api.edit(memoryFixture, "River Example");
  await api.remove(memoryFixture);
  const bodies = (fetcher.mock.calls as unknown as [string, RequestInit][]).map(([, options]) => JSON.parse(options.body as string));
  expect(bodies).toEqual([
    { approved: true, expected_revision: 1 },
    { content: "fact identity.name: Alex Example", mode: "fields", expected_source_revision: 2 },
    { expected_revision: 1, replace_ids: ["memory-old"], replace_revisions: { "memory-old": 3 } },
    { kind: "fact", key: "identity.name", content: "River Example", expected_revision: 1 },
    { expected_revision: 1 },
  ]);
});

it("keeps private questions on the atomic local ask endpoint", async () => {
  const fetcher = vi.fn(async () => response(answerFixture));
  vi.stubGlobal("fetch", fetcher);
  expect(await client().ask("What is my name?", false)).toEqual(answerFixture);
  expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/personal\/ask$/), expect.objectContaining({
    body: JSON.stringify({ question: "What is my name?", allow_sensitive: false }),
  }));
});

it("parses exact conflict revisions instead of treating arbitrary server objects as approval", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ detail: {
    message: "Confirm replacement", conflict_ids: ["old"], conflict_revisions: { old: 3 },
  } }, 409)));
  await expect(client().confirm(memoryFixture)).rejects.toMatchObject({ status: 409, kind: "stale", conflictRevisions: { old: 3 } });
});

it.each([
  { conflict_ids: ["old"], conflict_revisions: { old: "3" } },
  { conflict_ids: ["other"], conflict_revisions: { old: 3 } },
  { conflict_ids: ["old", "old"], conflict_revisions: { old: 3 } },
  { conflict_ids: ["old"], conflict_revisions: null },
])("rejects malformed conflict preconditions %j", async detail => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ detail }, 409)));
  await expect(client().confirm(memoryFixture)).rejects.toMatchObject({ conflictRevisions: null });
});

it.each([
  { ...memoryFixture, revision: 0 }, { ...memoryFixture, confidence: 1.1 },
  { ...memoryFixture, status: "accepted" }, { ...memoryFixture, valid_from: "yesterday" },
  { ...memoryFixture, content: {} }, { ...memoryFixture, sensitivity: "secret" },
])("rejects invalid memory response %j", async memory => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.includes("/entries?") ? [memory] : [])));
  await expect(client().load()).rejects.toMatchObject({ kind: "invalid" });
});

it.each([
  { ...sourceFixture, approved: "true" }, { ...sourceFixture, revision: false },
  { ...sourceFixture, name: "" }, { ...sourceFixture, kind: "url" },
])("rejects invalid source response %j", async source => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/learning/sources") ? [source] : [])));
  await expect(client().load()).rejects.toMatchObject({ kind: "invalid" });
});

it.each([
  { ...runFixture, status: "success" }, { ...runFixture, document_hash: "invalid" },
  { ...runFixture, trace: [{ stage: "storage", outcome: "completed", count: -1 }] },
  { ...runFixture, items: [{ index: 0, outcome: "confirmed", memory_id: null, conflict_ids: [] }] },
])("rejects invalid run response %j", async run => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/learning/runs") ? [run] : [])));
  await expect(client().load()).rejects.toMatchObject({ kind: "invalid" });
});

it.each([
  { ...answerFixture, mode: "openai-compatible" },
  { ...answerFixture, evidence: [{ ...answerFixture.evidence[0], score: 1.1 }] },
  { ...answerFixture, evidence: [{ ...answerFixture.evidence[0], purpose: "instruction" }] },
])("rejects invalid answer response %j", async answer => {
  vi.stubGlobal("fetch", vi.fn(async () => response(answer)));
  await expect(client().ask("question", false)).rejects.toMatchObject({ kind: "invalid" });
});

it("inspects history and origins only for the selected record", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/history") ? historyFixture : [originFixture])));
  expect(await client().inspect(memoryFixture)).toEqual({ memory: memoryFixture, history: historyFixture, origins: [originFixture] });
});

it("blocks provenance from another memory and stale history", async () => {
  const fetcher = vi.fn(async (url: string) => response(url.endsWith("/history") ? historyFixture : [{ ...originFixture, memory_id: "wrong-memory" }]));
  vi.stubGlobal("fetch", fetcher);
  await expect(client().inspect(memoryFixture)).rejects.toMatchObject({ kind: "invalid" });
  fetcher.mockImplementation(async (url: string) => response(url.endsWith("/history") ? [{ ...historyFixture[0], revision: 2 }] : []));
  await expect(client().inspect(memoryFixture)).rejects.toMatchObject({ kind: "stale" });
});

it("handles non-JSON proxy failures without showing HTML", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>proxy secret</html>", { status: 502 })));
  await expect(client().ask("question", false)).rejects.toEqual(new PersonalApiError(502, "request"));
});

it("encodes opaque IDs and forwards cancellation", async () => {
  const controller = new AbortController();
  const fetcher = vi.fn(async () => response({ status: "confirmed", revision: 2 }));
  vi.stubGlobal("fetch", fetcher);
  await createPersonalClient("synthetic", controller.signal).confirm({ ...memoryFixture, id: "id/part?x" });
  expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("id%2Fpart%3Fx/confirm"), expect.objectContaining({ signal: controller.signal }));
});

describe("ingestion size limits", () => {
  it("counts Unicode codepoints and UTF-8 bytes independently", () => {
    expect(ingestionWithinLimits("a".repeat(80_000))).toBe(true);
    expect(ingestionWithinLimits("a".repeat(80_001))).toBe(false);
    expect(ingestionWithinLimits("中".repeat(66_666))).toBe(true);
    expect(ingestionWithinLimits("中".repeat(66_667))).toBe(false);
    expect(ingestionWithinLimits("😀".repeat(50_000))).toBe(true);
    expect(ingestionWithinLimits("😀".repeat(50_001))).toBe(false);
  });
});
