import { afterEach, expect, it, vi } from "vitest";
import raw from "./__fixtures__/erasure.json";
import { isErasureCatalogue, isErasurePreview, isErasureRequest, sameErasureRequest, type ErasurePreview } from "./erasureApi";
import { createPersonalClient } from "./personalApi";
const fixture = raw as unknown as { catalogue: typeof raw.catalogue } & Record<"note" | "actionOnly" | "actionOutput" | "sourceOnly" | "sourceForget", ErasurePreview>;
const client = () => createPersonalClient("fictional-token", new AbortController().signal);
const response = (v: unknown) => new Response(JSON.stringify(v), { status: 200 });
afterEach(() => vi.unstubAllGlobals());
it("accepts independently generated real native catalogue and scope variants without private bodies", () => {
  expect(isErasureCatalogue(fixture.catalogue)).toBe(true);
  for (const preview of [fixture.note, fixture.actionOnly, fixture.actionOutput, fixture.sourceOnly, fixture.sourceForget]) expect(isErasurePreview(preview)).toBe(true);
  expect(JSON.stringify(fixture)).not.toContain("Fictional private body not in preview");
});
it.each([
  { digest: "invalid" }, { removed: [] }, { target: { ...fixture.note.target, id: "other" } },
  { target: { ...fixture.note.target, table: "tasks" } }, { retained: fixture.note.removed },
  { added: fixture.note.removed }, { updated: fixture.note.removed },
  { request: { ...fixture.note.request, forget_memories: true } },
  { request: { ...fixture.note.request, expected_revision: true } },
  { removed: [fixture.note.removed[0], fixture.note.removed[0]] },
])("rejects incoherent or forged scope %j", update => expect(isErasurePreview({ ...fixture.note, ...update })).toBe(false));
it("compares exact options/ownership independent of object key order and only resolves output revision during preview", () => {
  const reordered = Object.fromEntries(Object.entries(fixture.actionOutput.request).reverse()) as typeof fixture.actionOutput.request;
  expect(sameErasureRequest(reordered, fixture.actionOutput.request)).toBe(true);
  const initial = { ...reordered, expected_output_revision: null };
  expect(isErasureRequest(initial)).toBe(true);
  expect(sameErasureRequest(initial, reordered, true)).toBe(true);
  expect(sameErasureRequest(initial, reordered)).toBe(false);
  expect(sameErasureRequest({ ...reordered, purge_output: false }, reordered)).toBe(false);
});
it("sends exact owner/target/options to preview and freezes the returned output revision plus digest for apply", async () => {
  const preview = fixture.actionOutput;
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    expect(options.cache).toBe("no-store"); expect(options.headers).toMatchObject({ Authorization: "Bearer fictional-token" });
    if (url.endsWith("/preview")) return response(preview);
    return response({ deleted: true, request: preview.request, digest: preview.digest,
      removed_counts: { action_events: 4, action_plans: 1, notes: 1 }, retained_counts: {}, forgotten_memories: 0 });
  });
  vi.stubGlobal("fetch", fetcher);
  const actual = await client().previewErasure({ ...preview.request, expected_output_revision: null });
  await client().applyErasure(actual);
  expect(JSON.parse(fetcher.mock.calls[1][1].body as string)).toEqual({ request: preview.request, digest: preview.digest });
});
it("rejects foreign-owner/different-choice preview and wrong-scope receipts", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...fixture.note, request: { ...fixture.note.request, expected_owner_id: "foreign" } })));
  await expect(client().previewErasure(fixture.note.request)).rejects.toMatchObject({ kind: "invalid" });
  vi.stubGlobal("fetch", vi.fn(async () => response({ deleted: true, request: fixture.note.request, digest: fixture.note.digest,
    removed_counts: { notes: 1 }, retained_counts: {}, forgotten_memories: 0 })));
  await expect(client().applyErasure(fixture.note)).rejects.toMatchObject({ kind: "invalid" });
});
