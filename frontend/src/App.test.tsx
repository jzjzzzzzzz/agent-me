import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "./App";

afterEach(cleanup);

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.lang = "en";
  vi.restoreAllMocks();
});

it("submits a question and renders grounded sources", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
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
