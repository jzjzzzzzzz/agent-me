import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";
import { downloadCollaborationRun } from "./exportRun";
import type { CollaborationResponse } from "./api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const profileResponse = {
  ok: true,
  json: async () => ({
    name: "My Answer Agent",
    description: "A grounded question-answering agent built from your documents.",
    max_question_chars: 8000,
    external_provider_enabled: false,
  }),
};

function routeFetch(chatResponse: object) {
  return vi.fn().mockImplementation((url: string) =>
    url.endsWith("/api/v1/profile")
      ? Promise.resolve(profileResponse)
      : Promise.resolve({ ok: true, json: async () => chatResponse }),
  );
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.lang = "en";
  document.title = "Agent-Me | An inspectable AI Twin";
  let description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
  if (!description) {
    description = document.createElement("meta");
    description.name = "description";
    document.head.append(description);
  }
  description.content = "Agent-Me — an open-source, auditable AI Twin built with memory, retrieval, multi-agent reasoning, and verification.";
  vi.restoreAllMocks();
});

it("sets useful localized metadata before the profile is available", () => {
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => undefined)));

  render(<App />);

  expect(document.documentElement.lang).toBe("en");
  expect(document.title).toBe(
    "OPEN-SOURCE AI AGENT TWIN | Distill yourself into an AI Agent Twin.",
  );
  expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
    "content",
    expect.stringContaining("AI Twin"),
  );
});

it("submits a question and renders grounded sources", async () => {
  vi.stubGlobal(
    "fetch",
    routeFetch({
      answer: "Start with user goals.",
      mode: "extractive",
      sources: [
        {
          title: "Example",
          path: "example.md",
          excerpt: "Start with user goals.",
          score: 1,
        },
      ],
    }),
  );

  render(<App />);
  await userEvent.type(screen.getByLabelText(/ask the example/i), "How do I plan?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(
    await screen.findByText("Start with user goals.", { selector: ".answer > p" }),
  ).toBeInTheDocument();
  expect(screen.getByText("example.md")).toBeInTheDocument();
});

it("switches locale, translates the interface, and remembers the choice", async () => {
  render(<App />);

  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Language" }), "zh-CN");

  expect(screen.getByRole("heading", { name: "检查可审计的 RAG 工作流。" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "提问" })).toBeDisabled();
  expect(document.documentElement.lang).toBe("zh-CN");
  expect(document.title).toContain("检查可审计的 RAG 工作流。");
  expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
    "content",
    expect.stringContaining("类型化交接"),
  );
  expect(window.localStorage.getItem("agent-me-locale")).toBe("zh-CN");
});

it("keeps localized metadata when profile loading fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

  render(<App />);
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Language" }), "fr");

  await waitFor(() => expect(document.documentElement.lang).toBe("fr"));
  expect(document.title).toContain("Créez un agent de réponse");
  expect(document.title.trim()).not.toBe("");
  expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
    "content",
    expect.stringContaining("Ajoutez des documents Markdown"),
  );
});


it("translates provider mode and explains an empty source list", async () => {
  vi.stubGlobal(
    "fetch",
    routeFetch({
      answer: "The supplied context is insufficient.",
      mode: "openai-compatible",
      sources: [],
    }),
  );

  render(<App />);
  await userEvent.type(screen.getByLabelText(/ask the example/i), "Unknown question");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(await screen.findByText("provider")).toBeInTheDocument();
  expect(screen.getByText("No matching source excerpts were found.")).toBeInTheDocument();
});

it("shows a structured API error and clears a stale answer while retrying", async () => {
  let rejectRequest: ((reason: Error) => void) | undefined;
  let chatCall = 0;
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.endsWith("/api/v1/profile")) return Promise.resolve(profileResponse);
    chatCall += 1;
    if (chatCall === 1) {
      return Promise.resolve({
        ok: true,
        json: async () => ({ answer: "Old answer", mode: "extractive", sources: [] }),
      });
    }
    return new Promise((_, reject) => {
      rejectRequest = reject;
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  const input = screen.getByLabelText(/ask the example/i);
  await userEvent.type(input, "First");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(await screen.findByText("Old answer", { selector: ".answer > p" })).toBeInTheDocument();

  await userEvent.clear(input);
  await userEvent.type(input, "Second");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  expect(screen.queryByText("Old answer")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled();

  rejectRequest?.(new Error("network"));
  expect(await screen.findByRole("alert")).toHaveTextContent("Request failed");
});


it("applies the configured public profile and question limit", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "Documentation Helper",
        description: "Answers from reviewed documentation.",
        max_question_chars: 42,
        external_provider_enabled: false,
      }),
    }),
  );

  render(<App />);

  expect(await screen.findByText("Documentation Helper")).toBeInTheDocument();
  expect(screen.getByText("Answers from reviewed documentation.")).toBeInTheDocument();
  expect(document.title).toContain("Documentation Helper");
  expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
    "content",
    "Answers from reviewed documentation.",
  );
  expect(screen.getByLabelText(/ask the example/i)).toHaveAttribute("maxlength", "42");
  expect(screen.getByText(/0 \/ 42 characters/)).toBeInTheDocument();
});

it("discloses external provider forwarding before question submission", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        name: "Provider-backed Agent",
        description: "Answers using a configured provider.",
        max_question_chars: 8000,
        external_provider_enabled: true,
      }),
    }),
  );

  render(<App />);

  expect(
    await screen.findByText(
      "Questions, recent conversation history, and retrieved context are forwarded to the configured model provider.",
    ),
  ).toBeInTheDocument();

  await userEvent.click(screen.getByRole("radio", { name: "Role-based multi-agent" }));
  expect(
    screen.getByText(
      "Questions are processed by this deployment and are not sent to an external model provider.",
    ),
  ).toBeInTheDocument();
});

it("uses a conservative disclosure when profile metadata is unavailable", () => {
  vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => undefined)));

  render(<App />);

  expect(
    screen.getByText(
      "External provider use is not confirmed. Questions may be forwarded to a configured provider.",
    ),
  ).toBeInTheDocument();
});

it("runs the multi-agent lab and renders its ordered operational trace", async () => {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.endsWith("/api/v1/profile")) return Promise.resolve(profileResponse);
    return Promise.resolve({
      ok: true,
      json: async () => ({
        run_id: `run_${"b".repeat(32)}`,
        workflow: "planner-researcher-critic-writer",
        mode: "multi-agent-local",
        answer: "Use evidence first.\n\nSources: [example.md]",
        grounded: true,
        sources: [
          {
            title: "Example",
            path: "example.md",
            excerpt: "Use evidence first.",
            score: 1,
          },
        ],
        trace: ["planner", "researcher", "critic", "writer"].map((agent, index) => ({
          sequence: index + 1,
          agent,
          outcome: "completed",
          summary: `${agent} completed its handoff.`,
          metrics: { artifact_count: 1 },
        })),
      }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  await userEvent.click(screen.getByRole("radio", { name: "Role-based multi-agent" }));
  await userEvent.type(screen.getByLabelText(/ask the example/i), "How should I plan?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(await screen.findByRole("heading", { name: "Collaboration trace" })).toBeInTheDocument();
  expect(screen.getByText("Grounded")).toBeInTheDocument();
  expect(screen.getByText("planner")).toBeInTheDocument();
  expect(screen.getByText(`run_${"b".repeat(32)}`)).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/collaborate"),
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ question: "How should I plan?", workflow: "baseline" }),
    }),
  );
});

it("runs verified collaboration and renders the verifier handoff", async () => {
  const fetchMock = vi.fn().mockImplementation((url: string) => {
    if (url.endsWith("/api/v1/profile")) return Promise.resolve(profileResponse);
    return Promise.resolve({
      ok: true,
      json: async () => ({
        run_id: `run_${"c".repeat(32)}`,
        workflow: "planner-researcher-critic-writer-verifier",
        mode: "multi-agent-local",
        answer: "Verified answer.\n\nSources: [example.md]",
        grounded: true,
        sources: [],
        trace: ["planner", "researcher", "critic", "writer", "verifier"].map(
          (agent, index) => ({
            sequence: index + 1,
            agent,
            outcome: "completed",
            summary: `${agent} completed its handoff.`,
            metrics: { approved: true },
          }),
        ),
      }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  render(<App />);
  await userEvent.click(screen.getByRole("radio", { name: "Verified multi-agent" }));
  await userEvent.type(screen.getByLabelText(/ask the example/i), "Verify this answer");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));

  expect(await screen.findByText("verifier")).toBeInTheDocument();
  expect(screen.getByText("verified multi-agent")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/collaborate"),
    expect.objectContaining({
      body: JSON.stringify({ question: "Verify this answer", workflow: "verified" }),
    }),
  );
});

it("copies the answer and sources as deterministic plain text", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  vi.stubGlobal(
    "fetch",
    routeFetch({
      answer: "Start with user goals.",
      mode: "extractive",
      sources: [
        { title: "First", path: "first.md", excerpt: "…", score: 1 },
        { title: "Second", path: "second.md", excerpt: "…", score: 0.5 },
      ],
    }),
  );

  render(<App />);
  await userEvent.type(screen.getByLabelText(/ask the example/i), "How do I plan?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("Start with user goals.", { selector: ".answer > p" });

  await userEvent.click(screen.getByRole("button", { name: "Copy answer" }));
  expect(writeText).toHaveBeenCalledWith("Start with user goals.");
  expect(await screen.findByRole("status")).toHaveTextContent("Answer copied to clipboard.");

  await userEvent.click(screen.getByRole("button", { name: "Copy sources" }));
  expect(writeText).toHaveBeenLastCalledWith("First — first.md\nSecond — second.md");
  expect(await screen.findByRole("status")).toHaveTextContent("Sources copied to clipboard.");
});

it("hides the copy sources control when there are no sources", async () => {
  vi.stubGlobal(
    "fetch",
    routeFetch({
      answer: "The supplied context is insufficient.",
      mode: "openai-compatible",
      sources: [],
    }),
  );

  render(<App />);
  await userEvent.type(screen.getByLabelText(/ask the example/i), "Unknown question");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("The supplied context is insufficient.", { selector: ".answer > p" });

  expect(screen.getByRole("button", { name: "Copy answer" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Copy sources" })).not.toBeInTheDocument();
});

it("shows a safe localized message when the clipboard write fails", async () => {
  const writeText = vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError"));
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  vi.stubGlobal(
    "fetch",
    routeFetch({
      answer: "Start with user goals.",
      mode: "extractive",
      sources: [],
    }),
  );

  render(<App />);
  await userEvent.type(screen.getByLabelText(/ask the example/i), "How do I plan?");
  await userEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("Start with user goals.", { selector: ".answer > p" });

  await userEvent.click(screen.getByRole("button", { name: "Copy answer" }));

  const status = await screen.findByRole("status");
  expect(status).toHaveTextContent("Copy failed. Select and copy the text manually.");
  expect(status.textContent).not.toMatch(/NotAllowedError|denied/);
});

it("exports only the validated collaboration response and revokes its object URL", () => {
  let blobParts: BlobPart[] = [];
  const createObjectURL = vi.fn(() => "blob:run");
  const revokeObjectURL = vi.fn();
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  vi.stubGlobal(
    "Blob",
    vi.fn((parts: BlobPart[]) => {
      blobParts = parts;
      return {};
    }),
  );
  vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });

  const result = {
    run_id: `run_${"d".repeat(32)}`,
    workflow: "planner-researcher-critic-writer",
    mode: "multi-agent-local",
    answer: "Public answer",
    grounded: true,
    sources: [],
    trace: [],
    question: "private submitted question",
    profile: { name: "private profile" },
  } as unknown as CollaborationResponse;

  downloadCollaborationRun(result);

  const exported = JSON.parse(String(blobParts[0])) as Record<string, unknown>;
  expect(Object.keys(exported)).toEqual([
    "run_id", "workflow", "mode", "answer", "grounded", "sources", "trace",
  ]);
  expect(exported).not.toHaveProperty("question");
  expect(exported).not.toHaveProperty("profile");
  expect(createObjectURL).toHaveBeenCalledTimes(1);
  expect(click).toHaveBeenCalledTimes(1);
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:run");
});
