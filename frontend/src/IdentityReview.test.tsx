import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { entityFixture, projectFixture, relationshipFixture, memoryFixture, identityDeleteFixture, sourceFixture, timestamp } from "./__fixtures__/review";
import type { Entity, EntityRevision, Relationship, RelationshipRevision, MemoryRecord, OwnerIdentity, LearningSource } from "./personalApi";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { messages } from "./i18n";

const text = messages.en.personalWorkspace;
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function server() {
  const state: {
    entities: Entity[]; relationships: Relationship[]; memories: MemoryRecord[]; owner: OwnerIdentity;
    sources: LearningSource[]; entityHistory: Record<string, EntityRevision[]>; relationHistory: RelationshipRevision[]; deletionChanged: boolean;
  } = {
    entities: [], relationships: [], memories: [{ ...memoryFixture, status: "confirmed", revision: 2 }],
    sources: [], owner: { owner_id: "synthetic-owner", entity_id: null }, entityHistory: {}, relationHistory: [], deletionChanged: false,
  };
  let entityCount = 0;
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    const path = url.replace(/^.*\/personal/, "");
    const body = options.body ? JSON.parse(options.body as string) : null;
    if (options.method === "GET") {
      if (path === "/identity/entities") return response(state.entities);
      if (path === "/identity/owner") return response(state.owner);
      if (path === "/identity/relationships") return response(state.relationships);
      if (path.startsWith("/entries?")) return response(state.memories);
      if (path === "/learning/sources") return response(state.sources);
      if (path === "/learning/runs") return response([]);
      if (path.endsWith("/history")) return response(path.includes("/entities/") ? state.entityHistory[path.split("/")[3]] : state.relationHistory);
      if (path.endsWith("/delete-preview")) {
        const id = path.split("/")[3]; const isEntity = path.includes("/entities/");
        return response({ ...identityDeleteFixture, kind: isEntity ? "entity" : "relationship",
          record: isEntity ? state.entities.find(item => item.id === id) : state.relationships.find(item => item.id === id),
          memories: isEntity ? state.memories : [], sources: [], runs: [], relationships: isEntity ? state.relationships : [],
          owner_binding: isEntity && state.owner.entity_id === id, history_count: 2, origin_count: 0,
        });
      }
      if (path.includes("/neighbours?")) {
        const id = path.split("/")[3];
        const relationships = state.relationships.filter(item => item.status === "confirmed" &&
          (item.from_entity_id === id || item.to_entity_id === id) &&
          state.memories.some(memory => memory.id === item.evidence_id && memory.revision === item.evidence_revision && memory.status === "confirmed"));
        return response({ entities: state.entities.filter(item => item.status === "confirmed"), relationships });
      }
    }
    if (path === "/learning/sources") {
      const item = { ...sourceFixture, ...body }; state.sources.push(item); return response(item);
    }
    if (path === "/identity/entities") {
      const item: Entity = { ...entityFixture, ...body, id: `entity-${++entityCount}`, status: "pending", revision: 1, created_at: timestamp, updated_at: timestamp };
      delete (item as unknown as Record<string, unknown>).distinct;
      state.entities.push(item); state.entityHistory[item.id] = [{ ...item, change: "created" }]; return response(item);
    }
    if (path.startsWith("/identity/entities/") && !path.endsWith("/delete")) {
      const item = state.entities.find(item => item.id === path.split("/")[3])!;
      if (body.expected_revision !== item.revision) return response({ detail: "Entity changed" }, 409);
      const edit = path.endsWith("/edit");
      if (edit) { for (const key of ["name", "kind", "aliases", "sensitivity"] as const) Object.assign(item, { [key]: body[key] }); }
      item.revision++; item.status = edit ? "pending" : "confirmed";
      state.entityHistory[item.id].push({ ...item, change: edit ? "edited" : "confirmed" }); return response(item);
    }
    if (path === "/identity/owner") {
      const target = state.entities.find(item => item.id === body.entity_id);
      if (body.expected_owner_entity_id !== state.owner.entity_id || body.entity_id && target?.revision !== body.expected_entity_revision) {
        return response({ detail: "Owner changed" }, 409);
      }
      state.owner = { ...state.owner, entity_id: body.entity_id }; return response(state.owner);
    }
    if (path === "/identity/resolve") {
      const matches = state.entities.filter(item => item.status === "confirmed" && (body.allow_sensitive || item.sensitivity !== "sensitive") &&
        (!body.kind || item.kind === body.kind) && [item.name, ...item.aliases].some(alias => alias.toLowerCase() === body.name.toLowerCase()));
      return response({ status: matches.length === 1 ? "resolved" : matches.length ? "ambiguous" : "unknown", matches });
    }
    if (path === "/identity/relationships") {
      if (!state.memories.some(item => item.id === body.evidence_id && item.revision === body.expected_evidence_revision) ||
        state.entities.filter(item => [body.from_entity_id, body.to_entity_id].includes(item.id)).some(item => item.revision !== body.expected_entity_revisions[item.id])) {
        return response({ detail: "Relationship changed" }, 409);
      }
      const item: Relationship = { ...relationshipFixture, from_entity_id: body.from_entity_id, to_entity_id: body.to_entity_id,
        evidence_id: body.evidence_id, evidence_revision: body.expected_evidence_revision, predicate: body.predicate, sensitivity: body.sensitivity };
      state.relationships.push(item); state.relationHistory = [{ ...item, change: "created" }]; return response(item);
    }
    if (path.startsWith("/identity/relationships/") && path.endsWith("/confirm")) {
      const item = state.relationships.find(item => item.id === path.split("/")[3])!;
      if (body.expected_revision !== item.revision) return response({ detail: "Relationship changed" }, 409);
      item.revision++; item.status = "confirmed"; state.relationHistory.push({ ...item, change: "confirmed" }); return response(item);
    }
    if (path.endsWith("/delete")) {
      if (state.deletionChanged) return response({ detail: "Deletion scope changed" }, 409);
      const id = path.split("/")[3];
      if (path.includes("/entities/")) {
        state.entities = state.entities.filter(item => item.id !== id); state.memories = []; state.relationships = [];
        if (state.owner.entity_id === id) state.owner.entity_id = null;
      } else state.relationships = state.relationships.filter(item => item.id !== id);
      return response({ deleted: true });
    }
    if (path === "/ask") return response({ run_id: "personal_synthetic", mode: "personal-grounded-local", status: "unknown", answer: "No confirmed evidence", evidence: [] });
    throw new Error(`Unexpected identity request ${path}`);
  });
  vi.stubGlobal("fetch", fetcher);
  return { state, fetcher };
}
function mount(onLock = vi.fn()) { return render(<ReviewWorkbench token="synthetic-token" text={text} maxQuestionChars={8000} onLock={onLock} />); }
async function openIdentity() {
  const button = await screen.findByRole("button", { name: "Manage identities & relationships" });
  await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
  const panel = await screen.findByRole("region", { name: "Identity & relationship review" });
  await waitFor(() => expect(screen.getByRole("button", { name: "Close identity review" })).toBeEnabled());
  return panel;
}
const click = (panel: HTMLElement, name: string | RegExp) => fireEvent.click(within(panel).getByRole("button", { name }));
async function create(panel: HTMLElement, name: string, kind = "person", aliases = "") {
  const form = within(panel).getByRole("region", { name: "Identity records" });
  fireEvent.change(within(form).getByLabelText("Entity name"), { target: { value: name } });
  fireEvent.change(within(form).getByLabelText("Entity kind"), { target: { value: kind } });
  fireEvent.change(within(form).getByLabelText("Aliases"), { target: { value: aliases } });
  click(panel, "Propose identity");
  await waitFor(() => expect(within(form).getByLabelText("Entity name")).toHaveValue(""));
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
}
function seed(state: ReturnType<typeof server>["state"]) {
  state.entities = [{ ...entityFixture }, { ...projectFixture }];
  state.entityHistory[entityFixture.id] = [{ ...entityFixture, change: "confirmed" }];
  state.entityHistory[projectFixture.id] = [{ ...projectFixture, change: "confirmed" }];
}

it("loads identity management only on demand", async () => {
  const { fetcher } = server(); mount();
  await screen.findByRole("button", { name: "Manage identities & relationships" });
  expect(fetcher).toHaveBeenCalledTimes(4);
  await openIdentity(); expect(fetcher).toHaveBeenCalledTimes(6);
});

it("completes reviewed identity creation, owner binding, relationship proposal/confirmation and current graph/history", async () => {
  const { state, fetcher } = server(); mount(); const panel = await openIdentity();
  await create(panel, "Alex Example", "person", "Alex");
  expect(state.entities[0].status).toBe("pending");
  click(panel, "Confirm: Alex Example, entity-1");
  await waitFor(() => expect(state.entities[0].status).toBe("confirmed"));
  await waitFor(() => expect(within(panel).getByRole("button", { name: "Propose identity" })).toBeDisabled());
  await create(panel, "Orchid Demo", "project", "Orchid");
  click(panel, "Confirm: Orchid Demo, entity-2");
  await waitFor(() => expect(state.entities[1].status).toBe("confirmed"));
  await waitFor(() => expect(within(panel).getByRole("combobox", { name: "Workspace owner" })).toBeEnabled());
  fireEvent.change(within(panel).getByRole("combobox", { name: "Workspace owner" }), { target: { value: "entity-1" } });
  click(panel, "Review owner binding");
  const binding = within(panel).getByRole("alertdialog", { name: "Review owner binding" });
  expect(state.owner.entity_id).toBeNull(); expect(binding).toHaveTextContent("Alex Example");
  fireEvent.click(within(binding).getByRole("button", { name: "Confirm" }));
  await waitFor(() => expect(state.owner.entity_id).toBe("entity-1"));
  await waitFor(() => expect(within(panel).getByLabelText("From entity")).toBeEnabled());
  fireEvent.change(within(panel).getByLabelText("From entity"), { target: { value: "entity-1" } });
  fireEvent.change(within(panel).getByLabelText("To entity"), { target: { value: "entity-2" } });
  fireEvent.change(within(panel).getByLabelText("Confirmed evidence"), { target: { value: "memory-one" } });
  expect(within(panel).getByText("Alex Example", { selector: "blockquote" })).toBeInTheDocument();
  click(panel, "Propose relationship");
  await screen.findByRole("button", { name: "Confirm: works_on, relationship-one" });
  expect(state.relationships[0].status).toBe("pending");
  click(panel, "Confirm: works_on, relationship-one");
  await waitFor(() => expect(state.relationships[0].status).toBe("confirmed"));
  await waitFor(() => expect(within(panel).getByRole("button", { name: "Current relationships: Alex Example, entity-1" })).toBeEnabled());
  click(panel, "Current relationships: Alex Example, entity-1");
  expect(await within(panel).findByRole("region", { name: "Current relationships" })).toHaveTextContent("works_on");
  click(panel, "Identity history: Alex Example, entity-1");
  expect(await within(panel).findByRole("region", { name: "Identity history" })).toHaveTextContent("created");
  const body = JSON.parse(fetcher.mock.calls.find(([url, options]) => url.endsWith("/identity/relationships") && options.method === "POST")![1].body as string);
  expect(body.expected_evidence_revision).toBe(2);
  expect(body.expected_entity_revisions).toEqual({ "entity-1": 2, "entity-2": 2 });
});

it("shows alias ambiguity without any automatic merge or mutation", async () => {
  const { state, fetcher } = server(); seed(state);
  state.entities.push({ ...entityFixture, id: "person-other", name: "River Example", aliases: ["Alex"] });
  mount(); const panel = await openIdentity();
  const resolver = within(panel).getByRole("region", { name: "Resolve exact alias" });
  fireEvent.change(within(resolver).getByLabelText("Alias to resolve"), { target: { value: "Alex" } });
  fireEvent.click(within(resolver).getByRole("button", { name: "Resolve exact alias" }));
  await within(panel).findByText("Ambiguous: choose an entity ID; no automatic merge.");
  expect(state.entities).toHaveLength(3);
  expect(fetcher.mock.calls.filter(([, options]) => options.method === "POST")).toHaveLength(1);
});

it("shows exact cascade scope and requires a second deletion approval", async () => {
  const { state, fetcher } = server(); seed(state); state.owner.entity_id = "entity-one"; state.relationships = [{ ...relationshipFixture }];
  mount(); const panel = await openIdentity(); click(panel, "Preview deletion: Alex Example, entity-one");
  const preview = await within(panel).findByRole("alertdialog", { name: "Reviewed deletion scope" });
  expect(preview).toHaveTextContent("Alex Example"); expect(preview).toHaveTextContent("History snapshots: 2");
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/delete"))).toBe(false);
  fireEvent.click(within(preview).getByRole("button", { name: "Delete reviewed scope" }));
  await waitFor(() => expect(state.entities).toHaveLength(1));
  expect(state.memories).toHaveLength(0); expect(state.owner.entity_id).toBeNull();
  const body = JSON.parse(fetcher.mock.calls.find(([url]) => url.endsWith("/delete"))![1].body as string);
  expect(body).toEqual({ expected_revision: 2, digest: "b".repeat(64) });
});

it("rejects changed deletion scope without removing records", async () => {
  const { state } = server(); seed(state); mount(); const panel = await openIdentity();
  click(panel, "Preview deletion: Alex Example, entity-one");
  const preview = await within(panel).findByRole("alertdialog", { name: "Reviewed deletion scope" });
  state.deletionChanged = true;
  fireEvent.click(within(preview).getByRole("button", { name: "Delete reviewed scope" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Data changed"));
  expect(state.entities).toHaveLength(2); expect(state.memories).toHaveLength(1);
});

it("rejects a stale owner binding target and does not silently use its newer revision", async () => {
  const { state } = server(); seed(state); mount(); const panel = await openIdentity();
  fireEvent.change(within(panel).getByRole("combobox", { name: "Workspace owner" }), { target: { value: "entity-one" } });
  click(panel, "Review owner binding"); state.entities[0] = { ...state.entities[0], revision: 4 };
  const dialog = within(panel).getByRole("alertdialog", { name: "Review owner binding" });
  fireEvent.click(within(dialog).getByRole("button", { name: "Confirm" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Data changed"));
  expect(state.owner.entity_id).toBeNull();
});

it("disables relationship confirmation when its exact evidence is no longer current", async () => {
  const { state } = server(); seed(state); state.relationships = [{ ...relationshipFixture }];
  state.memories[0].revision = 3; state.memories[0].content = "Unreviewed new value";
  mount(); const panel = await openIdentity();
  expect(within(panel).getByRole("button", { name: "Confirm: works_on, relationship-one" })).toBeDisabled();
  expect(within(panel).getByText("Evidence or an endpoint is no longer current. Refresh and propose again.")).toBeInTheDocument();
  expect(within(panel).queryByText("Unreviewed new value", { selector: "blockquote" })).not.toBeInTheDocument();
});

it("edits preserve labels and aliases, and become pending until a new confirmation", async () => {
  const { state, fetcher } = server(); seed(state); state.entities[0].sensitivity = "sensitive";
  mount(); const panel = await openIdentity(); click(panel, "Edit: Alex Example, entity-one");
  const form = within(panel).getByRole("region", { name: "Identity records" });
  expect(within(form).getByLabelText("Aliases")).toHaveValue("Alex");
  expect(within(form).getByLabelText("Sensitivity")).toHaveValue("sensitive");
  fireEvent.change(within(form).getByLabelText("Entity name"), { target: { value: "River Example" } });
  click(panel, "Save edit as pending");
  await waitFor(() => expect(state.entities[0].status).toBe("pending"));
  expect(state.entities[0].aliases).toEqual(["Alex"]); expect(state.entities[0].sensitivity).toBe("sensitive");
  const body = JSON.parse(fetcher.mock.calls.find(([url]) => url.endsWith("/edit"))![1].body as string);
  expect(body.expected_revision).toBe(2);
});

it("uses a single shared request session and prevents concurrent workbench mutations", async () => {
  const { fetcher } = server(); mount(); const panel = await openIdentity();
  let resolve!: (value: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }));
  const form = within(panel).getByRole("region", { name: "Identity records" });
  fireEvent.change(within(form).getByLabelText("Entity name"), { target: { value: "Synthetic pending" } });
  click(panel, "Propose identity");
  expect(screen.getByRole("button", { name: "Register source" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeDisabled();
  const signals = fetcher.mock.calls.map(([, options]) => options.signal);
  expect(new Set(signals).size).toBe(1);
  resolve(response({ ...entityFixture, name: "Synthetic pending", status: "pending", revision: 1 }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
});

it("relocalizes identity controls without refetching or clearing drafts", async () => {
  const { fetcher } = server(); const { rerender } = mount(); const panel = await openIdentity();
  fireEvent.change(within(panel).getByLabelText("Entity name"), { target: { value: "<b>Private draft</b>" } });
  const count = fetcher.mock.calls.length;
  rerender(<ReviewWorkbench token="synthetic-token" text={messages["zh-CN"].personalWorkspace} maxQuestionChars={8000} onLock={vi.fn()} />);
  expect(screen.getByLabelText("对象名称")).toHaveValue("<b>Private draft</b>");
  expect(screen.getByRole("button", { name: "添加身份候选" })).toBeInTheDocument(); expect(fetcher).toHaveBeenCalledTimes(count);
});

it("bounds alias lists and requires distinct endpoints and an explicit predicate", async () => {
  server(); mount(); const panel = await openIdentity();
  const form = within(panel).getByRole("region", { name: "Identity records" });
  fireEvent.change(within(form).getByLabelText("Entity name"), { target: { value: "Synthetic" } });
  fireEvent.change(within(form).getByLabelText("Aliases"), { target: { value: Array.from({ length: 21 }, (_, i) => `Alias${i}`).join("\n") } });
  expect(within(panel).getByRole("button", { name: "Propose identity" })).toBeDisabled();
  expect(within(panel).getByRole("button", { name: "Propose relationship" })).toBeDisabled();
});

it("keeps sensitive alias lookup opt-in explicit and resets it after a successful lookup", async () => {
  const { state, fetcher } = server(); seed(state); state.entities[0].sensitivity = "sensitive";
  mount(); const panel = await openIdentity();
  const input = within(panel).getByLabelText("Alias to resolve");
  const form = input.closest("form")!;
  fireEvent.change(input, { target: { value: "Alex" } });
  fireEvent.click(within(form).getByRole("button", { name: "Resolve exact alias" }));
  await within(panel).findByText("Unknown", { selector: "h5" });
  fireEvent.click(within(form).getByLabelText("Include sensitive identities for this lookup"));
  fireEvent.click(within(form).getByRole("button", { name: "Resolve exact alias" }));
  await within(panel).findByText("Resolved", { selector: "h5" });
  expect(within(form).getByLabelText("Include sensitive identities for this lookup")).not.toBeChecked();
  const calls = fetcher.mock.calls.filter(([url]) => url.endsWith("/identity/resolve"));
  expect(calls.map(([, options]) => JSON.parse(options.body as string).allow_sensitive)).toEqual([false, true]);
});

it("cancels deletion review without issuing a deletion", async () => {
  const { state, fetcher } = server(); seed(state); mount(); const panel = await openIdentity();
  click(panel, "Preview deletion: Alex Example, entity-one");
  const dialog = await within(panel).findByRole("alertdialog", { name: "Reviewed deletion scope" });
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(within(panel).queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/delete"))).toBe(false); expect(state.entities).toHaveLength(2);
});

it("renders identity names and aliases as text and makes distinct creation an explicit one-off choice", async () => {
  const { state, fetcher } = server(); mount(); const panel = await openIdentity();
  const form = within(panel).getByRole("region", { name: "Identity records" });
  fireEvent.click(within(form).getByLabelText("Create a deliberately distinct identity"));
  await create(panel, "<img src=x onerror=alert(1)>", "person", "<b>Alias</b>");
  expect(state.entities).toHaveLength(1);
  expect(panel.querySelector("img")).toBeNull();
  expect(within(form).getByLabelText("Create a deliberately distinct identity")).not.toBeChecked();
  const call = fetcher.mock.calls.find(([url, options]) => url.endsWith("/identity/entities") && options.method === "POST")!;
  expect(JSON.parse(call[1].body as string).distinct).toBe(true);
});

it("aborts the shared identity request on unmount and cannot render its late result", async () => {
  const { fetcher } = server(); const { unmount } = mount(); const panel = await openIdentity();
  let resolve!: (value: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }));
  await createUnfinished();
  async function createUnfinished() {
    const form = within(panel).getByRole("region", { name: "Identity records" });
    fireEvent.change(within(form).getByLabelText("Entity name"), { target: { value: "Late private fixture" } });
    click(panel, "Propose identity");
  }
  const signal = fetcher.mock.calls.at(-1)![1].signal!;
  unmount(); expect(signal.aborted).toBe(true);
  resolve(response({ ...entityFixture, name: "Late private fixture" }));
  await Promise.resolve(); expect(screen.queryByText("Late private fixture")).not.toBeInTheDocument();
});

it("connects confirmed identities to source registration and explicit subject-scoped ask", async () => {
  const { state, fetcher } = server(); seed(state); mount();
  await screen.findByLabelText("Source name");
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
  const sources = screen.getByRole("region", { name: "Learning sources" });
  fireEvent.change(within(sources).getByRole("combobox", { name: "Subject" }), { target: { value: "entity-one" } });
  fireEvent.change(within(sources).getByLabelText("Source name"), { target: { value: "Fictional subject profile" } });
  fireEvent.click(within(sources).getByRole("button", { name: "Register source" }));
  await waitFor(() => expect(state.sources).toHaveLength(1));
  expect(state.sources[0].entity_id).toBe("entity-one"); expect(state.sources[0].approved).toBe(false);
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
  const ask = screen.getByRole("region", { name: "Ask with evidence" });
  fireEvent.change(within(ask).getByRole("combobox", { name: "Subject" }), { target: { value: "project-one" } });
  fireEvent.change(within(ask).getByLabelText("Private question"), { target: { value: "What is the project?" } });
  fireEvent.click(within(ask).getByRole("button", { name: "Send" }));
  await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith("/ask"))).toBe(true));
  const call = fetcher.mock.calls.find(([url]) => url.endsWith("/ask"))!;
  expect(JSON.parse(call[1].body as string)).toEqual({ question: "What is the project?", allow_sensitive: false, entity_id: "project-one" });
});

it("does not silently replace a stale subject with an unscoped source grant", async () => {
  const { state, fetcher } = server(); seed(state); mount();
  await screen.findByLabelText("Source name");
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
  const sources = screen.getByRole("region", { name: "Learning sources" });
  const subject = within(sources).getByRole("combobox", { name: "Subject" });
  fireEvent.change(subject, { target: { value: "entity-one" } });
  state.entities[0] = { ...state.entities[0], status: "pending", revision: 3 };
  fireEvent.click(screen.getByRole("button", { name: "Refresh workbench" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
  expect(subject).toHaveValue("entity-one");
  fireEvent.change(within(sources).getByLabelText("Source name"), { target: { value: "Fictional subject profile" } });
  fireEvent.click(within(sources).getByRole("button", { name: "Register source" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Data changed"));
  expect(fetcher.mock.calls.some(([url, options]) => url.endsWith("/learning/sources") && options.method === "POST")).toBe(false);
});
