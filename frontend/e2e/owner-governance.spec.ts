import { test, expect, get, post, unlock, layoutScreenshot, PREFIX } from "./fixtures";
import type { Locator, Page } from "@playwright/test";

async function open(page: Page) {
  await unlock(page); await page.getByRole("button", { name: "Manage learning governance", exact: true }).click();
  const pane = page.getByRole("region", { name: "Learning governance & memory maintenance", exact: true });
  await expect(pane.getByRole("button", { name: "Create retention preview", exact: true })).toBeEnabled();
  return pane;
}
async function policy(pane: Locator, name: string, value: unknown) {
  await pane.getByRole("textbox", { name: `Policy JSON: ${name}`, exact: true }).fill(JSON.stringify(value));
  await pane.getByRole("button", { name: `Review policy change: ${name}`, exact: true }).click();
  const dialog = pane.getByRole("alertdialog", { name: "Review policy change", exact: true });
  await expect(dialog).toContainText('"before"'); await expect(dialog).toContainText('"after"');
  await dialog.getByRole("button", { name: "Apply exact reviewed policy", exact: true }).click();
  await expect(pane.getByRole("button", { name: "Create retention preview", exact: true })).toBeEnabled();
}

test("typed policy review and exact consolidation preserve pending status and original history", async ({ page, ownerApi }, info) => {
  for (let i = 0; i < 2; i++) await post(ownerApi, "/entries", { key: "fictional.duplicate", content: "Fictional duplicate literal body" });
  const originals = await get(ownerApi, "/entries"); const controls = await get(ownerApi, "/learning/governance");
  expect(Object.values(controls.retention.policy).every(value => value === null)).toBe(true);
  const pane = await open(page);
  await policy(pane, "Learning policy", { ...controls.learning.policy, source_kinds: [], labels: [], max_candidates: 1 });
  expect((await get(ownerApi, "/learning/governance")).learning.policy.labels).toEqual([]);
  await pane.getByLabel("Key prefix filter", { exact: true }).fill("fictional.");
  await pane.getByRole("button", { name: "Create exact consolidation preview", exact: true }).click();
  const reviewButton = pane.getByRole("button", { name: /^Review exact members:/ }); await expect(reviewButton).toBeEnabled();
  expect(await get(ownerApi, "/entries")).toHaveLength(2); await reviewButton.click();
  const dialog = pane.getByRole("alertdialog", { name: "Review exact members", exact: true });
  await expect(dialog).toContainText(originals[0].id); await expect(dialog).toContainText(originals[1].id);
  await expect(dialog.getByRole("button", { name: "Apply exact consolidation", exact: true })).toBeDisabled();
  await dialog.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "governance-exact-pending-members");
  await dialog.getByRole("checkbox").check(); await dialog.getByRole("button", { name: "Apply exact consolidation", exact: true }).click();
  await expect(pane.getByRole("status")).toContainText("Reviewed plan applied");
  const rows = await get(ownerApi, "/entries?include_superseded=true");
  expect(rows.map((row: { status: string }) => row.status).sort()).toEqual(["pending", "superseded"]);
  const snapshot = await get(ownerApi, "/export");
  for (const original of originals) expect(snapshot.revisions.some((row: { id: string; revision: number }) => row.id === original.id && row.revision === 1)).toBe(true);
});

test("retention review binds real cascades and rejects a new relationship without a memory revision change", async ({ page, ownerApi, expectedHttpErrors }, info) => {
  const item = await post(ownerApi, "/entries", { key: "fictional.expired", content: "Fictional expired body", valid_until: new Date(Date.now() - 4 * 86400000).toISOString() });
  const confirmed = await post(ownerApi, `/entries/${item.id}/confirm`, { expected_revision: 1 });
  const controls = await get(ownerApi, "/learning/governance"); const pane = await open(page);
  await policy(pane, "Retention policy", { ...controls.retention.policy, expired_days: 1 });
  await pane.getByRole("button", { name: "Create retention preview", exact: true }).click();
  const button = pane.getByRole("button", { name: /^Review retention scope:/ }); await expect(button).toBeEnabled();
  await button.click(); let dialog = pane.getByRole("alertdialog", { name: "Reviewed retention scope", exact: true });
  await expect(dialog).toContainText("entries: 1"); await expect(dialog).toContainText("revisions: 2");
  expect(await get(ownerApi, "/entries")).toHaveLength(1);
  const entities = [];
  for (const kind of ["person", "project"]) {
    const entity = await post(ownerApi, "/identity/entities", { kind, name: `Fictional governance ${kind}` });
    entities.push(await post(ownerApi, `/identity/entities/${entity.id}/confirm`, { expected_revision: 1 }));
  }
  await post(ownerApi, "/identity/relationships", { from_entity_id: entities[0].id, to_entity_id: entities[1].id, predicate: "works_on", evidence_id: item.id });
  expect((await get(ownerApi, "/entries"))[0].revision).toBe(confirmed.revision);
  const plan = (await get(ownerApi, "/learning/governance")).retention_plans[0];
  expectedHttpErrors.add(`409:${PREFIX}/retention/plans/${plan.id}/apply-reviewed`);
  await dialog.getByRole("checkbox").check(); await dialog.getByRole("button", { name: "Apply reviewed retention", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Refresh"); expect(await get(ownerApi, "/entries")).toHaveLength(1);
  await page.getByRole("button", { name: "Refresh workbench", exact: true }).click(); await expect(button).toBeEnabled();
  await button.click(); dialog = pane.getByRole("alertdialog", { name: "Reviewed retention scope", exact: true });
  await expect(dialog).toContainText("relationships: 1"); await expect(dialog.getByRole("checkbox")).not.toBeChecked();
  await dialog.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "governance-retention-cascade");
  await dialog.getByRole("checkbox").check(); await dialog.getByRole("button", { name: "Apply reviewed retention", exact: true }).click();
  await expect(pane.getByRole("status")).toContainText("Reviewed plan applied");
  expect(await get(ownerApi, "/entries")).toEqual([]); expect(await get(ownerApi, "/identity/relationships")).toEqual([]);
  expect(await get(ownerApi, "/identity/entities")).toHaveLength(2);
});
