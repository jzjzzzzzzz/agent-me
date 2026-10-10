import { afterEach, expect, it, vi } from "vitest";
import { agencyFixture as f } from "./__fixtures__/agency";
import { isEvent, isInvocation, isNote, isPermission, isPlan, isTask, newOperationKey, type ActionPlan } from "./agencyApi";
import { createPersonalClient } from "./personalApi";

afterEach(() => vi.unstubAllGlobals());
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => createPersonalClient("fixture-owner-token", new AbortController().signal);
it("generates bounded operation keys using random bytes when randomUUID is unavailable", () => {
  let n = 0;
  const getRandomValues = vi.fn((bytes: Uint8Array) => { expect(bytes.length).toBe(16); bytes.fill(++n); return bytes; });
  vi.stubGlobal("crypto", { getRandomValues });
  expect(newOperationKey()).toBe("web-" + "01".repeat(16));
  expect(newOperationKey()).toBe("web-" + "02".repeat(16));
  expect(getRandomValues).toHaveBeenCalledTimes(2);
});
it("parses actual independently generated backend plan states, tools and output contracts", () => {
  for (const plan of [f.planned, f.approved, f.completed, f.completionPlan, f.completion, f.rolledBack, f.recommended, f.cancelled, f.notePlan, f.noteCompleted, f.failed]) {
    expect(isPlan(plan)).toBe(true); expect(isInvocation(plan.invocation)).toBe(true);
  }
  expect(f.disabled.every(isPermission)).toBe(true); expect(f.permissions.every(isPermission)).toBe(true);
  expect(f.tasks.every(isTask)).toBe(true); expect(f.notes.every(isNote)).toBe(true); expect(f.events.every(isEvent)).toBe(true);
});
it.each([
  { digest: "not-a-hash" }, { revision: true }, { attempts: 4 }, { approved_digest: null },
  { result: { table: "notes", id: "out", revision: 1, changed: true } },
  { result: { table: "tasks", id: "out", revision: 0, changed: true } },
  { undo: { command: "shell" } }, { source_revisions: {} },
  { invocation: { ...f.completed.invocation, intent: "recommend" } },
  { invocation: { ...f.completed.invocation, arguments: { ...f.completed.invocation.arguments, approved: true } } },
])("rejects malformed/composed plan authority %j", update => expect(isPlan({ ...f.completed, ...update })).toBe(false));
it("rejects unknown tools and permission scopes while preserving valid existing duplicate policy labels", () => {
  expect(isPermission({ ...f.disabled[0], enabled: "false" })).toBe(false);
  expect(isPermission({ ...f.disabled[0], scope: "shell" })).toBe(false);
  expect(isPermission({ ...f.disabled[0], labels: ["private", "private"] })).toBe(true);
  expect(isInvocation({ ...f.planned.invocation, tool: "shell.exec" })).toBe(false);
  expect(isInvocation({ ...f.planned.invocation, arguments: { ...f.planned.invocation.arguments, due_at: "2026-10-10" } })).toBe(false);
});
it("loads all four local resources with the same owner-bound abort/no-store authenticated request", async () => {
  const controller = new AbortController();
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    expect(options.signal).toBe(controller.signal); expect(options.cache).toBe("no-store");
    expect(options.headers).toMatchObject({ Authorization: "Bearer fixture-owner-token" });
    return response(url.endsWith("/permissions") ? f.disabled : url.endsWith("/actions") ? [f.planned] : url.endsWith("/tasks") ? f.tasks : url.endsWith("/notes") ? f.notes : { owner_id: f.owner_id, entity_id: null });
  });
  vi.stubGlobal("fetch", fetcher);
  const result = await createPersonalClient("fixture-owner-token", controller.signal).loadAgency();
  expect(result.owner_id).toBe(f.owner_id); expect(fetcher).toHaveBeenCalledTimes(5);
});
it.each(["permission", "plan", "task", "note"])("rejects a foreign owner in %s results", async which => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(
    url.endsWith("/permissions") ? f.disabled.map((item, i) => i === 0 && which === "permission" ? { ...item, owner_id: "foreign" } : item) :
      url.endsWith("/actions") ? [{ ...f.planned, owner_id: which === "plan" ? "foreign" : f.owner_id }] :
        url.endsWith("/tasks") ? f.tasks.map(item => ({ ...item, owner_id: which === "task" ? "foreign" : f.owner_id })) :
          url.endsWith("/notes") ? f.notes.map(item => ({ ...item, owner_id: which === "note" ? "foreign" : f.owner_id })) : { owner_id: f.owner_id, entity_id: null },
  )));
  await expect(client().loadAgency()).rejects.toMatchObject({ kind: "invalid" });
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/permissions") ? [1, 2, 3].map(id => ({ ...f.disabled[0], id: String(id) })) : url.endsWith("/owner") ? { owner_id: f.owner_id, entity_id: null } : [])));
  await expect(client().loadAgency()).rejects.toMatchObject({ kind: "invalid" });
});
it("rejects duplicate/missing tools, foreign events, stale plan reviews and wrong action receipts", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => response(url.endsWith("/permissions") ? [f.disabled[0], f.disabled[0]] : url.endsWith("/owner") ? { owner_id: f.owner_id, entity_id: null } : [])));
  await expect(client().loadAgency()).rejects.toMatchObject({ kind: "invalid" });
  vi.stubGlobal("fetch", vi.fn(async () => response(f.events.map(item => ({ ...item, plan_id: "foreign" })))));
  await expect(client().actionEvents(f.planned)).rejects.toMatchObject({ kind: "invalid" });
  vi.stubGlobal("fetch", vi.fn(async () => response([f.approved])));
  await expect(client().reviewAction(f.planned)).rejects.toMatchObject({ kind: "stale" });
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...f.completed, id: "foreign" })));
  await expect(client().act(f.approved, "execute")).rejects.toMatchObject({ kind: "invalid" });
});
it("sends only exact reviewed permission/approval metadata and POSTs an independent execution", async () => {
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    expect(options.cache).toBe("no-store");
    if (url.includes("/permissions/")) return response({ ...f.disabled[0], revision: 2, enabled: true });
    return response(url.endsWith("/approve") ? f.approved : f.completed);
  });
  vi.stubGlobal("fetch", fetcher);
  await client().configureTool(f.disabled[0], { enabled: true, labels: f.disabled[0].labels, entity_ids: null });
  await client().approveAction(f.planned); await client().act(f.approved, "execute");
  expect(JSON.parse(fetcher.mock.calls[0][1].body as string)).toEqual({ enabled: true, labels: f.disabled[0].labels, entity_ids: null, expected_revision: 1, expected_owner_id: f.owner_id });
  expect(JSON.parse(fetcher.mock.calls[1][1].body as string)).toEqual({ expected_revision: f.planned.revision, digest: f.planned.digest });
  expect(fetcher.mock.calls[2][1].method).toBe("POST");
  expect(JSON.parse(fetcher.mock.calls[2][1].body as string)).toEqual({});
});
it("refuses wrong operation/owner create receipts instead of treating them as the requested plan", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...f.planned, owner_id: "foreign" } as ActionPlan)));
  await expect(client().createAction(f.planned.invocation, f.owner_id)).rejects.toMatchObject({ kind: "invalid" });
});
