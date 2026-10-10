import { afterEach, expect, it, vi } from "vitest";
import { entityFixture, projectFixture, relationshipFixture, identityDeleteFixture, memoryFixture } from "./__fixtures__/review";
import { createPersonalClient } from "./personalApi";

const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const api = () => createPersonalClient("synthetic-token", new AbortController().signal);
afterEach(() => vi.unstubAllGlobals());

it("binds relationship proposals to exactly the reviewed evidence and endpoint revisions", async () => {
  const fetcher = vi.fn(async () => response(relationshipFixture)); vi.stubGlobal("fetch", fetcher);
  await api().createRelationship(entityFixture, projectFixture, { ...memoryFixture, revision: 2 }, "works_on", "private");
  await api().confirmRelationship(relationshipFixture, entityFixture, projectFixture);
  const bodies = (fetcher.mock.calls as unknown as [string, RequestInit][]).map(([, options]) => JSON.parse(options.body as string));
  expect(bodies[0]).toEqual({ from_entity_id: "entity-one", to_entity_id: "project-one", evidence_id: "memory-one",
    predicate: "works_on", sensitivity: "private", expected_evidence_revision: 2, expected_entity_revisions: { "entity-one": 2, "project-one": 2 } });
  expect(bodies[1]).toEqual({ expected_revision: 1, expected_entity_revisions: { "entity-one": 2, "project-one": 2 } });
});

it("reviews both the existing owner binding and the selected person revision", async () => {
  const fetcher = vi.fn(async () => response({ owner_id: "synthetic-owner", entity_id: "entity-one" }));
  vi.stubGlobal("fetch", fetcher);
  await api().bindOwner({ owner_id: "synthetic-owner", entity_id: null }, entityFixture);
  expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/identity\/owner$/), expect.objectContaining({
    body: JSON.stringify({ entity_id: "entity-one", expected_owner_entity_id: null, expected_entity_revision: 2 }),
  }));
  fetcher.mockImplementation(async () => response({ owner_id: "synthetic-owner", entity_id: null }));
  await api().bindOwner({ owner_id: "synthetic-owner", entity_id: "entity-one" }, null);
  expect((fetcher.mock.calls.at(-1) as unknown as [string, RequestInit])[1].body).toBe(JSON.stringify({ entity_id: null, expected_owner_entity_id: "entity-one" }));
});

it("passes entity revisions on edits and confirmation without client-authored lifecycle metadata", async () => {
  const fetcher = vi.fn(async () => response(entityFixture)); vi.stubGlobal("fetch", fetcher);
  const input = { kind: entityFixture.kind, name: "River Example", aliases: ["River"], sensitivity: entityFixture.sensitivity };
  await api().createEntity(input, true); await api().editEntity(entityFixture, input); await api().confirmEntity(entityFixture);
  const bodies = (fetcher.mock.calls as unknown as [string, RequestInit][]).map(([, options]) => JSON.parse(options.body as string));
  expect(bodies).toEqual([{ ...input, distinct: true }, { ...input, expected_revision: 2 }, { expected_revision: 2 }]);
});

it("inspects exact revision histories and rejects records from another entity", async () => {
  const fetcher = vi.fn(async () => response([{ ...entityFixture, change: "confirmed" }])); vi.stubGlobal("fetch", fetcher);
  expect(await api().entityHistory(entityFixture)).toHaveLength(1);
  fetcher.mockImplementation(async () => response([{ ...entityFixture, id: "wrong", change: "confirmed" }]));
  await expect(api().entityHistory(entityFixture)).rejects.toMatchObject({ kind: "invalid" });
  fetcher.mockImplementation(async () => response([{ ...entityFixture, revision: 3, change: "edited" }]));
  await expect(api().entityHistory(entityFixture)).rejects.toMatchObject({ kind: "stale" });
});

it("previews deletion without mutation and posts the exact digest/revision only after review", async () => {
  const fetcher = vi.fn(async (url: string) => response(url.endsWith("delete-preview") ? identityDeleteFixture : { deleted: true }));
  vi.stubGlobal("fetch", fetcher); const client = api();
  const preview = await client.previewIdentityDelete(entityFixture, "entity");
  expect((fetcher.mock.calls[0] as unknown as [string, RequestInit])[1].method).toBe("GET");
  await client.deleteIdentity(preview);
  expect(fetcher).toHaveBeenLastCalledWith(expect.stringMatching(/\/entities\/entity-one\/delete$/), expect.objectContaining({
    body: JSON.stringify({ expected_revision: 2, digest: "b".repeat(64) }),
  }));
});

it.each([
  { ...identityDeleteFixture, record: { ...entityFixture, id: "other" } },
  { ...identityDeleteFixture, digest: "invalid" },
  { ...identityDeleteFixture, memories: [{ ...memoryFixture, revision: "1" }] },
  { ...identityDeleteFixture, origin_count: -1 },
  { ...identityDeleteFixture, kind: "relationship", record: relationshipFixture },
])("rejects invalid deletion scopes %j", async preview => {
  vi.stubGlobal("fetch", vi.fn(async () => response(preview)));
  await expect(api().previewIdentityDelete(entityFixture, "entity")).rejects.toMatchObject({ kind: "invalid" });
});

it("rejects a preview of a newer entity revision instead of approving unseen identity changes", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...identityDeleteFixture, record: { ...entityFixture, revision: 3 } })));
  await expect(api().previewIdentityDelete(entityFixture, "entity")).rejects.toMatchObject({ kind: "stale" });
});

it.each([
  { status: "resolved", matches: [entityFixture, projectFixture] },
  { status: "ambiguous", matches: [entityFixture] },
  { status: "unknown", matches: [entityFixture] },
  { status: "resolved", matches: [{ ...entityFixture, status: "pending" }] },
  { status: "resolved", matches: [{ ...entityFixture, sensitivity: "sensitive" }] },
])("fails closed on incoherent alias or unselected sensitive matches %j", async result => {
  vi.stubGlobal("fetch", vi.fn(async () => response(result)));
  await expect(api().resolve("Alex", null, false)).rejects.toMatchObject({ kind: "invalid" });
});

it("exposes ambiguity as multiple explicit IDs, never an implicit merge", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ status: "ambiguous", matches: [entityFixture, { ...entityFixture, id: "other" }] })));
  const result = await api().resolve("Alex", "person", false);
  expect(result.status).toBe("ambiguous"); expect(result.matches.map(item => item.id)).toEqual(["entity-one", "other"]);
});

it.each([
  { entities: [projectFixture], relationships: [] },
  { entities: [entityFixture, projectFixture], relationships: [relationshipFixture] },
  { entities: [{ ...entityFixture, sensitivity: "sensitive" }], relationships: [] },
  { entities: [{ ...entityFixture, owner_id: "other-owner" }], relationships: [] },
])("rejects wrong-subject, pending or unselected sensitive current graphs %j", async result => {
  vi.stubGlobal("fetch", vi.fn(async () => response(result)));
  await expect(api().neighbours(entityFixture, false)).rejects.toMatchObject({ kind: "invalid" });
});

it("loads owner/relationships lazily and rejects mixed ownership", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/owner")
    ? { owner_id: "synthetic-owner", entity_id: "entity-one" } : [{ ...relationshipFixture, owner_id: "different-owner" }])));
  await expect(api().loadIdentity()).rejects.toMatchObject({ kind: "invalid" });
});
