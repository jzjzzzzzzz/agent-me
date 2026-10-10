import { test, expect, get, post, unlock, layoutScreenshot, PREFIX } from "./fixtures";
import fixture from "../src/__fixtures__/migration.json" with { type: "json" };
import type { Locator, Page } from "@playwright/test";

async function open(page: Page) {
  await unlock(page); await page.getByRole("button", { name: "Review migration & audit", exact: true }).click();
  const pane = page.getByRole("region", { name: "Snapshot migration & audit", exact: true });
  await expect(pane.getByLabel("Choose private snapshot JSON", { exact: true })).toBeEnabled();
  return pane;
}
async function load(pane: Locator, body = JSON.stringify(fixture.snapshot)) {
  await pane.getByLabel("Choose private snapshot JSON", { exact: true }).setInputFiles({ name: "fictional-private-snapshot.json", mimeType: "application/json", buffer: Buffer.from(body) });
  await expect(pane.getByRole("button", { name: "Preview snapshot import", exact: true })).toBeEnabled();
}
async function review(pane: Locator) {
  await pane.getByRole("button", { name: "Preview snapshot import", exact: true }).click();
  const dialog = pane.getByRole("alertdialog", { name: "Reviewed snapshot import", exact: true });
  await expect(dialog).toBeVisible(); return dialog;
}
const consent = (dialog: Locator) => dialog.getByRole("checkbox").check();

test("owner imports a reviewed private file, preserves data/binding, disables authority, inspects redacted audit and explicitly exports", async ({ page, ownerApi }, info) => {
  const destination = await get(ownerApi, "/portability/state");
  const pane = await open(page); await load(pane); const dialog = await review(pane);
  await expect(dialog).toContainText(destination.owner_id); await expect(dialog).toContainText(fixture.snapshot.owner_id);
  await expect(dialog).toContainText("tool_permissions:"); await expect(dialog).toContainText("inert archives");
  await expect(pane).not.toContainText("Fictional migration payload not rendered"); expect(await get(ownerApi, "/entries")).toEqual([]);
  await expect(dialog.getByRole("button", { name: "Import exact reviewed snapshot", exact: true })).toBeDisabled();
  await dialog.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "migration-authority-review");
  await consent(dialog); await dialog.getByRole("button", { name: "Import exact reviewed snapshot", exact: true }).click();
  await expect(pane.getByRole("status")).toContainText("Reviewed snapshot imported");
  await expect(pane.getByLabel("Choose private snapshot JSON", { exact: true })).toBeDisabled();
  const imported = await get(ownerApi, "/identity/owner");
  expect(imported).toEqual({ owner_id: fixture.snapshot.owner_id, entity_id: fixture.snapshot.owner_entity_id });
  expect((await get(ownerApi, "/entries"))[0]).toMatchObject({ content: "Fictional migration owner", status: "confirmed" });
  const source = (await get(ownerApi, "/learning/sources"))[0]; expect(source.approved).toBe(false); expect(source.revision).toBe(fixture.snapshot.sources[0].revision + 1);
  expect((await get(ownerApi, "/tools/permissions")).every((p: { enabled: boolean }) => !p.enabled)).toBe(true);
  expect((await get(ownerApi, "/disclosure/policy")).policy.enabled).toBe(false); expect(await get(ownerApi, "/actions")).toEqual([]);
  const archives = await get(ownerApi, "/portability/archives"); expect(archives).toHaveLength(1); expect(archives[0].authority.action_plans).toHaveLength(1);
  expect((await get(ownerApi, "/notes"))[0].content).toBe("Fictional migration payload not rendered <img src=x>");
  await pane.getByRole("combobox", { name: "Audit event limit", exact: true }).selectOption("500");
  await pane.getByRole("button", { name: "Reload audit events", exact: true }).click();
  await expect(pane.getByRole("region", { name: "Operational audit", exact: true })).toContainText("portability.import");
  await expect(pane).not.toContainText("Fictional migration payload not rendered"); expect(await pane.locator("img").count()).toBe(0);
  const downloadPromise = page.waitForEvent("download"); await pane.getByRole("button", { name: "Download private snapshot", exact: true }).click();
  const download = await downloadPromise; expect(download.suggestedFilename()).toBe("private-twin-export.json");
  const stream = await download.createReadStream(); if (!stream) throw new Error("Fixture download stream missing");
  let body = ""; for await (const chunk of stream) body += chunk.toString();
  const exported = JSON.parse(body); expect(exported.owner_id).toBe(fixture.snapshot.owner_id); expect(exported.notes[0].content).toContain("Fictional migration payload");
  expect(exported.tool_permissions).toEqual([]); expect(exported.disclosure_policy.policy.enabled).toBe(false);
  await page.getByRole("button", { name: "Lock", exact: true }).click(); await expect(pane).toHaveCount(0);
});

test("file replacement rejects ambiguous JSON locally and purge/reset invalidates a previously reviewed destination", async ({ page, ownerApi, expectedHttpErrors }) => {
  const pane = await open(page); await load(pane); let dialog = await review(pane); await consent(dialog);
  await pane.getByLabel("Choose private snapshot JSON", { exact: true }).setInputFiles({ name: "fictional-invalid.json", mimeType: "application/json", buffer: Buffer.from('{"version":8,"owner_id":"a","owner_id":"b"}') });
  await expect(dialog).toHaveCount(0); await expect(pane.getByRole("alert")).toContainText("duplicate keys");
  await expect(pane.getByRole("button", { name: "Preview snapshot import", exact: true })).toBeDisabled(); expect(await get(ownerApi, "/entries")).toEqual([]);
  await load(pane); dialog = await review(pane); await expect(dialog.getByRole("checkbox")).not.toBeChecked();
  const before = await get(ownerApi, "/identity/owner"); await post(ownerApi, "/workspace/purge", { expected_owner_id: before.owner_id, confirmation: "erase-personal-workspace" });
  expectedHttpErrors.add(`409:${PREFIX}/portability/import`);
  await consent(dialog); await dialog.getByRole("button", { name: "Import exact reviewed snapshot", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Refresh"); expect(await get(ownerApi, "/entries")).toEqual([]);
  expect((await get(ownerApi, "/identity/owner")).owner_id).not.toBe(fixture.snapshot.owner_id);
  await page.getByRole("button", { name: "Refresh workbench", exact: true }).click();
  await expect(pane.getByRole("button", { name: "Preview snapshot import", exact: true })).toBeEnabled();
  dialog = await review(pane); await expect(dialog.getByRole("checkbox")).not.toBeChecked();
  await page.keyboard.press("Escape"); await expect(dialog).toHaveCount(0);
  await expect(pane.getByRole("button", { name: "Preview snapshot import", exact: true })).toBeFocused();
});
