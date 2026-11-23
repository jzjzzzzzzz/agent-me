import { expect, get, post, test, unlock } from "./fixtures";

test("private chat memory survives reload, respects scope and can be forgotten", async ({ page, ownerApi }) => {
  const pending = await post(ownerApi, "/identity/entities", { kind: "project", name: "Orchid" });
  await post(ownerApi, `/identity/entities/${pending.id}/confirm`, { expected_revision: pending.revision });

  await unlock(page);
  await page.getByRole("button", { name: "Close review workbench", exact: true }).click();
  const workspace = page.getByRole("region", { name: "Private workspace", exact: true });
  const ask = async (value: string) => {
    await workspace.getByLabel("Private question", { exact: true }).fill(value);
    await workspace.getByRole("button", { name: "Send", exact: true }).click();
    await expect(workspace.getByLabel("Private question", { exact: true })).toHaveValue("");
  };
  await workspace.getByRole("button", { name: "Load project scopes", exact: true }).click();
  await workspace.getByRole("combobox", { name: "Memory scope", exact: true }).selectOption(pending.id);
  await ask("Remember: preference response.style = Orchid updates start with evidence.");
  await expect(workspace.getByRole("status")).toContainText("Candidate created");
  await workspace.getByRole("button", { name: /^Confirm: response\.style,/ }).click();
  await expect(workspace.getByRole("button", { name: /^Confirm: response\.style,/ })).toHaveCount(0);

  await unlock(page); // Reloads and authenticates again, without retaining the prior chat scope.
  await page.getByRole("button", { name: "Close review workbench", exact: true }).click();
  await ask("Orchid updates");
  await expect(workspace.locator(".private-history article").last()).toContainText("could not find");
  await workspace.getByRole("button", { name: "Load project scopes", exact: true }).click();
  await workspace.getByRole("combobox", { name: "Memory scope", exact: true }).selectOption(pending.id);
  await ask("How do I like you to answer?");
  await expect(workspace.locator(".private-history article").last()).toContainText("start with evidence");
  await workspace.getByText("Sources offered to the last answer", { exact: true }).click();
  await expect(workspace.locator(".chat-memory-sources")).toContainText("memory/");
  await expect(workspace.locator(".chat-memory-sources")).toContainText("Profile field");

  await workspace.getByRole("button", { name: /^Delete: response\.style,/ }).click();
  await expect(workspace.getByRole("button", { name: /^Delete: response\.style,/ })).toHaveCount(0);
  await ask("Orchid updates");
  await expect(workspace.locator(".private-history article").last()).toContainText("could not find");
  await expect(workspace.locator(".chat-memory-sources")).toHaveCount(0);
  await ask("Remember: preference response.style = Orchid updates start with evidence.");
  await expect(workspace.getByRole("status")).toContainText("forgotten value was not restored");
  expect(await get(ownerApi, "/entries")).toEqual([]);
});

test("owner can create a pending memory from an exact historical quote", async ({ page, ownerApi }) => {
  await unlock(page);
  await page.getByRole("button", { name: "Close review workbench", exact: true }).click();
  const workspace = page.getByRole("region", { name: "Private workspace", exact: true });
  const question = workspace.getByLabel("Private question", { exact: true });
  await question.fill("I like visual project updates.");
  await workspace.getByRole("button", { name: "Send", exact: true }).click();
  await expect(question).toHaveValue("");
  expect(await get(ownerApi, "/entries")).toEqual([]);

  await workspace.getByRole("button", { name: "Propose memory from this message", exact: true }).click();
  const captureForm = workspace.getByRole("form", { name: "Memory from a chat message" });
  await expect(captureForm.getByLabel("Exact excerpt from your message")).toHaveValue("I like visual project updates.");
  await captureForm.getByLabel("Key", { exact: true }).fill("project.update_style");
  await captureForm.getByLabel("Exact excerpt from your message").fill("visual project updates");
  await captureForm.getByRole("button", { name: "Add candidate", exact: true }).click();
  await expect(workspace.getByRole("status")).toContainText("Candidate created");
  expect(await get(ownerApi, "/entries")).toMatchObject([
    { kind: "preference", key: "project.update_style", status: "pending", content: "visual project updates" },
  ]);
});
