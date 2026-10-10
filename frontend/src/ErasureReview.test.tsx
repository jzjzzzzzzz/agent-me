import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import raw from "./__fixtures__/erasure.json";
import { messages } from "./i18n";
import { ReviewWorkbench } from "./ReviewWorkbench";
import type { ErasureCatalogue, ErasurePreview } from "./erasureApi";
const f = raw as unknown as { catalogue: ErasureCatalogue } & Record<"note" | "actionOnly" | "actionOutput" | "sourceOnly" | "sourceForget", ErasurePreview>;
const t = messages.en.personalWorkspace.erasure;
const response = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function server() {
  const state = { catalogue: structuredClone(f.catalogue), stale: false, unauthorized: false, applied: 0 };
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    const path = url.replace(/^.*\/personal/, ""); const body = options.body ? JSON.parse(options.body as string) : null;
    if (state.unauthorized) return response({ detail: "Unauthorized" }, 401);
    if (options.method === "GET") return response(path.endsWith("/catalogue") ? state.catalogue : []);
    if (path.endsWith("/preview")) {
      const preview = body.kind === "note" ? f.note : body.kind === "action" ? body.purge_output ? f.actionOutput : f.actionOnly : body.forget_memories ? f.sourceForget : f.sourceOnly;
      return response(preview);
    }
    if (path.endsWith("/apply")) {
      if (state.stale) return response({ detail: "Erasure scope changed" }, 409);
      state.applied++;
      const preview = body.request.kind === "note" ? f.note : body.request.kind === "action" ? body.request.purge_output ? f.actionOutput : f.actionOnly : body.request.forget_memories ? f.sourceForget : f.sourceOnly;
      const counts = (rows: ErasurePreview["removed"]) => {
        const result: Record<string, number> = {}; for (const row of rows) result[row.table] = (result[row.table] ?? 0) + 1; return result;
      };
      state.catalogue.items = state.catalogue.items.filter(item => !preview.removed.some(row => row.table === item.record.table && row.id === item.record.id));
      return response({ deleted: true, request: preview.request, digest: preview.digest, removed_counts: counts(preview.removed), retained_counts: counts(preview.retained), forgotten_memories: preview.request.forget_memories ? 2 : 0 });
    }
    throw new Error(`Unexpected erasure fixture ${path}`);
  });
  vi.stubGlobal("fetch", fetcher); return { state, fetcher };
}
const mount = (onLock = vi.fn()) => render(<ReviewWorkbench token="fictional-token" text={messages.en.personalWorkspace} maxQuestionChars={8000} onLock={onLock} />);
async function idle() { await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled()); }
async function open() { await screen.findByRole("button", { name: t.open }); await idle(); fireEvent.click(screen.getByRole("button", { name: t.open })); const pane = await screen.findByRole("region", { name: t.title }); await idle(); return pane; }
function choose(pane: HTMLElement, kind = "note") {
  fireEvent.change(within(pane).getByRole("combobox", { name: t.kind }), { target: { value: kind } });
  const item = f.catalogue.items.find(item => item.kind === kind)!;
  fireEvent.change(within(pane).getByRole("combobox", { name: t.target }), { target: { value: item.record.id } });
}
async function preview(pane: HTMLElement) { fireEvent.click(within(pane).getByRole("button", { name: t.preview })); await idle(); return within(pane).getByRole("alertdialog", { name: t.scope }); }

it("loads metadata only on demand and leaves no deletion effect until scope consent and confirmation", async () => {
  const { state, fetcher } = server(); mount(); const pane = await open(); expect(fetcher).toHaveBeenCalledTimes(5);
  expect(within(pane).getByText(t.noTargets)).toBeInTheDocument(); choose(pane); const dialog = await preview(pane);
  expect(state.applied).toBe(0); expect(dialog).toHaveTextContent(f.note.digest); expect(within(dialog).getByRole("button", { name: t.confirm })).toBeDisabled();
  fireEvent.click(within(dialog).getByLabelText(t.consent)); fireEvent.click(within(dialog).getByRole("button", { name: t.confirm })); await idle();
  expect(state.applied).toBe(1); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument(); expect(within(pane).getByRole("status")).toHaveTextContent(t.done);
  const apply = fetcher.mock.calls.find(([url]) => url.endsWith("/apply"))!;
  expect(JSON.parse(apply[1].body as string)).toEqual({ request: f.note.request, digest: f.note.digest });
});
it("source/action choices clear all previous scope/consent and retained copies are explicit", async () => {
  const { state } = server(); mount(); const pane = await open(); choose(pane, "source"); let dialog = await preview(pane);
  expect(within(dialog).getByRole("region", { name: t.retained })).toHaveTextContent("notes: 1"); fireEvent.click(within(dialog).getByLabelText(t.consent));
  fireEvent.click(within(pane).getByLabelText(t.forgetMemories)); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  dialog = await preview(pane); expect(within(dialog).getByLabelText(t.consent)).not.toBeChecked(); expect(within(dialog).getByRole("region", { name: t.removed })).toHaveTextContent("entries: 2");
  choose(pane, "action"); dialog = await preview(pane); expect(within(dialog).getByRole("region", { name: t.retained })).toHaveTextContent("notes: 1");
  fireEvent.click(within(pane).getByLabelText(t.purgeOutput)); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  dialog = await preview(pane); expect(dialog).toHaveTextContent(`${t.purgeOutput} @ 1`); expect(state.applied).toBe(0);
});
it("rejects a stale dependent scope, discards consent and never silently retries", async () => {
  const { state, fetcher } = server(); mount(); const pane = await open(); choose(pane); const dialog = await preview(pane);
  state.stale = true; fireEvent.click(within(dialog).getByLabelText(t.consent)); fireEvent.click(within(dialog).getByRole("button", { name: t.confirm })); await idle();
  expect(state.applied).toBe(0); expect(screen.getByRole("alert")).toHaveTextContent("Refresh"); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/apply"))).toHaveLength(1);
});
it("workbench refresh invalidates a reviewed scope and keyboard cancellation makes no mutation", async () => {
  const { state } = server(); mount(); const pane = await open(); choose(pane); let dialog = await preview(pane);
  fireEvent.keyDown(dialog, { key: "Escape" }); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  dialog = await preview(pane); fireEvent.click(within(dialog).getByLabelText(t.consent));
  fireEvent.click(screen.getByRole("button", { name: "Refresh workbench" })); await idle();
  expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument(); expect(state.applied).toBe(0);
});
it("locks on failed owner authentication and relabels retained drafts without changing choices", async () => {
  const { state } = server(); const lock = vi.fn(); const rendered = mount(lock); const pane = await open(); choose(pane, "source");
  rendered.rerender(<ReviewWorkbench token="fictional-token" text={messages["zh-CN"].personalWorkspace} maxQuestionChars={8000} onLock={lock} />);
  expect(screen.getByRole("combobox", { name: "副本类型" })).toHaveValue("source");
  state.unauthorized = true; fireEvent.click(screen.getByRole("button", { name: "预览精确清除范围" })); await waitFor(() => expect(lock).toHaveBeenCalledTimes(1));
});
