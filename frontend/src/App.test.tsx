import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

afterEach(cleanup);

const profileResponse = {
  ok: true,
  json: async () => ({
    name: "My Answer Agent",
    description: "A grounded question-answering agent built from your documents.",
    max_question_chars: 8000,
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
  vi.restoreAllMocks();
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

  expect(screen.getByRole("heading", { name: "用你掌控的知识构建问答 Agent。" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "提问" })).toBeDisabled();
  expect(document.documentElement.lang).toBe("zh-CN");
  expect(window.localStorage.getItem("agent-me-locale")).toBe("zh-CN");
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
      }),
    }),
  );

  render(<App />);

  expect(await screen.findByText("Documentation Helper")).toBeInTheDocument();
  expect(screen.getByText("Answers from reviewed documentation.")).toBeInTheDocument();
  expect(screen.getByLabelText(/ask the example/i)).toHaveAttribute("maxlength", "42");
  expect(screen.getByText(/0 \/ 42 characters/)).toBeInTheDocument();
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
  await userEvent.click(screen.getByRole("radio", { name: "Multi-agent lab" }));
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
      body: JSON.stringify({ question: "How should I plan?" }),
    }),
  );
});
