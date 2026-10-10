import { test, expect, PREFIX, FIXTURE_TOKEN, post, get, unlock, openIdentity, layoutScreenshot } from "./fixtures";

test("owner source → memory → relationship → scoped answer → deletion → lock", async ({ page, ownerApi }, info) => {
  await unlock(page);
  const identities = await openIdentity(page);
  const records = identities.getByRole("region", { name: "Identity records", exact: true });
  for (const [name, kind, alias] of [["Alex Example", "person", "Alex"], ["Orchid Demo", "project", "Orchid"]]) {
    await records.getByLabel("Entity name", { exact: true }).fill(name);
    await records.getByRole("combobox", { name: "Entity kind", exact: true }).selectOption(kind);
    await records.getByLabel("Aliases", { exact: true }).fill(alias);
    await records.getByRole("button", { name: "Propose identity", exact: true }).click();
    await records.getByRole("button", { name: new RegExp(`^Confirm: ${name},`) }).click();
    await expect(page.getByRole("button", { name: "Refresh workbench", exact: true })).toBeEnabled();
  }
  const entities = await get(ownerApi, "/identity/entities");
  const person = entities.find((item: { kind: string }) => item.kind === "person");
  const project = entities.find((item: { kind: string }) => item.kind === "project");
  await expect(records.getByText("Alex Example", { exact: true })).toBeVisible();
  await records.scrollIntoViewIfNeeded();
  await layoutScreenshot(page, info, "identity-records");

  await identities.getByRole("combobox", { name: "Workspace owner", exact: true }).selectOption(person.id);
  await identities.getByRole("button", { name: "Review owner binding", exact: true }).click();
  const ownerDialog = identities.getByRole("alertdialog", { name: "Review owner binding", exact: true });
  await expect(ownerDialog).toContainText("Alex Example");
  await ownerDialog.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refresh workbench", exact: true })).toBeEnabled();
  expect((await get(ownerApi, "/identity/owner")).entity_id).toBe(person.id);
  await page.getByRole("button", { name: "Close identity review", exact: true }).click();

  const sources = page.getByRole("region", { name: "Learning sources", exact: true });
  await sources.getByLabel("Source name", { exact: true }).fill("Fictional profile");
  await sources.getByRole("combobox", { name: "Subject", exact: true }).selectOption(person.id);
  await sources.getByRole("button", { name: "Register source", exact: true }).click();
  await sources.getByRole("button", { name: /^Approve source: Fictional profile,/ }).click();
  await sources.getByLabel("Source content", { exact: true }).fill("fact identity.name: Alex Example\nfact projects.current: Orchid Demo");
  await sources.getByRole("button", { name: "Propose memories", exact: true }).click();
  const review = page.getByRole("region", { name: "Review memories", exact: true });
  await review.getByRole("button", { name: /^Inspect provenance: identity.name,/ }).click();
  const provenance = review.getByRole("region", { name: "Inspect provenance: identity.name", exact: true });
  await expect(provenance.locator("blockquote")).toHaveText("Alex Example");
  for (const key of ["identity.name", "projects.current"]) {
    await review.getByRole("button", { name: new RegExp(`^Confirm: ${key.replaceAll(".", "\\.")},`) }).click();
    await expect(page.getByRole("button", { name: "Refresh workbench", exact: true })).toBeEnabled();
  }
  const memories = await get(ownerApi, "/entries");
  const projectMemory = memories.find((item: { key: string }) => item.key === "projects.current");
  await openIdentity(page);
  await identities.getByRole("combobox", { name: "From entity", exact: true }).selectOption(person.id);
  await identities.getByRole("combobox", { name: "To entity", exact: true }).selectOption(project.id);
  await identities.getByRole("combobox", { name: "Confirmed evidence", exact: true }).selectOption(projectMemory.id);
  await identities.getByRole("button", { name: "Propose relationship", exact: true }).click();
  await identities.getByRole("button", { name: /^Confirm: works_on,/ }).click();
  await identities.getByRole("button", { name: /^Current relationships: Alex Example,/ }).click();
  const graph = identities.getByRole("region", { name: "Current relationships", exact: true });
  await expect(graph).toContainText("works_on");
  await graph.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "current-relationships");
  expect((await get(ownerApi, "/identity/relationships"))[0].status).toBe("confirmed");
  await page.getByRole("button", { name: "Close identity review", exact: true }).click();

  const ask = page.getByRole("region", { name: "Ask with evidence", exact: true });
  await ask.getByRole("combobox", { name: "Subject", exact: true }).selectOption(person.id);
  await ask.getByLabel("Private question", { exact: true }).fill("What projects am I working on?");
  await ask.getByRole("button", { name: "Send", exact: true }).click();
  await expect(ask.getByRole("article", { name: "Grounded answer", exact: true })).toContainText("Orchid Demo");
  expect(await get(ownerApi, "/history")).toEqual([]);
  await review.getByRole("button", { name: "Confirmed (2)", exact: true }).click();
  await review.getByRole("button", { name: /^Delete: projects\.current,/ }).click();
  const deleteMemory = review.getByRole("alertdialog", { name: /^Delete: projects\.current,/ });
  await deleteMemory.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(ask.getByRole("article", { name: "Grounded answer", exact: true })).toHaveCount(0);
  await ask.getByRole("button", { name: "Send", exact: true }).click();
  await expect(ask.getByRole("article", { name: "Grounded answer", exact: true })).toContainText("unknown");
  await expect(ask.getByRole("article", { name: "Grounded answer", exact: true })).not.toContainText("Orchid Demo");
  expect(await get(ownerApi, "/identity/relationships")).toEqual([]);
  await page.getByRole("button", { name: "Lock", exact: true }).click();
  await expect(page.getByLabel("Workspace token", { exact: true })).toHaveValue("");
  await expect(page.getByRole("region", { name: "Sources & memory review", exact: true })).toHaveCount(0);
  const stored = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
  expect(stored).not.toContain(FIXTURE_TOKEN); expect(stored).not.toContain("Alex Example");
});

test("sensitive ambiguity, stale owner review and historical cascade digest", async ({ page, ownerApi, expectedHttpErrors }, info) => {
  async function person(name: string, sensitivity: string) {
    const pending = await post(ownerApi, "/identity/entities", { kind: "person", name, aliases: ["Alex"], sensitivity, distinct: true });
    return post(ownerApi, `/identity/entities/${pending.id}/confirm`, { expected_revision: pending.revision });
  }
  const a = await person("Alex Example", "private");
  const b = await person("River Example", "sensitive");
  await post(ownerApi, "/identity/owner", { entity_id: a.id, expected_owner_entity_id: null, expected_entity_revision: a.revision });
  const source = await post(ownerApi, "/learning/sources", { kind: "document", name: "Fictional historical source", entity_id: a.id });
  const approved = await post(ownerApi, `/learning/sources/${source.id}/review`, { approved: true, expected_revision: source.revision });
  await post(ownerApi, `/learning/sources/${source.id}/ingest`, { content: "fact project.role: Works on Orchid", mode: "fields", expected_source_revision: approved.revision });
  const memory = (await get(ownerApi, "/entries"))[0];
  const confirmation = await post(ownerApi, `/entries/${memory.id}/confirm`, { expected_revision: memory.revision });
  const edit = await post(ownerApi, `/entries/${memory.id}/edit`, { kind: memory.kind, key: memory.key, content: "Historical link now belongs to River", entity_id: b.id, expected_revision: confirmation.revision });
  await post(ownerApi, `/entries/${memory.id}/confirm`, { expected_revision: edit.revision });
  await unlock(page); const identities = await openIdentity(page);
  const aliasInput = identities.getByLabel("Alias to resolve", { exact: true });
  const aliasForm = identities.locator("form").filter({ has: page.getByLabel("Alias to resolve", { exact: true }) });
  await aliasInput.fill("Alex");
  await aliasForm.getByRole("button", { name: "Resolve exact alias", exact: true }).click();
  await expect(identities.getByRole("heading", { name: "Resolved", exact: true })).toBeVisible();
  await aliasForm.getByRole("checkbox", { name: "Include sensitive identities for this lookup", exact: true }).check();
  await aliasForm.getByRole("button", { name: "Resolve exact alias", exact: true }).click();
  await expect(identities.getByRole("heading", { name: "Ambiguous: choose an entity ID; no automatic merge.", exact: true })).toBeVisible();
  await expect(aliasForm.getByRole("checkbox", { name: "Include sensitive identities for this lookup", exact: true })).not.toBeChecked();
  expect(await get(ownerApi, "/identity/entities")).toHaveLength(2);

  await identities.getByRole("combobox", { name: "Workspace owner", exact: true }).selectOption(b.id);
  await identities.getByRole("button", { name: "Review owner binding", exact: true }).click();
  const binding = identities.getByRole("alertdialog", { name: "Review owner binding", exact: true });
  const updated = await post(ownerApi, `/identity/entities/${b.id}/edit`, { kind: "person", name: "Updated River", expected_revision: b.revision });
  await post(ownerApi, `/identity/entities/${b.id}/confirm`, { expected_revision: updated.revision });
  expectedHttpErrors.add(`409:${PREFIX}/identity/owner`);
  await binding.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Data changed");
  expect((await get(ownerApi, "/identity/owner")).entity_id).toBe(a.id);
  await page.getByRole("button", { name: "Refresh workbench", exact: true }).click();
  await identities.getByRole("button", { name: /^Preview deletion: Alex Example,/ }).click();
  const scope = identities.getByRole("alertdialog", { name: "Reviewed deletion scope", exact: true });
  await expect(scope).toContainText("Alex Example");
  await expect(scope).toBeFocused();
  await scope.press("Escape");
  await expect(scope).toHaveCount(0);
  await expect(identities.getByRole("button", { name: /^Preview deletion: Alex Example,/ })).toBeFocused();
  await identities.getByRole("button", { name: /^Preview deletion: Alex Example,/ }).press("Enter");
  await expect(scope).toContainText("Historical link now belongs to River");
  await expect(scope).toContainText("Fictional historical source");
  await scope.scrollIntoViewIfNeeded(); await layoutScreenshot(page, info, "reviewed-deletion");
  await post(ownerApi, "/entries", { key: "new.dependent", content: "Added after preview", entity_id: a.id });
  expectedHttpErrors.add(`409:${PREFIX}/identity/entities/${a.id}/delete`);
  await scope.getByRole("button", { name: "Delete reviewed scope", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Data changed");
  expect(await get(ownerApi, "/entries")).toHaveLength(2);
  await page.getByRole("button", { name: "Refresh workbench", exact: true }).click();
  await identities.getByRole("button", { name: /^Preview deletion: Alex Example,/ }).click();
  await expect(scope).toContainText("Added after preview");
  await scope.getByRole("button", { name: "Delete reviewed scope", exact: true }).click();
  await expect(identities.getByRole("button", { name: /^Preview deletion: Alex Example,/ })).toHaveCount(0);
  const remaining = await get(ownerApi, "/identity/entities");
  expect(remaining).toHaveLength(1); expect(remaining[0].id).toBe(b.id);
  expect((await get(ownerApi, "/identity/owner")).entity_id).toBeNull();
  for (const path of ["/entries", "/learning/sources", "/learning/runs"]) expect(await get(ownerApi, path)).toEqual([]);
});

test("literal rendering, locale-preserved drafts and lock while request is pending", async ({ page, ownerApi }, info) => {
  await unlock(page); const identities = await openIdentity(page);
  const records = identities.getByRole("region", { name: "Identity records", exact: true });
  const literal = "<img src=x onerror=alert(1)>";
  await records.getByLabel("Entity name", { exact: true }).fill(literal);
  await records.getByLabel("Aliases", { exact: true }).fill("<b>Alias</b>");
  await records.getByRole("button", { name: "Propose identity", exact: true }).click();
  await expect(records.getByText(literal, { exact: true })).toBeVisible();
  await expect(page.locator('img[src="x"]')).toHaveCount(0);
  await records.getByLabel("Entity name", { exact: true }).fill("Private fictional draft");
  await page.getByRole("combobox", { name: "Language", exact: true }).selectOption("zh-CN");
  await expect(page.getByLabel("对象名称", { exact: true })).toHaveValue("Private fictional draft");
  await page.getByLabel("对象名称", { exact: true }).scrollIntoViewIfNeeded();
  await layoutScreenshot(page, info, "localized-identity");
  await page.getByRole("combobox", { name: "语言", exact: true }).selectOption("en");

  let release!: () => void;
  const gate = new Promise<void>(done => { release = done; });
  let started!: () => void;
  const pending = new Promise<void>(done => { started = done; });
  await page.route(`**${PREFIX}/identity/entities`, async route => {
    if (route.request().method() !== "POST") { await route.continue(); return; }
    started(); await gate;
    try { await route.continue(); } catch { /* The browser cancelled the owned request on lock. */ }
  });
  await records.getByRole("button", { name: "Propose identity", exact: true }).click();
  await pending;
  await expect(page.getByRole("button", { name: "Refresh workbench", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Lock", exact: true }).click();
  await expect(page.getByLabel("Workspace token", { exact: true })).toHaveValue("");
  release();
  await expect(page.getByRole("region", { name: "Identity & relationship review", exact: true })).toHaveCount(0);
  await expect(page.getByText("Private fictional draft", { exact: true })).toHaveCount(0);
  expect((await get(ownerApi, "/identity/entities")).some((item: { name: string }) => item.name === literal)).toBe(true);
});
