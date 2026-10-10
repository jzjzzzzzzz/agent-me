import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { memoryFixture, runFixture, sourceFixture } from "./__fixtures__/review";
import { createPersonalClient, type SemanticReview } from "./personalApi";
import { messages } from "./i18n";
import { ReviewWorkbench } from "./ReviewWorkbench";

const GOLDEN_HASH = "f57379c19ac944f1bff9f4c24a9e123fde68f463191a1ac25cfa866be5d9bd81";
const digest = vi.fn(async () => Uint8Array.from(GOLDEN_HASH.match(/../g)!, byte => parseInt(byte, 16)).buffer);
const review: SemanticReview = { source_id: "source-one", source_revision: 2, selector: `learning-source/${"a".repeat(64)}`,
  target_id: "b".repeat(64), disclosure_revision: 2, permitted: true, configured: true, sensitivity: "private", max_source_chars: 1000 };
const source = { ...sourceFixture, approved: true, revision: 2 };
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function server(metadata = review, status = 200) {
  let ingested = false;
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    if (url.endsWith("/semantic-review")) return response(metadata);
    if (url.endsWith("/ingest-semantic")) {
      ingested = status === 200;
      return response(status === 200 ? { ...runFixture, mode: "notes", extractor: `model-literal-spans-v1/${metadata.target_id}` } : { detail: "Synthetic provider rejection" }, status);
    }
    if (url.endsWith("/learning/sources")) return response([source]);
    if (url.includes("/entries?")) return response(ingested ? [{ ...memoryFixture, confidence: null }] : []);
    if (url.endsWith("/learning/runs")) return response(ingested ? [{ ...runFixture, mode: "notes" }] : []);
    void options;
    return response([]);
  });
  vi.stubGlobal("fetch", fetcher); vi.stubGlobal("crypto", { subtle: { digest } });
  return fetcher;
}
async function open() {
  render(<ReviewWorkbench token="synthetic-token" text={messages.en.personalWorkspace} maxQuestionChars={8000} onLock={vi.fn()} />);
  await screen.findByLabelText("Source name");
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Source"), { target: { value: "source-one" } });
  fireEvent.change(screen.getByLabelText("Extraction mode"), { target: { value: "semantic" } });
  await screen.findByText(review.selector);
  await waitFor(() => expect(screen.getByRole("button", { name: "Refresh workbench" })).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Source content"), { target: { value: "My name is Alex Example." } });
}

it("does not call a model merely by selecting semantic mode, and binds an explicit attempt to exact text/target/revisions", async () => {
  const fetcher = server(); await open();
  const submit = screen.getByRole("button", { name: "Propose memories" }); expect(submit).toBeDisabled();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/ingest-semantic"))).toBe(false);
  fireEvent.click(screen.getByLabelText("Send this exact source text to the reviewed provider for this attempt"));
  expect(submit).toBeEnabled(); fireEvent.click(submit);
  await screen.findByRole("button", { name: "Confirm: identity.name, memory-one" });
  expect(screen.getByLabelText("Source content")).toHaveValue("My name is Alex Example.");
  expect(screen.getByLabelText("Send this exact source text to the reviewed provider for this attempt")).not.toBeChecked();
  const [, options] = fetcher.mock.calls.find(([url]) => url.endsWith("/ingest-semantic"))!;
  const body = JSON.parse(options.body as string);
  expect(body).toMatchObject({ content: "My name is Alex Example.", allow_provider: true, allow_sensitive: false,
    expected_source_revision: 2, expected_disclosure_revision: 2, reviewed_target_id: "b".repeat(64), mode: "notes" });
  expect(digest).toHaveBeenCalledWith("SHA-256", new TextEncoder().encode(body.content));
  expect(body.reviewed_content_hash).toBe(GOLDEN_HASH);
});

it.each([
  { ...review, configured: false, target_id: null, permitted: false }, { ...review, permitted: false },
])("leaves disclosure disabled when configuration/scope is missing %j", async metadata => {
  const fetcher = server(metadata); await open();
  expect(screen.getByLabelText("Send this exact source text to the reviewed provider for this attempt")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Propose memories" })).toBeDisabled();
  expect(fetcher.mock.calls.some(([url]) => url.endsWith("/ingest-semantic"))).toBe(false);
});

it("invalidates consent on content changes and separately requires sensitive-text opt-in", async () => {
  server({ ...review, sensitivity: "sensitive" }); await open();
  const consent = screen.getByLabelText("Send this exact source text to the reviewed provider for this attempt");
  fireEvent.click(consent); expect(screen.getByRole("button", { name: "Propose memories" })).toBeDisabled();
  fireEvent.click(screen.getByLabelText("Allow sensitive source text for this attempt"));
  expect(consent).not.toBeChecked(); fireEvent.click(consent);
  expect(screen.getByRole("button", { name: "Propose memories" })).toBeEnabled();
  fireEvent.change(screen.getByLabelText("Source content"), { target: { value: "Changed private text" } });
  expect(consent).not.toBeChecked();
});

it("resets consent after a failed delivery but preserves the source draft for an explicit retry", async () => {
  server(review, 502); await open();
  const consent = screen.getByLabelText("Send this exact source text to the reviewed provider for this attempt");
  fireEvent.click(consent); fireEvent.click(screen.getByRole("button", { name: "Propose memories" }));
  await screen.findByRole("alert"); expect(consent).not.toBeChecked();
  expect(screen.getByLabelText("Source content")).toHaveValue("My name is Alex Example.");
});

it("refuses stale/invalid review metadata and does not silently adopt a newer source revision", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...review, source_revision: 3 })));
  const client = createPersonalClient("synthetic", new AbortController().signal);
  await expect(client.semanticReview(source)).rejects.toMatchObject({ kind: "stale" });
});

it("bounds whole-source model context without truncating the draft", async () => {
  server({ ...review, max_source_chars: 5 }); await open();
  fireEvent.click(screen.getByLabelText("Send this exact source text to the reviewed provider for this attempt"));
  expect(screen.getByRole("button", { name: "Propose memories" })).toBeDisabled();
  expect(screen.getByLabelText("Source content")).toHaveValue("My name is Alex Example.");
  expect(within(screen.getByRole("region", { name: "Learning sources" })).getByText(/Maximum source codepoints/)).toBeInTheDocument();
});
