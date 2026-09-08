import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import type { CollaborationPolicy } from "./api";
import { messages } from "./i18n";
import baseline from "./__fixtures__/collaboration/baseline.json";
import verified from "./__fixtures__/collaboration/verified.json";
import * as exporter from "./exportRun";

const text = messages.en;
const fixtures = { baseline, verified };
const question = "How does the example agent plan projects?";
const response = (payload: unknown) => ({ ok: true, json: async () => structuredClone(payload) });

function mockRequests(run: (policy: CollaborationPolicy) => Promise<ReturnType<typeof response>>) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith("/api/v1/profile")) return Promise.resolve(response({
      name: "Fixture agent", description: "Public synthetic metadata", max_question_chars: 8000,
      external_provider_enabled: false,
    }));
    if (url.endsWith("/api/v1/chat")) return Promise.resolve(response({
      answer: "Standard result", mode: "extractive", sources: [],
    }));
    const body = JSON.parse(String(init?.body)) as { workflow: CollaborationPolicy };
    return run(body.workflow);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it("compares both policies with one trimmed question without replacing modes or persisting content", async () => {
  const user = userEvent.setup();
  const fetchMock = mockRequests(async policy => response(fixtures[policy]));
  const storage = vi.spyOn(Storage.prototype, "setItem");
  const pushState = vi.spyOn(window.history, "pushState");
  const replaceState = vi.spyOn(window.history, "replaceState");
  const download = vi.spyOn(exporter, "downloadCollaborationRun").mockImplementation(() => undefined);
  render(<App />);
  await screen.findByText("Fixture agent");
  storage.mockClear(); // The existing locale preference is separate from comparing content.
  await user.type(screen.getByLabelText(text.formLabel), `  ${question}  `);
  await user.click(screen.getByRole("button", { name: text.compareWorkflows }));
  await screen.findByText(verified.run_id);

  expect(screen.getAllByRole("radio")).toHaveLength(3);
  expect(screen.getByRole("radio", { name: text.standardWorkflow })).toBeChecked();
  const requests = fetchMock.mock.calls.filter(([url]) => url.endsWith("/api/v1/collaborate"));
  expect(requests.map(([, init]) => JSON.parse(String(init?.body)))).toEqual([
    { question, workflow: "baseline" }, { question, workflow: "verified" },
  ]);
  expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/api/v1/chat"))).toBe(false);
  const articles = within(screen.getByRole("region", { name: text.compareWorkflows })).getAllByRole("article");
  expect(articles).toEqual([
    screen.getByRole("article", { name: text.baselineComparison }),
    screen.getByRole("article", { name: text.verifiedComparison }),
  ]);
  for (const [index, payload] of [baseline, verified].entries()) {
    const card = within(articles[index]);
    expect(card.getByText(payload.answer, { normalizer: value => value })).toBeInTheDocument();
    expect(card.getByText(payload.sources[0].excerpt)).toBeInTheDocument();
    expect(card.getByText("Grounded")).toBeInTheDocument();
    expect(card.getByRole("heading", { name: text.answer, level: 4 })).toBeInTheDocument();
    expect(card.getByRole("heading", { name: text.workflowTrace, level: 5 })).toBeInTheDocument();
    expect(card.getByRole("button", { name: text.exportRun })).toBeInTheDocument();
    for (const stage of payload.trace) expect(card.getByText(stage.agent, { selector: "code" })).toBeInTheDocument();
  }
  expect(within(articles[1]).getByText(text.extraVerifier)).toBeInTheDocument();
  expect(screen.getByText(text.comparisonLimits)).toBeInTheDocument();
  expect(storage).not.toHaveBeenCalled();
  expect(pushState).not.toHaveBeenCalled();
  expect(replaceState).not.toHaveBeenCalled();
  expect(download).not.toHaveBeenCalled();
});

it.each(["baseline", "verified"] as const)("keeps the other result when %s fails", async failed => {
  mockRequests(async policy => {
    if (policy === failed) throw new Error("private upstream detail");
    return response(fixtures[policy]);
  });
  render(<App />);
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  const failedCard = screen.getByRole("article", { name: failed === "baseline" ? text.baselineComparison : text.verifiedComparison });
  expect(await within(failedCard).findByRole("alert")).toHaveTextContent(text.comparisonFailed);
  expect(await screen.findByText(fixtures[failed === "baseline" ? "verified" : "baseline"].run_id)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: text.retryComparison })).toBeEnabled();
  expect(document.body).not.toHaveTextContent("private upstream detail");
});

it("renders each side as it completes, with stable baseline-first semantic order", async () => {
  const resolvers: Partial<Record<CollaborationPolicy, (value: ReturnType<typeof response>) => void>> = {};
  mockRequests(policy => new Promise(resolve => { resolvers[policy] = resolve; }));
  render(<App />);
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  const baselineCard = screen.getByRole("article", { name: text.baselineComparison });
  const verifiedCard = screen.getByRole("article", { name: text.verifiedComparison });
  expect(baselineCard).toHaveAttribute("aria-busy", "true");
  expect(within(baselineCard).getByText(text.searching)).toHaveAttribute("aria-live", "polite");
  expect(screen.getByRole("button", { name: text.retryComparison })).toBeDisabled();
  expect(screen.getByRole("button", { name: text.ask })).toBeDisabled();
  await act(async () => { resolvers.verified?.(response(verified)); });
  expect(await within(verifiedCard).findByText(verified.run_id)).toBeInTheDocument();
  expect(verifiedCard).toHaveAttribute("aria-busy", "false");
  expect(baselineCard).toHaveAttribute("aria-busy", "true");
  expect(screen.getAllByRole("article")).toEqual([baselineCard, verifiedCard]);
  await act(async () => { resolvers.baseline?.(response(baseline)); });
  expect(await within(baselineCard).findByText(baseline.run_id)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: text.retryComparison })).toBeEnabled();
});

it("retries both failures using the captured question even after the input changes", async () => {
  let attempts = 0;
  const fetchMock = mockRequests(async policy => {
    if (++attempts <= 2) throw new Error("offline");
    return response(fixtures[policy]);
  });
  render(<App />);
  const input = screen.getByLabelText(text.formLabel);
  await userEvent.type(input, question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  expect(await screen.findAllByRole("alert")).toHaveLength(2);
  await userEvent.clear(input);
  await userEvent.type(input, "A different draft question");
  await userEvent.click(screen.getByRole("button", { name: text.retryComparison }));
  await screen.findByText(verified.run_id);
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.filter(([url]) => url.endsWith("/api/v1/collaborate"))
    .map(([, init]) => JSON.parse(String(init?.body)).question)).toEqual(Array(4).fill(question));
  expect(screen.getByText(`${text.comparisonQuestion}: ${question}`)).toBeInTheDocument();
});

it("is keyboard-operated without moving focus or changing the selected mode", async () => {
  const user = userEvent.setup();
  mockRequests(async policy => response(fixtures[policy]));
  render(<App />);
  await user.click(screen.getByRole("radio", { name: text.verifiedWorkflow }));
  await user.type(screen.getByLabelText(text.formLabel), question);
  await user.tab();
  expect(screen.getByRole("button", { name: text.ask })).toHaveFocus();
  await user.tab();
  const compare = screen.getByRole("button", { name: text.compareWorkflows });
  expect(compare).toHaveFocus();
  await user.keyboard("{Enter}");
  await screen.findByText(verified.run_id);
  expect(compare).toHaveFocus();
  expect(screen.getByRole("radio", { name: text.verifiedWorkflow })).toBeChecked();
  await user.tab();
  expect(screen.getByLabelText(text.openRun, { selector: "input" })).toHaveFocus();
});

it("rejects a valid response belonging to the wrong requested policy", async () => {
  mockRequests(async () => response(verified));
  render(<App />);
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  expect(await within(screen.getByRole("article", { name: text.baselineComparison })).findByRole("alert"))
    .toHaveTextContent(text.comparisonFailed);
  expect(await within(screen.getByRole("article", { name: text.verifiedComparison })).findByText(verified.run_id))
    .toBeInTheDocument();
});

it("shows insufficient evidence as a completed workflow, not a request failure", async () => {
  mockRequests(async policy => response(policy === "baseline" ? baseline : {
    ...verified,
    grounded: false,
    answer: "No grounded evidence.",
    sources: [],
    trace: verified.trace.map(stage => stage.agent === "critic"
      ? { ...stage, outcome: "blocked", metrics: { approved: false, query_coverage: 0 } }
      : stage),
  }));
  render(<App />);
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  const card = within(screen.getByRole("article", { name: text.verifiedComparison }));
  expect(await card.findByText(text.notGrounded)).toBeInTheDocument();
  expect(card.getByText(text.blocked)).toBeInTheDocument();
  expect(card.getByText(text.noSources)).toBeInTheDocument();
  expect(card.queryByRole("alert")).not.toBeInTheDocument();
});

it("clears a previous comparison on a normal submission", async () => {
  mockRequests(async policy => response(fixtures[policy]));
  render(<App />);
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  await screen.findByText(verified.run_id);
  await userEvent.click(screen.getByRole("button", { name: text.ask }));
  expect(await screen.findByText("Standard result")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: text.compareWorkflows })).not.toBeInTheDocument();
});

it("disables comparison for empty questions and aborts its requests when unmounted", async () => {
  const fetchMock = mockRequests(() => new Promise(() => undefined));
  const { unmount } = render(<App />);
  expect(screen.getByRole("button", { name: text.compareWorkflows })).toBeDisabled();
  await userEvent.type(screen.getByLabelText(text.formLabel), "   ");
  expect(screen.getByRole("button", { name: text.compareWorkflows })).toBeDisabled();
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  const requests = fetchMock.mock.calls.filter(([url]) => url.endsWith("/api/v1/collaborate"));
  expect(requests).toHaveLength(2);
  unmount();
  await waitFor(() => expect(requests.every(([, init]) => init?.signal?.aborted)).toBe(true));
});

it("maintains independent clipboard statuses between comparison sides", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  mockRequests(async (policy) => response(fixtures[policy]));
  render(<App />);
  await userEvent.type(screen.getByLabelText(text.formLabel), question);
  await userEvent.click(screen.getByRole("button", { name: text.compareWorkflows }));
  await screen.findByText(verified.run_id);

  const baselineCard = screen.getByRole("article", { name: text.baselineComparison });
  const verifiedCard = screen.getByRole("article", { name: text.verifiedComparison });

  await userEvent.click(within(baselineCard).getByRole("button", { name: text.copyAnswer }));
  expect(await within(baselineCard).findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
  expect(within(verifiedCard).queryByRole("status")).not.toBeInTheDocument();

  await userEvent.click(within(verifiedCard).getByRole("button", { name: text.copyAnswer }));
  expect(await within(verifiedCard).findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
  expect(within(baselineCard).getByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
});
