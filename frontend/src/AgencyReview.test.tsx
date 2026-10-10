import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { agencyFixture as f } from "./__fixtures__/agency";
import { messages } from "./i18n";
import type { ActionPlan, NoteRecord, TaskRecord } from "./agencyApi";

const t = messages.en.personalWorkspace.agency;
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function server() {
  const state = {
    permissions: structuredClone(f.disabled), plans: [] as ActionPlan[], tasks: [] as TaskRecord[], notes: [] as NoteRecord[],
    memories: structuredClone(f.memories), fail: false, unauthorized: false, staleRollback: false,
  };
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    const path = url.replace(/^.*\/personal/, ""); const body = options.body ? JSON.parse(options.body as string) : null;
    if (state.unauthorized) return response({ detail: "Unauthorized" }, 401);
    if (options.method === "GET") {
      if (path === "/identity/owner") return response({ owner_id: f.owner_id, entity_id: null });
      if (path === "/identity/entities" || path === "/learning/sources" || path === "/learning/runs") return response([]);
      if (path.startsWith("/entries?")) return response(state.memories);
      if (path === "/tools/permissions") return response(state.permissions);
      if (path === "/actions") return response(state.plans);
      if (path === "/tasks") return response(state.tasks);
      if (path === "/notes") return response(state.notes);
      if (path.endsWith("/events")) return response(f.events.map(item => ({ ...item, plan_id: path.split("/")[2] })));
    }
    if (path.startsWith("/tools/permissions/")) {
      const item = state.permissions.find(p => p.tool === decodeURIComponent(path.split("/").at(-1)!))!;
      if (item.revision !== body.expected_revision) return response({ detail: "Permission changed" }, 409);
      Object.assign(item, body, { revision: item.revision + 1 }); return response(item);
    }
    if (path === "/actions") {
      const same = state.plans.find(item => item.invocation.idempotency_key === body.idempotency_key);
      if (same) return JSON.stringify(same.invocation) === JSON.stringify(body) ? response(same) : response({ detail: "Operation key changed" }, 409);
      const permission = state.permissions.find(p => p.tool === body.tool)!;
      if (body.intent === "act" && !permission.enabled) return response({ detail: "Tool disabled" }, 403);
      const plan = { ...structuredClone(f.planned), id: `plan-${state.plans.length + 1}`, invocation: body,
        status: body.intent === "recommend" ? "recommended" : "planned", permission_revision: permission.revision,
        source_revisions: Object.fromEntries(body.source_ids.map((id: string) => [id, state.memories.find(item => item.id === id)!.revision])), entity_revisions: {},
      } as ActionPlan;
      state.plans.push(plan); return response(plan);
    }
    if (path.startsWith("/actions/")) {
      const plan = state.plans.find(item => item.id === path.split("/")[2])!;
      const action = path.split("/")[3]; const permission = state.permissions.find(item => item.tool === plan.invocation.tool)!;
      if (action === "approve" || action === "execute") {
        if (!permission.enabled) return response({ detail: "Tool disabled" }, 403);
        if (permission.revision !== plan.permission_revision) return response({ detail: "Permission changed" }, 409);
        if (Object.entries(plan.source_revisions).some(([id, revision]) => !state.memories.some(item => item.id === id && item.status === "confirmed" && item.revision === revision))) return response({ detail: "Evidence changed" }, 409);
      }
      if (action === "approve") {
        if (body.expected_revision !== plan.revision || body.digest !== plan.digest) return response({ detail: "Approval changed" }, 409);
        plan.status = "approved"; plan.approved_digest = plan.digest;
      } else if (action === "execute") {
        if (plan.status === "completed") return response(plan);
        plan.attempts++;
        if (state.fail) plan.status = "failed";
        else {
          plan.status = "completed";
          if (plan.invocation.tool === "tasks.complete") {
            const args = plan.invocation.arguments as { task_id: string; expected_revision: number };
            const task = state.tasks.find(item => item.id === args.task_id)!;
            if (task.revision !== args.expected_revision) return response({ detail: "Target changed" }, 409);
            task.status = "completed"; task.revision++;
            plan.result = { table: "tasks", id: task.id, revision: task.revision, changed: true }; plan.undo = { before_status: "open" };
          } else {
            const id = `output-${state.plans.length}`;
            plan.result = { table: plan.invocation.tool === "notes.create" ? "notes" : "tasks", id, revision: 1, changed: true }; plan.undo = {};
            const metadata = { id, owner_id: f.owner_id, created_by: plan.id, revision: 1, sensitivity: plan.invocation.sensitivity, source_ids: plan.invocation.source_ids };
            if (plan.invocation.tool === "notes.create") state.notes.push({ ...f.notes[0], ...plan.invocation.arguments, ...metadata } as NoteRecord);
            else state.tasks.push({ ...f.tasks[0], ...plan.invocation.arguments, ...metadata, status: "open" } as TaskRecord);
          }
        }
      } else if (action === "cancel") plan.status = "cancelled";
      else if (action === "rollback") {
        if (state.staleRollback) return response({ detail: "Output changed" }, 409);
        plan.status = "rolled_back";
        if (plan.invocation.tool === "tasks.complete") { const task = state.tasks.find(item => item.id === plan.result!.id)!; task.status = "open"; task.revision++; }
        else if (plan.result!.table === "tasks") state.tasks = state.tasks.filter(item => item.id !== plan.result!.id);
        else state.notes = state.notes.filter(item => item.id !== plan.result!.id);
      }
      plan.revision++; return response(plan);
    }
    if (path.endsWith("/edit")) { const memory = state.memories.find(item => item.id === path.split("/")[2])!; memory.revision++; memory.status = "pending"; memory.content = body.content; return response(memory); }
    throw new Error(`Unexpected action fixture request: ${path}`);
  });
  vi.stubGlobal("fetch", fetcher); return { state, fetcher };
}
const mount = (onLock = vi.fn()) => render(<ReviewWorkbench token="fictional-token" text={messages.en.personalWorkspace} maxQuestionChars={8000} onLock={onLock} />);
async function idle() { await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled()); }
async function open() {
  const button = await screen.findByRole("button", { name: t.open }); await idle(); fireEvent.click(button);
  const panel = await screen.findByRole("region", { name: t.title }); await idle(); return panel;
}
const click = (panel: HTMLElement, name: string | RegExp) => fireEvent.click(within(panel).getByRole("button", { name }));
async function enable(panel: HTMLElement, tool = "tasks.create") {
  fireEvent.click(within(panel).getByLabelText(`${t.enabled}: ${tool}`)); click(panel, `${t.reviewPermission}: ${tool}`);
  const dialog = within(panel).getByRole("alertdialog", { name: t.reviewPermission }); expect(dialog).toHaveTextContent('"enabled": true');
  click(dialog, t.applyPermission); await idle();
}
async function propose(panel: HTMLElement, title = "Fictional Orchid review", intent = "act") {
  fireEvent.change(within(panel).getByLabelText(t.intent), { target: { value: intent } });
  fireEvent.change(within(panel).getByLabelText(t.taskTitle), { target: { value: title } });
  click(panel, t.propose); await idle();
}
async function approve(panel: HTMLElement, id = "plan-1", tool = "tasks.create") {
  click(panel, `${t.reviewPlan}: ${tool}, ${id}`); await idle(); click(within(panel).getByRole("alertdialog", { name: t.reviewPlan }), t.approve); await idle();
}
async function execute(panel: HTMLElement, id = "plan-1", tool = "tasks.create", failed = false) {
  click(panel, `${t.reviewExecute}: ${tool}, ${id}`); await idle(); click(within(panel).getByRole("alertdialog", { name: t.reviewExecute }), failed ? t.retry : t.execute); await idle();
}

it("lazily loads owner-bound action resources, defaults off and renders empty states", async () => {
  const { fetcher } = server(); mount(); await screen.findByRole("button", { name: t.open }); await idle();
  expect(fetcher).toHaveBeenCalledTimes(4); const panel = await open(); expect(fetcher).toHaveBeenCalledTimes(9);
  expect(within(panel).getByText(t.noPlans)).toBeInTheDocument(); expect(within(panel).getByText(t.noOutputs)).toBeInTheDocument();
  expect(within(panel).getByLabelText(`${t.enabled}: tasks.create`)).not.toBeChecked();
});
it("has independent no-effects permission review, plan, exact approval, execution, events and rollback gates", async () => {
  const { state, fetcher } = server(); mount(); const panel = await open();
  fireEvent.click(within(panel).getByLabelText(`${t.enabled}: tasks.create`)); click(panel, `${t.reviewPermission}: tasks.create`);
  expect(state.permissions[0].enabled).toBe(false); fireEvent.keyDown(within(panel).getByRole("alertdialog"), { key: "Escape" });
  expect(state.permissions[0].enabled).toBe(false); click(panel, `${t.reviewPermission}: tasks.create`);
  click(within(panel).getByRole("alertdialog"), t.applyPermission); await idle(); await propose(panel);
  expect(state.plans[0].status).toBe("planned"); expect(state.tasks).toEqual([]);
  click(panel, `${t.reviewPlan}: tasks.create, plan-1`); await idle();
  expect(within(panel).getByRole("alertdialog")).toHaveTextContent(f.planned.digest);
  expect(state.plans[0].approved_digest).toBeNull(); click(within(panel).getByRole("alertdialog"), t.approve); await idle();
  expect(state.plans[0].status).toBe("approved"); expect(state.tasks).toEqual([]); await execute(panel);
  expect(state.tasks[0].title).toBe("Fictional Orchid review"); expect(state.plans[0].attempts).toBe(1);
  click(panel, `${t.events}: tasks.create, plan-1`); await idle(); expect(within(panel).getByRole("alertdialog")).toHaveTextContent("transaction_committed"); click(within(panel).getByRole("alertdialog"), "Cancel");
  click(panel, `${t.reviewRollback}: tasks.create, plan-1`); await idle(); expect(state.tasks).toHaveLength(1);
  click(within(panel).getByRole("alertdialog"), t.rollback); await idle(); expect(state.tasks).toEqual([]); expect(state.plans[0].status).toBe("rolled_back");
  const approval = fetcher.mock.calls.find(([url]) => String(url).endsWith("/approve"))!;
  expect(JSON.parse(approval[1].body as string)).toEqual({ expected_revision: 1, digest: f.planned.digest });
});
it("saves recommendations with tools disabled but never offers approval/execution; cancellation is reviewed", async () => {
  const { state } = server(); mount(); const panel = await open(); await propose(panel, "Suggestion only", "recommend");
  expect(state.plans[0].status).toBe("recommended"); expect(within(panel).queryByRole("button", { name: /^Review plan:/ })).not.toBeInTheDocument(); expect(state.tasks).toEqual([]);
  click(panel, `${t.reviewCancel}: tasks.create, plan-1`); await idle(); expect(state.plans[0].status).toBe("recommended");
  click(within(panel).getByRole("alertdialog"), t.cancelPlan); await idle(); expect(state.plans[0].status).toBe("cancelled");
});
it("shows exact label/entity policy semantics and cancels an outdated draft review", async () => {
  const { state } = server(); mount(); const panel = await open();
  const form = within(panel).getByRole("button", { name: `${t.reviewPermission}: tasks.create` }).closest("form")!;
  fireEvent.change(within(form).getByLabelText(`${t.entityScope}: tasks.create`), { target: { value: "selected" } });
  const group = within(form).getByRole("group", { name: "Sensitivity: tasks.create" });
  fireEvent.click(within(group).getByLabelText("public")); fireEvent.click(within(group).getByLabelText("private"));
  click(panel, `${t.reviewPermission}: tasks.create`); expect(within(panel).getByRole("alertdialog")).toHaveTextContent('"entity_ids": []');
  fireEvent.click(within(form).getByLabelText(`${t.enabled}: tasks.create`)); expect(within(panel).queryByRole("alertdialog")).not.toBeInTheDocument();
  click(panel, `${t.reviewPermission}: tasks.create`); click(within(panel).getByRole("alertdialog"), t.applyPermission); await idle();
  expect(state.permissions[0]).toMatchObject({ enabled: true, labels: [], entity_ids: [], revision: 2 });
});
it("preserves operation draft/key through ambiguous receipts and replay; only an explicit new key creates another plan", async () => {
  const { state } = server(); mount(); const panel = await open(); await enable(panel); await propose(panel);
  const key = within(panel).getByLabelText(t.idempotency); const original = (key as HTMLInputElement).value;
  click(panel, t.propose); await idle(); expect(state.plans).toHaveLength(1); expect(key).toHaveValue(original);
  click(panel, t.newKey); expect(key).not.toHaveValue(original); click(panel, t.propose); await idle(); expect(state.plans).toHaveLength(2);
});
it("counts inherited and newly selected completion sources once and prevents over-limit submission", async () => {
  const { state } = server();
  state.memories = Array.from({ length: 21 }, (_, n) => ({ ...f.memories[0], id: `fictional-source-${n}`, key: `fictional.field.${n}` }));
  state.tasks = [{ ...f.tasks[0], source_ids: state.memories.slice(0, 20).map(item => item.id) }];
  mount(); const panel = await open();
  fireEvent.change(within(panel).getByLabelText(t.tool), { target: { value: "tasks.complete" } });
  fireEvent.change(within(panel).getByRole("combobox", { name: t.outputs }), { target: { value: state.tasks[0].id } });
  const sources = within(panel).getByLabelText(t.sources) as HTMLSelectElement;
  sources.options[20].selected = true; fireEvent.change(sources);
  expect(within(panel).getByText(`${t.sources}: 21 / 20`)).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: t.propose })).toBeDisabled();
  sources.options[20].selected = false; sources.options[0].selected = true; fireEvent.change(sources);
  expect(within(panel).getByText(`${t.sources}: 20 / 20`)).toBeInTheDocument();
  expect(within(panel).getByRole("button", { name: t.propose })).toBeEnabled();
});
it("explicitly retries failed approved actions at most three times, without auto calls", async () => {
  const { state, fetcher } = server(); state.fail = true; mount(); const panel = await open(); await enable(panel); await propose(panel); await approve(panel); await execute(panel);
  expect(state.plans[0].status).toBe("failed"); expect(state.tasks).toEqual([]); const calls = fetcher.mock.calls.length;
  await new Promise(resolve => setTimeout(resolve, 5)); expect(fetcher).toHaveBeenCalledTimes(calls);
  await execute(panel, "plan-1", "tasks.create", true); await execute(panel, "plan-1", "tasks.create", true);
  expect(state.plans[0].attempts).toBe(3); expect(within(panel).queryByRole("button", { name: /^Review execution:/ })).not.toBeInTheDocument();
});
it("a visible memory mutation invalidates an open action review before the mutation completes", async () => {
  const { state } = server(); state.permissions = structuredClone(f.permissions); const plan = structuredClone(f.planned); state.plans = [plan];
  mount(); const panel = await open(); click(panel, `${t.reviewPlan}: tasks.create, ${plan.id}`); await idle();
  expect(within(panel).getByRole("alertdialog")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Confirmed \(/ }));
  const memory = state.memories[0]; fireEvent.click(screen.getByRole("button", { name: `Edit: ${memory.key}, ${memory.id}` }));
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: "Changed source" } });
  fireEvent.click(screen.getByRole("button", { name: "Save edit as pending" })); await idle();
  expect(within(panel).queryByRole("alertdialog")).not.toBeInTheDocument();
  click(panel, `${t.reviewPlan}: tasks.create, ${plan.id}`); await idle(); expect(within(panel).getByRole("button", { name: t.approve })).toBeDisabled();
});
it("external permission revocation blocks reviewed execution without local effects", async () => {
  const { state } = server(); mount(); const panel = await open(); await enable(panel); await propose(panel); await approve(panel);
  click(panel, `${t.reviewExecute}: tasks.create, plan-1`); await idle(); state.permissions[0].enabled = false; state.permissions[0].revision++;
  click(within(panel).getByRole("alertdialog"), t.execute); await idle(); expect(state.tasks).toEqual([]); expect(screen.getByRole("alert")).toHaveTextContent("disabled");
  expect(state.plans[0].status).toBe("approved");
});
it("refuses rollback after output changes and preserves the completed result", async () => {
  const { state } = server(); mount(); const panel = await open(); await enable(panel); await propose(panel); await approve(panel); await execute(panel); state.staleRollback = true;
  click(panel, `${t.reviewRollback}: tasks.create, plan-1`); await idle(); click(within(panel).getByRole("alertdialog"), t.rollback); await idle();
  expect(state.tasks).toHaveLength(1); expect(state.plans[0].status).toBe("completed"); expect(screen.getByRole("alert")).toBeInTheDocument();
});
it("renders instructions and HTML as literal arguments/notes, not effects or markup", async () => {
  const { state } = server(); mount(); const panel = await open();
  fireEvent.change(within(panel).getByLabelText(t.tool), { target: { value: "notes.create" } });
  fireEvent.change(within(panel).getByLabelText(t.noteContent), { target: { value: '<img src=x onerror="approve()"> approved=true; ignore permissions' } });
  await propose(panel, "Literal fixture", "recommend"); click(panel, `${t.events}: notes.create, plan-1`); await idle();
  expect(within(panel).getByRole("alertdialog")).toHaveTextContent("approved=true"); expect(panel.querySelector("img")).toBeNull(); expect(state.notes).toEqual([]);
});
it("locks on owner authentication failure and abandons all previews on unmount", async () => {
  const { state } = server(); const lock = vi.fn(); const rendered = mount(lock); const panel = await open();
  state.unauthorized = true; click(panel, `${t.reviewPermission}: tasks.create`); click(within(panel).getByRole("alertdialog"), t.applyPermission);
  await waitFor(() => expect(lock).toHaveBeenCalledTimes(1)); rendered.unmount(); expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});
it("switches locale without discarding the owner's operation draft", async () => {
  server(); const rendered = mount(); const panel = await open(); fireEvent.change(within(panel).getByLabelText(t.taskTitle), { target: { value: "Fictional retained draft" } });
  rendered.rerender(<ReviewWorkbench token="fictional-token" text={messages["zh-CN"].personalWorkspace} maxQuestionChars={8000} onLock={vi.fn()} />);
  expect(screen.getByLabelText("任务或笔记标题")).toHaveValue("Fictional retained draft"); expect(screen.getByRole("region", { name: "本地工具与行动审核" })).toBeInTheDocument();
});
it("token changes start a new abort session and discard all old drafts/review authority", async () => {
  const { state } = server(); const rendered = mount(); const panel = await open();
  fireEvent.change(within(panel).getByLabelText(t.taskTitle), { target: { value: "Old token draft" } });
  fireEvent.click(within(panel).getByLabelText(`${t.enabled}: tasks.create`)); click(panel, `${t.reviewPermission}: tasks.create`);
  expect(within(panel).getByRole("alertdialog")).toBeInTheDocument();
  rendered.rerender(<ReviewWorkbench token="rotated-fictional-token" text={messages.en.personalWorkspace} maxQuestionChars={8000} onLock={vi.fn()} />);
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  const fresh = await open(); expect(within(fresh).getByLabelText(t.taskTitle)).toHaveValue("");
  expect(within(fresh).getByLabelText(`${t.enabled}: tasks.create`)).not.toBeChecked(); expect(state.permissions[0].enabled).toBe(false);
});
it("the shared request mutex prevents repeated proposal calls and abort prevents late receipt refresh", async () => {
  const { fetcher } = server(); const delegate = fetcher.getMockImplementation()!;
  let finish: ((value: Response) => void) | undefined; let signal: AbortSignal | undefined; let body: ActionPlan["invocation"] | undefined;
  fetcher.mockImplementation(async (url: string, options: RequestInit) => {
    if (url.endsWith("/actions") && options.method === "POST") {
      signal = options.signal as AbortSignal; body = JSON.parse(options.body as string);
      return new Promise<Response>(resolve => { finish = resolve; });
    }
    return delegate(url, options);
  });
  const rendered = mount(); const panel = await open();
  fireEvent.change(within(panel).getByLabelText(t.taskTitle), { target: { value: "Pending receipt fixture" } });
  const form = within(panel).getByRole("button", { name: t.propose }).closest("form")!;
  fireEvent.submit(form); fireEvent.submit(form);
  expect(fetcher.mock.calls.filter(([url, options]) => url.endsWith("/actions") && options.method === "POST")).toHaveLength(1);
  const count = fetcher.mock.calls.length; rendered.unmount(); expect(signal?.aborted).toBe(true);
  finish!(response({ ...f.planned, id: "late-plan", invocation: body, source_revisions: {}, entity_revisions: {}, status: "recommended" }));
  await new Promise(resolve => setTimeout(resolve, 5)); expect(fetcher).toHaveBeenCalledTimes(count);
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});
