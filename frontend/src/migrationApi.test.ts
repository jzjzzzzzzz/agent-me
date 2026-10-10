import { afterEach, expect, it, vi } from "vitest";
import raw from "./__fixtures__/migration.json";
import { isImportReceipt, isImportReview, readSnapshot, snapshotBody, snapshotFits, strictSnapshotJson, type DestinationState, type ImportReview, type RawSnapshot } from "./migrationApi";
import { createPersonalClient } from "./personalApi";
const state: DestinationState = { owner_id: raw.preview.destination_owner_id, empty: true, max_snapshot_bytes: 16 * 1024 * 1024, max_request_body_bytes: 262144 };
const snapshot: RawSnapshot = { raw: JSON.stringify(raw.snapshot), ownerId: raw.snapshot.owner_id, version: 8, bytes: JSON.stringify(raw.snapshot).length };
const file = (text: string) => ({ size: new TextEncoder().encode(text).length, arrayBuffer: async () => new TextEncoder().encode(text).buffer }) as File;
const client = () => createPersonalClient("fixture-token", new AbortController().signal);
const response = (v: unknown) => new Response(JSON.stringify(v), { status: 200 });
afterEach(() => vi.unstubAllGlobals());
it("parses real native preview/receipt authority dispositions", () => {
  expect(isImportReview(raw.preview)).toBe(true); expect(isImportReceipt(raw.receipt)).toBe(true);
  expect(isImportReview({ ...raw.preview, executable_plans_restored: true })).toBe(false);
  expect(isImportReview({ ...raw.preview, provider_permissions_restored: true })).toBe(false);
});
it.each([
  '{"owner_id":"a","owner_id":"b","version":8}', '{"owner_id":"a","version":8,"nested":{"a":1,"\\u0061":2}}',
  '{"owner_id":"a","version":8,"bad":"\\ud800"}', '{"owner_id":"a","version":8,"bad":1e1000}',
  '{"owner_id":"a","version":8,"bad":NaN}', '{"owner_id":"a","version":8,}', '[]', '\u00a0{"owner_id":"a","version":8}',
])("rejects ambiguous or invalid private JSON without token diagnostics", value => expect(() => strictSnapshotJson(value)).toThrow("invalid"));
it("handles escaped strings/braces/nested arrays and legitimate repeated keys in different objects", () => {
  const valid = JSON.stringify({ version: 8, owner_id: "fictional", objects: [{ key: '"}\\[' }, { key: "another" }] });
  expect(strictSnapshotJson(valid).version).toBe(8);
});
it("preserves original large numeric tokens through the actual upload body rather than rounding them", async () => {
  const text = '{"version":8,"owner_id":"fictional","revision":9007199254740993}';
  const parsed = await readSnapshot(file(text), state, new AbortController().signal);
  expect(snapshotBody(parsed, state.owner_id)).toContain('"revision":9007199254740993');
  expect(snapshotBody(parsed, state.owner_id)).not.toContain('"revision":9007199254740992');
});
it("bounds before allocation and checks the exact wrapped application body with Unicode bytes", async () => {
  const read = vi.fn(); const oversized = { size: state.max_snapshot_bytes + 1, arrayBuffer: read } as unknown as File;
  await expect(readSnapshot(oversized, state, new AbortController().signal)).rejects.toMatchObject({ kind: "tooLarge" }); expect(read).not.toHaveBeenCalled();
  const text = '{"version":8,"owner_id":"fictional","text":"林"}';
  const loaded = await readSnapshot(file(text), state, new AbortController().signal);
  const size = new TextEncoder().encode(snapshotBody(loaded, state.owner_id, "0".repeat(64))).length;
  expect(snapshotFits(loaded, { ...state, max_request_body_bytes: size })).toBe(true);
  expect(snapshotFits(loaded, { ...state, max_request_body_bytes: size - 1 })).toBe(false);
});
it("rejects invalid UTF-8 and non-JSON outer whitespace without normalizing it into accepted input", async () => {
  const bytes = new Uint8Array([0xff]);
  await expect(readSnapshot({ size: 1, arrayBuffer: async () => bytes.buffer } as File, state, new AbortController().signal)).rejects.toMatchObject({ kind: "invalid" });
  await expect(readSnapshot(file('\u00a0{"version":8,"owner_id":"fictional"}'), state, new AbortController().signal)).rejects.toMatchObject({ kind: "invalid" });
  const valid = '\ufeff \r\n{"version":8,"owner_id":"fictional"}\r\n';
  expect((await readSnapshot(file(valid), state, new AbortController().signal)).ownerId).toBe("fictional");
});
it("abandons a late file read on abort", async () => {
  const controller = new AbortController();
  const data = new TextEncoder().encode(snapshot.raw).buffer;
  const selected = { size: data.byteLength, arrayBuffer: async () => { controller.abort(); return data; } } as File;
  await expect(readSnapshot(selected, state, controller.signal)).rejects.toMatchObject({ name: "AbortError" });
});
it("sends only raw snapshot, reviewed destination and exact digest, and checks returned count/owner identity", async () => {
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    expect(options.cache).toBe("no-store"); expect(options.headers).toMatchObject({ Authorization: "Bearer fixture-token" });
    return response(url.endsWith("/preview") ? raw.preview : raw.receipt);
  });
  vi.stubGlobal("fetch", fetcher);
  const review = await client().previewImport(snapshot, state); await client().importSnapshot(snapshot, review, state);
  expect(JSON.parse(fetcher.mock.calls[1][1].body as string)).toEqual({ snapshot: raw.snapshot, expected_destination_owner_id: state.owner_id, digest: raw.preview.digest });
});
it("blocks nonempty/over-limit requests before fetch and refuses a foreign destination review", async () => {
  const fetcher = vi.fn(async () => response({ ...raw.preview, destination_owner_id: "foreign" })); vi.stubGlobal("fetch", fetcher);
  await expect(client().previewImport(snapshot, { ...state, empty: false })).rejects.toMatchObject({ kind: "stale" });
  await expect(client().previewImport(snapshot, { ...state, max_request_body_bytes: 1024 })).rejects.toMatchObject({ status: 413 }); expect(fetcher).not.toHaveBeenCalled();
  await expect(client().previewImport(snapshot, state)).rejects.toMatchObject({ kind: "invalid" });
});
it("rejects changed import receipts and foreign audit metadata", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...raw.receipt, counts: { entries: 99 } })));
  await expect(client().importSnapshot(snapshot, raw.preview as ImportReview, state)).rejects.toMatchObject({ kind: "invalid" });
  vi.stubGlobal("fetch", vi.fn(async () => response(raw.snapshot.audit_events.map(row => ({ ...row, owner_id: "foreign" })))));
  await expect(client().inspectAudit(state, 100)).rejects.toMatchObject({ kind: "stale" });
});
it("exports original response bytes without reserializing large revision tokens", async () => {
  const exportRaw = `{"version":8,"owner_id":${JSON.stringify(state.owner_id)},"large":9007199254740993}`;
  vi.stubGlobal("fetch", vi.fn(async () => new Response(exportRaw, { status: 200 })));
  expect(await client().exportSnapshot(state)).toBe(exportRaw);
});
