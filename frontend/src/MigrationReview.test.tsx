import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import raw from "./__fixtures__/migration.json";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { messages } from "./i18n";
const t = messages.en.personalWorkspace.migration;
const response = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function server() {
  const state = { owner: raw.preview.destination_owner_id, empty: true, applied: 0, stale: false, unauthorized: false, limit: 262144 };
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    if (state.unauthorized) return response({ detail: "Unauthorized" }, 401);
    const path = url.replace(/^.*\/personal/, "");
    if (options.method === "GET") {
      if (path === "/portability/state") return response({ owner_id: state.owner, empty: state.empty, max_snapshot_bytes: 16 * 1024 * 1024, max_request_body_bytes: state.limit });
      if (path.startsWith("/audit?")) return response(raw.snapshot.audit_events.slice(0, 2).map(row => ({ ...row, owner_id: state.owner })));
      if (path === "/export") return response({ ...raw.snapshot, owner_id: state.owner });
      return response([]);
    }
    if (path === "/portability/preview") return state.empty ? response(raw.preview) : response({ detail: "Destination not empty" }, 409);
    if (path === "/portability/import") {
      if (state.stale || !state.empty) return response({ detail: "Destination changed" }, 409);
      state.applied++; state.owner = raw.snapshot.owner_id; state.empty = false; return response(raw.receipt);
    }
    throw new Error(`Unexpected migration fixture ${path}`);
  });
  vi.stubGlobal("fetch", fetcher); return { state, fetcher };
}
const mount = (onLock = vi.fn()) => render(<ReviewWorkbench token="fictional-token" text={messages.en.personalWorkspace} maxQuestionChars={8000} onLock={onLock} />);
async function idle() { await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled()); }
async function open() { await screen.findByRole("button", { name: t.open }); await idle(); fireEvent.click(screen.getByRole("button", { name: t.open })); const pane = await screen.findByRole("region", { name: t.title }); await idle(); return pane; }
async function load(pane: HTMLElement, value = JSON.stringify(raw.snapshot)) {
  const bytes = new TextEncoder().encode(value);
  fireEvent.change(within(pane).getByLabelText(t.readFile), { target: { files: [{ size: bytes.byteLength, arrayBuffer: async () => bytes.buffer }] } }); await idle();
}
async function preview(pane: HTMLElement) { fireEvent.click(within(pane).getByRole("button", { name: t.preview })); await idle(); return within(pane).getByRole("alertdialog", { name: t.review }); }
it("lazily loads bounded metadata/audit, never shows raw snapshot bodies, and separates review from consent/apply", async () => {
  const { state, fetcher } = server(); mount(); const pane = await open(); expect(fetcher).toHaveBeenCalledTimes(6);
  expect(within(pane).getByText(t.empty)).toBeInTheDocument(); await load(pane); const dialog = await preview(pane);
  expect(state.applied).toBe(0); expect(dialog).toHaveTextContent(raw.preview.digest); expect(dialog).toHaveTextContent(t.toolsArchived);
  expect(pane).not.toHaveTextContent("Fictional migration payload not rendered"); expect(within(dialog).getByRole("button", { name: t.import })).toBeDisabled();
  fireEvent.click(within(dialog).getByLabelText(t.consent)); fireEvent.click(within(dialog).getByRole("button", { name: t.import })); await idle();
  expect(state.applied).toBe(1); expect(within(pane).getByText(t.occupied)).toBeInTheDocument(); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(within(pane).getByLabelText(t.readFile)).toBeDisabled(); expect(within(pane).getByRole("button", { name: t.clearFile })).toBeDisabled();
  const sent = JSON.parse(fetcher.mock.calls.find(([url]) => url.endsWith("/import"))![1].body as string);
  expect(sent).toEqual({ snapshot: raw.snapshot, expected_destination_owner_id: raw.preview.destination_owner_id, digest: raw.preview.digest });
});
it("replacing/clearing files or refreshing discards old review and consent without mutation", async () => {
  const { state } = server(); mount(); const pane = await open(); await load(pane); let dialog = await preview(pane);
  fireEvent.click(within(dialog).getByLabelText(t.consent)); await load(pane); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  dialog = await preview(pane); expect(within(dialog).getByLabelText(t.consent)).not.toBeChecked();
  fireEvent.click(screen.getByRole("button", { name: "Refresh workbench" })); await idle(); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
  fireEvent.click(within(pane).getByRole("button", { name: t.clearFile })); expect(within(pane).getByRole("button", { name: t.preview })).toBeDisabled(); expect(state.applied).toBe(0);
});
it("rejects malformed duplicate-key snapshots locally and does not retain the previously loaded file", async () => {
  const { fetcher } = server(); mount(); const pane = await open(); await load(pane); await load(pane, '{"version":8,"owner_id":"a","owner_id":"b"}');
  expect(within(pane).getByRole("alert")).toHaveTextContent(t.invalid); expect(within(pane).getByRole("button", { name: t.preview })).toBeDisabled();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/preview"))).toBe(false);
});
it("nonempty destinations disable loading/import while still allowing audit inspection", async () => {
  const { state, fetcher } = server(); state.empty = false; mount(); const pane = await open();
  expect(within(pane).getByLabelText(t.readFile)).toBeDisabled(); expect(within(pane).getByText(t.occupied)).toBeInTheDocument();
  fireEvent.change(within(pane).getByRole("combobox", { name: t.limit }), { target: { value: 500 } });
  fireEvent.click(within(pane).getByRole("button", { name: t.reloadAudit })); await idle();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/audit?limit=500"))).toBe(true); expect(state.applied).toBe(0);
});
it("stale destination rejection removes consent and does not automatically retry", async () => {
  const { state, fetcher } = server(); mount(); const pane = await open(); await load(pane); const dialog = await preview(pane); state.stale = true;
  fireEvent.click(within(dialog).getByLabelText(t.consent)); fireEvent.click(within(dialog).getByRole("button", { name: t.import })); await idle();
  expect(state.applied).toBe(0); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument(); expect(screen.getByRole("alert")).toHaveTextContent("Refresh");
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/import"))).toHaveLength(1);
});
it("export is an explicit owner download and preserves byte data rather than raw rendering", async () => {
  server(); const create = vi.fn(() => "blob:fixture-private-export"); const revoke = vi.fn();
  Object.defineProperty(URL, "createObjectURL", { value: create, configurable: true }); Object.defineProperty(URL, "revokeObjectURL", { value: revoke, configurable: true });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  try {
    mount(); const pane = await open(); expect(create).not.toHaveBeenCalled(); fireEvent.click(within(pane).getByRole("button", { name: t.export })); await idle();
    expect(create).toHaveBeenCalledTimes(1); expect(click).toHaveBeenCalledTimes(1); expect(revoke).toHaveBeenCalledWith("blob:fixture-private-export");
    expect(within(pane).getByRole("status")).toHaveTextContent(t.exported); expect(pane).not.toHaveTextContent("Fictional migration payload not rendered");
  } finally { click.mockRestore(); }
});
it("authentication failure locks and locale changes keep the loaded file while changing review labels", async () => {
  const { state } = server(); const lock = vi.fn(); const rendered = mount(lock); const pane = await open(); await load(pane);
  rendered.rerender(<ReviewWorkbench token="fictional-token" text={messages["zh-CN"].personalWorkspace} maxQuestionChars={8000} onLock={lock} />);
  expect(screen.getByRole("button", { name: "预览快照导入" })).toBeEnabled(); state.unauthorized = true; fireEvent.click(screen.getByRole("button", { name: "预览快照导入" }));
  await waitFor(() => expect(lock).toHaveBeenCalledTimes(1));
});
