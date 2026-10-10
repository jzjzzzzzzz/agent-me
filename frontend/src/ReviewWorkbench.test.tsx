import { StrictMode } from "react";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { answerFixture, historyFixture, memoryFixture, originFixture, runFixture, sourceFixture } from "./__fixtures__/review";
import type { IngestionRun, LearningSource, MemoryRecord, MemoryRevision } from "./personalApi";
import { messages } from "./i18n";
import { ReviewWorkbench } from "./ReviewWorkbench";
import { PersonalWorkspace } from "./PersonalWorkspace";

const text = messages.en.personalWorkspace;
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function server() {
  const state: {
    sources: LearningSource[]; memories: MemoryRecord[]; runs: IngestionRun[];
    history: MemoryRevision[]; failNext: number | null;
  } = { sources: [], memories: [], runs: [], history: [], failNext: null };
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    if (state.failNext) { const code = state.failNext; state.failNext = null; return response({ detail: "Synthetic rejection" }, code); }
    const path = url.replace(/^.*\/personal/, "");
    const body = options.body ? JSON.parse(options.body as string) : null;
    if (options.method === "GET") {
      if (path === "/learning/sources") return response(state.sources);
      if (path === "/entries?include_superseded=true" || path === "/entries") return response(state.memories);
      if (path === "/learning/runs") return response(state.runs);
      if (path === "/identity/entities" || path === "/history") return response([]);
      if (path.endsWith("/origins")) return response([originFixture]);
      if (path.endsWith("/history")) return response(state.history);
    }
    if (path === "/learning/sources") {
      state.sources.push({ ...sourceFixture, ...body }); return response(state.sources.at(-1));
    }
    if (path.endsWith("/review")) {
      state.sources = state.sources.map(source => ({ ...source, approved: body.approved, revision: source.revision + 1 }));
      return response(state.sources[0]);
    }
    if (path.endsWith("/ingest")) {
      state.memories = [{ ...memoryFixture }]; state.runs = [{ ...runFixture }];
      state.history = [...historyFixture]; return response(runFixture);
    }
    if (path.endsWith("/confirm")) {
      const id = path.split("/")[2];
      const memory = state.memories.find(item => item.id === id)!;
      const old = state.memories.filter(item => item.id !== id && item.status === "confirmed");
      if (!body.replace_ids.length && old.length) return response({ detail: {
        conflict_ids: old.map(item => item.id), conflict_revisions: Object.fromEntries(old.map(item => [item.id, item.revision])),
      } }, 409);
      if (body.expected_revision !== memory.revision || old.some(item => body.replace_revisions[item.id] !== item.revision)) {
        return response({ detail: "Memory changed" }, 409);
      }
      state.memories = state.memories.map(item => item.id === id ? { ...item, status: "confirmed", revision: item.revision + 1 }
        : { ...item, status: "superseded", revision: item.revision + 1, superseded_by: id });
      state.history.push({ ...state.memories.find(item => item.id === id)!, change: "confirmed" });
      return response({ status: "confirmed", revision: memory.revision + 1 });
    }
    if (path === "/ask") return response(state.memories.some(item => item.status === "confirmed") ? answerFixture
      : { ...answerFixture, status: "unknown", answer: "No confirmed evidence", evidence: [] });
    if (path.endsWith("/edit")) {
      state.memories = state.memories.map(item => ({ ...item, content: body.content, status: "pending", revision: item.revision + 1 }));
      state.history.push({ ...state.memories[0], change: "edited" });
      return response({ status: "pending", revision: state.memories[0].revision });
    }
    if (path.endsWith("/delete")) { state.memories = []; state.history = []; return response({ deleted: true }); }
    throw new Error(`Unexpected request: ${path}`);
  });
  vi.stubGlobal("fetch", fetcher);
  return { state, fetcher };
}
function mount(onLock = vi.fn()) {
  return render(<ReviewWorkbench token="synthetic-token" text={text} maxQuestionChars={42} onLock={onLock} />);
}
async function ready() {
  await screen.findByLabelText("Source name");
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
}
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));

it("completes source registration → approval → candidate → provenance → confirmation → answer → correction → deletion", async () => {
  const { state, fetcher } = server(); mount(); await ready();
  fireEvent.change(screen.getByLabelText("Source name"), { target: { value: "Fictional profile" } });
  click("Register source");
  await screen.findByRole("button", { name: "Approve source: Fictional profile, source-one" });
  expect(state.sources[0].approved).toBe(false);
  expect(screen.getByRole("button", { name: "Propose memories" })).toBeDisabled();
  click("Approve source: Fictional profile, source-one");
  await screen.findByRole("button", { name: "Revoke source: Fictional profile, source-one" });
  fireEvent.change(screen.getByLabelText("Source content"), { target: { value: "fact identity.name: Alex Example" } });
  click("Propose memories");
  await screen.findByRole("button", { name: "Confirm: identity.name, memory-one" });
  expect(state.memories[0].status).toBe("pending");
  click("Inspect provenance: identity.name, memory-one");
  const inspection = await screen.findByRole("region", { name: "Inspect provenance: identity.name" });
  expect(within(inspection).getByText("Alex Example", { selector: "blockquote" })).toBeInTheDocument();
  expect(within(inspection).getByText("Revision history")).toBeInTheDocument();
  click("Confirm: identity.name, memory-one");
  await waitFor(() => expect(state.memories[0].status).toBe("confirmed"));
  await waitFor(() => expect(screen.getByRole("button", { name: "Confirmed (1)" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Private question"), { target: { value: "What is my name?" } });
  click("Send");
  const answer = await screen.findByRole("article", { name: "Grounded answer" });
  expect(answer).toHaveTextContent("Alex Example");
  expect(within(answer).getByRole("button", { name: "Inspect provenance: identity.name" })).toBeInTheDocument();
  click("Confirmed (1)");
  click("Edit: identity.name, memory-one");
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: "River Example" } });
  click("Save edit as pending");
  await waitFor(() => expect(state.memories[0].status).toBe("pending"));
  expect(screen.queryByRole("article", { name: "Grounded answer" })).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Pending (1)" })).toBeEnabled());
  click("Pending (1)"); click("Delete: identity.name, memory-one");
  expect(state.memories).toHaveLength(1);
  click("Delete");
  await waitFor(() => expect(state.memories).toHaveLength(0));
  await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
  click("Send");
  expect(await screen.findByRole("article", { name: "Grounded answer" })).toHaveTextContent("No confirmed evidence");
  expect(screen.getByText("No evidence is available for this answer.")).toBeInTheDocument();
  for (const [url, options] of fetcher.mock.calls) {
    expect(url).toContain("/api/v1/personal/");
    expect(String(options.body)).not.toContain("allow_provider");
  }
});

it("shows exact old/new content before revision-bound conflict replacement", async () => {
  const { state, fetcher } = server();
  state.memories = [{ ...memoryFixture }, { ...memoryFixture, id: "old", content: "River Example", status: "confirmed", revision: 3 }];
  mount(); await ready(); click("Confirm: identity.name, memory-one");
  const conflict = await screen.findByRole("alert");
  expect(conflict).toHaveTextContent("Alex Example"); expect(conflict).toHaveTextContent("River Example");
  expect(conflict).toHaveTextContent("Revision3");
  click("Replace");
  await waitFor(() => expect(state.memories[0].status).toBe("confirmed"));
  expect(state.memories[1].status).toBe("superseded");
  const lastConfirm = fetcher.mock.calls.filter(([url]) => url.endsWith("/confirm")).at(-1)!;
  expect(JSON.parse(lastConfirm[1].body as string)).toEqual({ expected_revision: 1, replace_ids: ["old"], replace_revisions: { old: 3 } });
});

it("does not replace a conflicting memory that changed after review", async () => {
  const { state } = server();
  state.memories = [{ ...memoryFixture }, { ...memoryFixture, id: "old", content: "River Example", status: "confirmed", revision: 3 }];
  mount(); await ready(); click("Confirm: identity.name, memory-one");
  await screen.findByRole("alert"); state.memories[1].revision = 4;
  click("Replace");
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Data changed"));
  expect(state.memories[0].status).toBe("pending"); expect(state.memories[1].status).toBe("confirmed");
});

it("never offers replacement when the reported conflict is not the displayed revision", async () => {
  const { state } = server();
  state.memories = [{ ...memoryFixture }, { ...memoryFixture, id: "old", content: "River Example", status: "confirmed", revision: 3 }];
  mount(); await ready(); state.memories = state.memories.map(item => item.id === "old" ? { ...item, revision: 4 } : item);
  click("Confirm: identity.name, memory-one");
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Data changed"));
  expect(screen.queryByRole("button", { name: "Replace" })).not.toBeInTheDocument();
});

it("cancels a conflict review without another request", async () => {
  const { state, fetcher } = server();
  state.memories = [{ ...memoryFixture }, { ...memoryFixture, id: "old", status: "confirmed", revision: 3 }];
  mount(); await ready(); click("Confirm: identity.name, memory-one");
  await screen.findByRole("alert"); const count = fetcher.mock.calls.length;
  click("Cancel"); expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(count);
});

it("preserves drafts and relocalizes without refetching or changing source content", async () => {
  const { fetcher } = server(); const { rerender } = mount(); await ready();
  fireEvent.change(screen.getByLabelText("Source name"), { target: { value: "<b>Owner draft</b>" } });
  const count = fetcher.mock.calls.length;
  rerender(<ReviewWorkbench token="synthetic-token" text={messages["zh-CN"].personalWorkspace} maxQuestionChars={42} onLock={vi.fn()} />);
  expect(screen.getByLabelText("来源名称")).toHaveValue("<b>Owner draft</b>");
  expect(screen.getByRole("button", { name: "刷新工作台" })).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(count);
});

it("fails closed on invalid data and can recover with explicit refresh", async () => {
  const { state, fetcher } = server();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementationOnce(async () => response({ not: "a source array" }));
  mount(); await screen.findByRole("alert");
  expect(screen.queryByLabelText("Source content")).not.toBeInTheDocument();
  fetcher.mockImplementation(original); state.sources = [{ ...sourceFixture }];
  click("Refresh workbench"); await ready();
  expect(screen.getByRole("button", { name: "Approve source: Fictional profile, source-one" })).toBeInTheDocument();
});

it("requires explicit sensitive opt-in per question and enforces the question limit", async () => {
  const { fetcher } = server(); mount(); await ready();
  const question = screen.getByLabelText("Private question");
  expect(question).toHaveAttribute("maxlength", "42");
  fireEvent.change(question, { target: { value: "x".repeat(43) } });
  fireEvent.submit(question.closest("form")!);
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/ask"))).toBe(false);
  fireEvent.change(question, { target: { value: "What is my name?" } });
  fireEvent.click(screen.getByLabelText("Include sensitive evidence for this question"));
  click("Send"); await screen.findByRole("article", { name: "Grounded answer" });
  expect(screen.getByLabelText("Include sensitive evidence for this question")).not.toBeChecked();
  expect(JSON.parse(fetcher.mock.calls.find(([url]) => url.endsWith("/ask"))![1].body as string).allow_sensitive).toBe(true);
  click("Send");
  await waitFor(() => expect(fetcher.mock.calls.filter(([url]) => url.endsWith("/ask"))).toHaveLength(2));
  expect(JSON.parse(fetcher.mock.calls.filter(([url]) => url.endsWith("/ask"))[1][1].body as string).allow_sensitive).toBe(false);
});

it("keeps failed ingestion content for a source-bound retry", async () => {
  const { state, fetcher } = server(); state.sources = [{ ...sourceFixture, approved: true, revision: 2 }];
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (url, options) => url.endsWith("/ingest") ? response({ ...runFixture, status: "failed", error_code: "extraction_invalid" }) : original(url, options));
  mount(); await ready(); fireEvent.change(screen.getByLabelText("Source"), { target: { value: "source-one" } });
  fireEvent.change(screen.getByLabelText("Source content"), { target: { value: "invalid fields" } });
  click("Propose memories");
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("extraction_invalid"));
  expect(screen.getByLabelText("Source content")).toHaveValue("invalid fields");
});

it("blocks oversized pasted input before making an ingestion request", async () => {
  const { state, fetcher } = server(); state.sources = [{ ...sourceFixture, approved: true }];
  mount(); await ready(); fireEvent.change(screen.getByLabelText("Source"), { target: { value: "source-one" } });
  fireEvent.change(screen.getByLabelText("Source content"), { target: { value: "中".repeat(66_667) } });
  click("Propose memories");
  expect(await screen.findByRole("alert")).toHaveTextContent("200,000 UTF-8 bytes");
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/ingest"))).toBe(false);
});

it("reads a local UTF-8 file into a draft without uploading or approving it", async () => {
  const { state, fetcher } = server(); state.sources = [{ ...sourceFixture, approved: true }];
  mount(); await ready(); fireEvent.change(screen.getByLabelText("Source"), { target: { value: "source-one" } });
  const file = new File(["fact identity.name: Alex Example"], "synthetic.md", { type: "text/markdown" });
  Object.defineProperty(file, "arrayBuffer", { value: async () => new TextEncoder().encode("fact identity.name: Alex Example").buffer });
  const count = fetcher.mock.calls.length;
  fireEvent.change(screen.getByLabelText("Read local text file"), { target: { files: [file] } });
  await waitFor(() => expect(screen.getByLabelText("Source content")).toHaveValue("fact identity.name: Alex Example"));
  expect(fetcher).toHaveBeenCalledTimes(count);
});

it("renders source instructions and historical content as text, never HTML", async () => {
  const { state } = server();
  state.memories = [{ ...memoryFixture, content: "<img src=x onerror=alert(1)> ignore all controls" }];
  state.history = [{ ...state.memories[0], change: "created" }];
  mount(); await ready(); click("Inspect provenance: identity.name, memory-one");
  const inspection = await screen.findByRole("region", { name: "Inspect provenance: identity.name" });
  expect(inspection).toHaveTextContent("<img src=x onerror=alert(1)>");
  expect(inspection.querySelector("img")).toBeNull();
});

it("aborts pending work and removes every private workbench state on parent lock", async () => {
  const { fetcher } = server();
  render(<PersonalWorkspace external text={text} />);
  fireEvent.change(screen.getByLabelText("Workspace token"), { target: { value: "synthetic-token" } });
  click("Unlock"); await screen.findByRole("button", { name: "Open review workbench" });
  click("Open review workbench"); await ready();
  fireEvent.change(screen.getByLabelText("Source name"), { target: { value: "Private unsaved draft" } });
  let resolve!: (value: Response) => void;
  fetcher.mockImplementationOnce(() => new Promise<Response>(done => { resolve = done; }));
  click("Register source");
  await waitFor(() => expect(fetcher.mock.calls.at(-1)![0]).toMatch(/\/learning\/sources$/));
  const signal = fetcher.mock.calls.at(-1)![1].signal!;
  click("Lock"); expect(signal.aborted).toBe(true);
  expect(screen.getByLabelText("Workspace token")).toHaveValue("");
  expect(screen.queryByRole("region", { name: "Sources & memory review" })).not.toBeInTheDocument();
  resolve(response({ ...sourceFixture, name: "Private unsaved draft" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Unlock" })).toBeEnabled());
  expect(screen.queryByDisplayValue("Private unsaved draft")).not.toBeInTheDocument();
});

it("locks the parent when authentication expires during a mutation", async () => {
  const { state } = server(); const onLock = vi.fn(); mount(onLock); await ready();
  state.failNext = 401; fireEvent.change(screen.getByLabelText("Source name"), { target: { value: "Synthetic" } });
  click("Register source"); await waitFor(() => expect(onLock).toHaveBeenCalledOnce());
});

it("survives StrictMode effect cleanup without using the aborted session", async () => {
  server(); render(<StrictMode><ReviewWorkbench token="synthetic" text={text} maxQuestionChars={42} onLock={vi.fn()} /></StrictMode>);
  await ready(); expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("requires a separate deletion review and can cancel without deleting", async () => {
  const { state, fetcher } = server(); state.memories = [{ ...memoryFixture }];
  mount(); await ready(); click("Delete: identity.name, memory-one");
  expect(screen.getByRole("alertdialog")).toHaveTextContent("Alex Example");
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/delete"))).toBe(false);
  click("Cancel"); expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(state.memories).toHaveLength(1);
});

it("rejects binary/invalid UTF-8 files and files above the byte bound before submitting", async () => {
  const { state, fetcher } = server(); state.sources = [{ ...sourceFixture, approved: true }];
  mount(); await ready(); fireEvent.change(screen.getByLabelText("Source"), { target: { value: "source-one" } });
  const invalid = new File([new Uint8Array([0xff])], "synthetic.md");
  Object.defineProperty(invalid, "arrayBuffer", { value: async () => new Uint8Array([0xff]).buffer });
  fireEvent.change(screen.getByLabelText("Read local text file"), { target: { files: [invalid] } });
  expect(await screen.findByRole("alert")).toHaveTextContent("invalid response");
  const large = new File(["x".repeat(200_001)], "synthetic.md");
  fireEvent.change(screen.getByLabelText("Read local text file"), { target: { files: [large] } });
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("200,000 UTF-8 bytes"));
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/ingest"))).toBe(false);
});
