import { test, expect, get, post, unlock, layoutScreenshot, PREFIX } from "./fixtures";
import type { APIRequestContext, Locator } from "@playwright/test";

async function createOutput(api: APIRequestContext, tool: string, argumentsValue: unknown, key: string, sourceIds: string[] = []) {
  const plan = await post(api, "/actions", { tool, arguments: argumentsValue, idempotency_key: key, source_ids: sourceIds });
  await post(api, `/actions/${plan.id}/approve`, { expected_revision: plan.revision, digest: plan.digest });
  return post(api, `/actions/${plan.id}/execute`, {});
}
async function choose(pane: Locator, kind: string, id: string) {
  await pane.getByRole("combobox", { name: "Copy type", exact: true }).selectOption(kind);
  await pane.getByRole("combobox", { name: "Stored copy", exact: true }).selectOption(id);
}
async function preview(pane: Locator) {
  await pane.getByRole("button", { name: "Preview exact erasure scope", exact: true }).click();
  return pane.getByRole("alertdialog", { name: "Reviewed erasure scope", exact: true });
}
async function confirm(dialog: Locator) {
  await dialog.getByRole("checkbox").check();
  await dialog.getByRole("button", { name: "Erase exact reviewed scope", exact: true }).click();
}

test("output erasure reviews every associated plan, rejects a new link, and does not guess independent text copies", async ({ page, ownerApi, expectedHttpErrors }, info) => {
  for (const tool of ["tasks.create", "tasks.complete", "notes.create"]) await post(ownerApi, `/tools/permissions/${tool}`, { enabled: true, expected_revision: 1 });
  const original = await createOutput(ownerApi, "tasks.create", { title: "Fictional erasure task", description: "Fictional private body shared but not semantically erased" }, "erase-task");
  const independent = await createOutput(ownerApi, "notes.create", { title: "Fictional unlinked copy", content: "Fictional private body shared but not semantically erased" }, "unlinked-copy");
  await unlock(page); await page.getByRole("button", { name: "Review stored-data erasure", exact: true }).click();
  const pane = page.getByRole("region", { name: "Stored-data erasure review", exact: true });
  await choose(pane, "task", original.result.id); let dialog = await preview(pane);
  await expect(dialog.getByRole("button", { name: "Erase exact reviewed scope", exact: true })).toBeDisabled();
  await expect(dialog).not.toContainText("Fictional private body shared but not semantically erased");
  const later = await post(ownerApi, "/actions", { tool: "tasks.complete", arguments: { task_id: original.result.id, expected_revision: 1 }, idempotency_key: "later-plan-link" });
  expectedHttpErrors.add(`409:${PREFIX}/owner/erasure/apply`);
  await confirm(dialog); await expect(page.getByRole("alert")).toContainText("Refresh");
  expect(await get(ownerApi, "/tasks")).toHaveLength(1); expect(await get(ownerApi, "/actions")).toHaveLength(3);
  await page.getByRole("button", { name: "Refresh workbench", exact: true }).click();
  await expect(pane.getByRole("button", { name: "Preview exact erasure scope", exact: true })).toBeEnabled();
  dialog = await preview(pane);
  const removed = dialog.getByRole("region", { name: "Removed copies", exact: true });
  await expect(removed).toContainText("action_plans: 2"); await removed.getByText("Removed copies", { exact: true }).click();
  await expect(removed).toContainText(later.id); await dialog.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "erasure-cascade-scope");
  await confirm(dialog); await expect(pane.getByRole("status")).toContainText("Reviewed scope erased");
  expect(await get(ownerApi, "/tasks")).toEqual([]);
  expect((await get(ownerApi, "/notes"))[0].id).toBe(independent.result.id);
  expect((await get(ownerApi, "/actions"))[0].id).toBe(independent.id);
  await choose(pane, "note", independent.result.id); dialog = await preview(pane); await confirm(dialog);
  await expect(pane.getByRole("status")).toContainText(independent.result.id); expect(await get(ownerApi, "/notes")).toEqual([]);
  expect(await get(ownerApi, "/actions")).toEqual([]);
});

test("source forgetting covers history/restores/cross-source origins while independent note and action copies remain explicit", async ({ page, ownerApi }, info) => {
  const sources = [];
  for (const name of ["Fictional erasure source A", "Fictional erasure source B"]) {
    const s = await post(ownerApi, "/learning/sources", { kind: "document", name });
    sources.push(await post(ownerApi, `/learning/sources/${s.id}/review`, { approved: true, expected_revision: 1 }));
  }
  const content = "fact project: Fictional original source excerpt";
  const run = await post(ownerApi, `/learning/sources/${sources[0].id}/ingest`, { content, expected_source_revision: 2 });
  await post(ownerApi, `/learning/sources/${sources[1].id}/ingest`, { content, expected_source_revision: 2 });
  const memory = (await get(ownerApi, "/entries")).find((m: { id: string }) => m.id === run.items[0].memory_id);
  await post(ownerApi, `/entries/${memory.id}/confirm`, { expected_revision: memory.revision });
  await post(ownerApi, `/entries/${memory.id}/restore`, { revision: 1 });
  const entities = [];
  for (const kind of ["person", "project"]) {
    const entity = await post(ownerApi, "/identity/entities", { kind, name: `Fictional ${kind} erasure` });
    entities.push(await post(ownerApi, `/identity/entities/${entity.id}/confirm`, { expected_revision: 1 }));
  }
  const relation = await post(ownerApi, "/identity/relationships", { from_entity_id: entities[0].id, to_entity_id: entities[1].id, predicate: "works_on", evidence_id: memory.id });
  await post(ownerApi, `/identity/relationships/${relation.id}/confirm`, { expected_revision: 1 });
  await post(ownerApi, "/tools/permissions/notes.create", { enabled: true, expected_revision: 1 });
  const note = await createOutput(ownerApi, "notes.create", { title: "Fictional independent source note", content: "Fictional original source excerpt" }, "source-copy", [memory.id]);
  await unlock(page);
  await page.getByRole("combobox", { name: "Source", exact: true }).selectOption(sources[0].id);
  await page.getByLabel("Source content", { exact: true }).fill("Fictional volatile source draft");
  await page.getByRole("button", { name: "Review stored-data erasure", exact: true }).click();
  const pane = page.getByRole("region", { name: "Stored-data erasure review", exact: true });
  await choose(pane, "source", sources[0].id); await pane.getByLabel("Also forget derived and explicitly restored memories", { exact: true }).check();
  let dialog = await preview(pane);
  await expect(dialog.getByRole("region", { name: "Removed copies", exact: true })).toContainText("entries: 2");
  await expect(dialog.getByRole("region", { name: "Removed copies", exact: true })).toContainText("relationships: 1");
  await expect(dialog.getByRole("region", { name: "Retained linked copies", exact: true })).toContainText("notes: 1");
  await dialog.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "erasure-retained-copies");
  await confirm(dialog); await expect(pane.getByRole("status")).toContainText(sources[0].id);
  expect(await get(ownerApi, "/entries?include_superseded=true")).toEqual([]); expect(await get(ownerApi, "/identity/relationships")).toEqual([]);
  expect(await get(ownerApi, "/identity/entities")).toHaveLength(2); expect(await get(ownerApi, "/learning/sources")).toHaveLength(1);
  expect((await get(ownerApi, "/notes"))[0].id).toBe(note.result.id); expect((await get(ownerApi, "/actions"))[0].id).toBe(note.id);
  await expect(page.getByLabel("Source content", { exact: true })).toHaveValue("");
  await choose(pane, "action", note.id); dialog = await preview(pane);
  await expect(dialog.getByRole("region", { name: "Retained linked copies", exact: true })).toContainText("notes: 1");
  await confirm(dialog); await expect(pane.getByRole("status")).toContainText(note.id);
  expect(await get(ownerApi, "/actions")).toEqual([]); expect(await get(ownerApi, "/notes")).toHaveLength(1);
  await choose(pane, "note", note.result.id); dialog = await preview(pane); await confirm(dialog);
  await expect(pane.getByRole("status")).toContainText(note.result.id); expect(await get(ownerApi, "/notes")).toEqual([]);
});

test("inert import archive erasure preserves imported live outputs and leaves authority disabled", async ({ page, ownerApi }) => {
  await post(ownerApi, "/tools/permissions/notes.create", { enabled: true, expected_revision: 1 });
  await createOutput(ownerApi, "notes.create", { title: "Fictional portable note", content: "Fictional portable body" }, "portable-fixture");
  const snapshot = await get(ownerApi, "/export");
  const owner = await get(ownerApi, "/identity/owner");
  await post(ownerApi, "/workspace/purge", { expected_owner_id: owner.owner_id, confirmation: "erase-personal-workspace" });
  const previewImport = await post(ownerApi, "/portability/preview", { snapshot });
  const imported = await post(ownerApi, "/portability/import", { snapshot, digest: previewImport.digest });
  await unlock(page); await page.getByRole("button", { name: "Review stored-data erasure", exact: true }).click();
  const pane = page.getByRole("region", { name: "Stored-data erasure review", exact: true });
  await choose(pane, "archive", imported.archive_id); const dialog = await preview(pane);
  await expect(dialog.getByRole("region", { name: "Removed copies", exact: true })).toContainText("import_archives: 1");
  await confirm(dialog); await expect(pane.getByRole("status")).toContainText(imported.archive_id);
  expect(await get(ownerApi, "/portability/archives")).toEqual([]); expect(await get(ownerApi, "/notes")).toHaveLength(1);
  expect((await get(ownerApi, "/tools/permissions")).every((p: { enabled: boolean }) => !p.enabled)).toBe(true);
});
