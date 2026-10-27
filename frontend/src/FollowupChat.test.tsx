import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";

beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem("agent-me-locale", "en");
  window.history.replaceState(null, "", "/");
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("sends successful turns with follow-ups, excludes failed turns, and resets a conversation", async () => {
  const requests: Array<{ question: string; history?: unknown[]; previous_sources?: unknown[] }> = [];
  const source = { title: "Figures", path: "figures.md", excerpt: "I use Matplotlib for paper figures.", score: 1 };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/api/v1/profile")) return new Response(JSON.stringify({
      name: "Synthetic twin", description: "Example", max_question_chars: 8000,
      max_history_chars: 24000, max_history_turn_chars: 8000, external_provider_enabled: true,
    }));
    requests.push(JSON.parse(String(init?.body)));
    if (requests.length === 2) return new Response(JSON.stringify({ detail: "Temporary failure" }), { status: 502 });
    return new Response(JSON.stringify({
      answer: requests.length === 1 ? "Matplotlib. [figures.md]" : `Successful answer ${requests.length}`,
      mode: "openai-compatible", sources: requests.length === 1 ? [source] : [],
    }));
  }));
  render(<App />);
  await screen.findByText("Synthetic twin");
  const input = screen.getByRole("textbox");
  fireEvent.change(input, { target: { value: "Which tool do I use?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("Matplotlib. [figures.md]");
  fireEvent.change(input, { target: { value: "Why did I choose it?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByRole("alert");
  expect(screen.getByText("Matplotlib. [figures.md]")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await screen.findByText("Successful answer 3");
  const expectedHistory = [
    { role: "user", content: "Which tool do I use?" },
    { role: "assistant", content: "Matplotlib. [figures.md]" },
  ];
  expect(requests[0]).toEqual({ question: "Which tool do I use?" });
  expect(requests[1].history).toEqual(expectedHistory);
  expect(requests[2].history).toEqual(expectedHistory);
  const expectedSources = [{ path: source.path, excerpt: source.excerpt }];
  expect(requests[1].previous_sources).toEqual(expectedSources);
  expect(requests[2].previous_sources).toEqual(expectedSources);
  fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
  expect(screen.queryByText("Matplotlib. [figures.md]")).not.toBeInTheDocument();
  fireEvent.change(input, { target: { value: "What tea do I prefer?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(requests).toHaveLength(4));
  expect(requests[3]).toEqual({ question: "What tea do I prefer?" });
  expect(Object.keys(window.localStorage)).toEqual(["agent-me-locale"]);
});
