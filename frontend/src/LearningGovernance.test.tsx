import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import raw from "./__fixtures__/governance.json";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { messages } from "./i18n";
import type { ConsolidationPlan, GovernanceData, RetentionPlan } from "./governanceApi";
import type { MemoryRecord } from "./personalApi";
const t = messages.en.personalWorkspace.governance;
const response = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function server() {
  const state = { controls: { ...structuredClone(raw.state), retention_plans: [] as RetentionPlan[], consolidation_plans: [] as ConsolidationPlan[] } as GovernanceData,
    memories: structuredClone(raw.memories) as MemoryRecord[], stale: false, unauthorized: false, merged: 0, retained: 0 };
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    if (state.unauthorized) return response({ detail: "Unauthorized" }, 401);
    const path = url.replace(/^.*\/personal/, ""); const body = options.body ? JSON.parse(options.body as string) : null;
    if (options.method === "GET") {
      if (path === "/learning/governance") return response({ ...state.controls, observed_at: "2026-10-11T00:00:00Z" });
      if (path.startsWith("/entries?")) return response(state.memories);
      if (path.endsWith("/review")) return response(raw.retentionReview);
      return response([]);
    }
    if (path.endsWith("/policy")) {
      if (state.stale) return response({ detail: "Policy changed" }, 409);
      const field = path.startsWith("/learning") ? "learning" : "retention";
      const value = { revision: state.controls[field].revision + 1, policy: body.policy };
      state.controls = { ...state.controls, [field]: value }; return response(value);
    }
    if (path === "/consolidation/preview") { state.controls.consolidation_plans = [raw.consolidation as ConsolidationPlan]; return response(raw.consolidation); }
    if (path.startsWith("/consolidation/") && path.endsWith("/apply")) {
      if (state.stale) return response({ detail: "Members changed" }, 409);
      state.merged++; state.controls.consolidation_plans = [raw.consolidationApplied as ConsolidationPlan];
      state.memories[0].revision++; state.memories[1].revision++; state.memories[1].status = "superseded";
      return response(raw.consolidationApplied);
    }
    if (path === "/retention/preview") { state.controls.retention_plans = [raw.retention as RetentionPlan]; return response(raw.retention); }
    if (path.endsWith("/apply-reviewed")) {
      if (state.stale) return response({ detail: "Retention scope changed" }, 409);
      state.retained++; state.controls.retention_plans = [raw.retentionApplied as RetentionPlan]; return response(raw.retentionApplied);
    }
    throw new Error(`Unexpected governance fixture ${path}`);
  }); vi.stubGlobal("fetch", fetcher); return { state, fetcher };
}
const mount = (lock = vi.fn()) => render(<ReviewWorkbench token="fixture-token" text={messages.en.personalWorkspace} maxQuestionChars={8000} onLock={lock} />);
async function idle() { await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled()); }
async function open() { await screen.findByRole("button", { name: t.open }); await idle(); fireEvent.click(screen.getByRole("button", { name: t.open })); const pane = await screen.findByRole("region", { name: t.title }); await idle(); return pane; }
const click = (pane: HTMLElement, name: string) => fireEvent.click(within(pane).getByRole("button", { name }));
it("lazily loads default-off controls, validates typed policy and reviews before applying", async () => {
  const { state, fetcher } = server(); mount(); const pane = await open(); expect(fetcher).toHaveBeenCalledTimes(5);
  const input = within(pane).getByLabelText(`${t.policyJson}: ${t.learning}`);
  fireEvent.change(input, { target: { value: JSON.stringify({ ...state.controls.learning.policy, source_kinds: [], labels: [], max_candidates: 1 }) } });
  click(pane, `${t.reviewPolicy}: ${t.learning}`); const dialog = within(pane).getByRole("alertdialog", { name: t.reviewPolicy });
  expect(state.controls.learning.revision).toBe(1); expect(dialog).toHaveTextContent('"max_candidates": 1');
  click(dialog, t.applyPolicy); await idle(); expect(state.controls.learning.revision).toBe(2); expect(state.controls.learning.policy.labels).toEqual([]);
  fireEvent.change(within(pane).getByLabelText(`${t.policyJson}: ${t.learning}`), { target: { value: '{"approved":true}' } });
  expect(within(pane).getByRole("button", { name: `${t.reviewPolicy}: ${t.learning}` })).toBeDisabled();
});
it("exact consolidation preserves pending keeper and requires independent member consent", async () => {
  const { state } = server(); mount(); const pane = await open(); click(pane, t.createConsolidation); await idle();
  expect(state.merged).toBe(0); click(pane, `${t.reviewConsolidation}: ${raw.consolidation.id}`);
  const dialog = within(pane).getByRole("alertdialog"); expect(dialog).toHaveTextContent("Fictional duplicate pending body"); expect(dialog).toHaveTextContent(raw.consolidation.digest);
  expect(within(dialog).getByRole("button", { name: t.applyConsolidation })).toBeDisabled(); fireEvent.click(within(dialog).getByLabelText(t.consent)); click(dialog, t.applyConsolidation); await idle();
  expect(state.merged).toBe(1); expect(state.memories[0].status).toBe("pending"); expect(state.memories[1].status).toBe("superseded");
});
it("retention uses actual scope counts and exact two-digest approval without auto application", async () => {
  const { state, fetcher } = server(); state.controls.retention.revision = raw.retention.policy_revision;
  mount(); const pane = await open(); click(pane, t.createRetention); await idle(); expect(state.retained).toBe(0);
  click(pane, `${t.reviewRetention}: ${raw.retention.id}`); await idle(); const dialog = within(pane).getByRole("alertdialog", { name: t.retentionScope });
  expect(dialog).toHaveTextContent("entries: 1"); expect(dialog).toHaveTextContent(raw.retentionReview.scope_digest);
  fireEvent.click(within(dialog).getByLabelText(t.consent)); click(dialog, t.applyRetention); await idle(); expect(state.retained).toBe(1);
  expect(JSON.parse(fetcher.mock.calls.find(([url]) => url.endsWith("/apply-reviewed"))![1].body as string)).toEqual({ digest: raw.retentionReview.digest, scope_digest: raw.retentionReview.scope_digest });
});
it("stale policy/scope fails without preserving consent or automatic retries", async () => {
  const { state } = server(); mount(); const pane = await open(); click(pane, t.createConsolidation); await idle(); click(pane, `${t.reviewConsolidation}: ${raw.consolidation.id}`);
  state.stale = true; const dialog = within(pane).getByRole("alertdialog"); fireEvent.click(within(dialog).getByLabelText(t.consent)); click(dialog, t.applyConsolidation); await idle();
  expect(state.merged).toBe(0); expect(screen.getByRole("alert")).toHaveTextContent("Refresh"); expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument();
});
it("refresh invalidates reviewed effects and future plans remain explicitly blocked", async () => {
  const { state } = server(); state.controls.retention_plans = [{ ...raw.retention, as_of: "9999-01-01T00:00:00Z" } as RetentionPlan];
  mount(); const pane = await open(); expect(within(pane).getByRole("button", { name: `${t.reviewRetention}: ${raw.retention.id}` })).toBeDisabled();
  click(pane, t.createConsolidation); await idle(); click(pane, `${t.reviewConsolidation}: ${raw.consolidation.id}`); fireEvent.click(screen.getByRole("button", { name: "Refresh workbench" })); await idle();
  expect(within(pane).queryByRole("alertdialog")).not.toBeInTheDocument(); expect(state.merged).toBe(0);
});
it("authentication failures lock and locale switches relabel owner draft controls", async () => {
  const { state } = server(); const lock = vi.fn(); const rendered = mount(lock); const pane = await open();
  fireEvent.change(within(pane).getByLabelText(t.keyPrefix), { target: { value: "fictional." } });
  rendered.rerender(<ReviewWorkbench token="fixture-token" text={messages["zh-CN"].personalWorkspace} maxQuestionChars={8000} onLock={lock} />);
  expect(screen.getByLabelText("字段前缀筛选")).toHaveValue("fictional."); state.unauthorized = true;
  fireEvent.click(screen.getByRole("button", { name: "创建精确整合预览" })); await waitFor(() => expect(lock).toHaveBeenCalledTimes(1));
});
