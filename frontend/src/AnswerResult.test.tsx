import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnswerResult } from "./AnswerResult";
import type { ChatResponse, CollaborationResponse } from "./api";
import { messages } from "./i18n";

const text = messages.en;

const syntheticResultA: ChatResponse = {
  answer: "First synthetic answer.",
  mode: "extractive",
  sources: [
    { title: "First doc", path: "first.md", excerpt: "First excerpt.", score: 1 },
  ],
};

const syntheticResultB: ChatResponse = {
  answer: "Second synthetic answer.",
  mode: "openai-compatible",
  sources: [
    { title: "Second doc", path: "second.md", excerpt: "Second excerpt.", score: 0.8 },
  ],
};

const syntheticCollaboration: CollaborationResponse = {
  run_id: "run_synthetic_1234567890abcdef12345678",
  workflow: "planner-researcher-critic-writer",
  mode: "multi-agent-local",
  answer: "Collaboration answer.",
  grounded: true,
  sources: [
    { title: "Collab doc", path: "collab.md", excerpt: "Collab excerpt.", score: 0.9 },
  ],
  trace: [],
};

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("clears success clipboard feedback when the result changes", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  const { rerender } = render(<AnswerResult result={syntheticResultA} text={text} />);

  await userEvent.click(screen.getByRole("button", { name: text.copyAnswer }));
  expect(writeText).toHaveBeenCalledWith("First synthetic answer.");
  expect(await screen.findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);

  rerender(<AnswerResult result={syntheticResultB} text={text} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByText("Second synthetic answer.")).toBeInTheDocument();
});

it("clears failure clipboard feedback when the result changes", async () => {
  const writeText = vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError"));
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  const { rerender } = render(<AnswerResult result={syntheticResultA} text={text} />);

  await userEvent.click(screen.getByRole("button", { name: text.copyAnswer }));
  const status = await screen.findByRole("status");
  expect(status).toHaveTextContent(text.copyFailure);

  rerender(<AnswerResult result={syntheticResultB} text={text} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("clears sources copy feedback when the result changes", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  const { rerender } = render(<AnswerResult result={syntheticResultA} text={text} />);

  await userEvent.click(screen.getByRole("button", { name: text.copySources }));
  expect(writeText).toHaveBeenCalledWith("First doc — first.md");
  expect(await screen.findByRole("status")).toHaveTextContent(text.copySourcesSuccess);

  rerender(<AnswerResult result={syntheticResultB} text={text} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("preserves clipboard feedback when an unrelated parent rerender keeps the same result", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  const { rerender } = render(
    <AnswerResult result={syntheticResultA} text={text} headingLevel={2} />,
  );

  await userEvent.click(screen.getByRole("button", { name: text.copyAnswer }));
  expect(await screen.findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);

  // Rerender with the same result reference but changed heading level
  rerender(<AnswerResult result={syntheticResultA} text={text} headingLevel={3} />);
  expect(screen.getByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
  expect(screen.getByRole("heading", { name: text.answer, level: 3 })).toBeInTheDocument();
});

it("clears clipboard feedback when an equivalent new result replaces the current one", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  const { rerender } = render(<AnswerResult result={syntheticResultA} text={text} />);

  await userEvent.click(screen.getByRole("button", { name: text.copyAnswer }));
  expect(await screen.findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);

  rerender(
    <AnswerResult
      result={{
        ...syntheticResultA,
        sources: [...syntheticResultA.sources],
      }}
      text={text}
      headingLevel={3}
    />,
  );
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("maintains independent copy statuses across multiple AnswerResult instances", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  function MultiResult({ first, second }: { first: ChatResponse; second: CollaborationResponse }) {
    return (
      <div>
        <div data-testid="card-1">
          <AnswerResult result={first} text={text} headingLevel={3} />
        </div>
        <div data-testid="card-2">
          <AnswerResult result={second} text={text} headingLevel={4} />
        </div>
      </div>
    );
  }

  const { rerender } = render(
    <MultiResult first={syntheticResultA} second={syntheticCollaboration} />,
  );

  const card1 = screen.getByTestId("card-1");
  const card2 = screen.getByTestId("card-2");

  await userEvent.click(within(card1).getByRole("button", { name: text.copyAnswer }));
  expect(await within(card1).findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
  expect(within(card2).queryByRole("status")).not.toBeInTheDocument();

  await userEvent.click(within(card2).getByRole("button", { name: text.copyAnswer }));
  expect(await within(card2).findByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
  expect(within(card1).getByRole("status")).toHaveTextContent(text.copyAnswerSuccess);

  // Updating card 1 clears only card 1's status, leaving card 2 independent
  rerender(<MultiResult first={syntheticResultB} second={syntheticCollaboration} />);
  expect(within(card1).queryByRole("status")).not.toBeInTheDocument();
  expect(within(card2).getByRole("status")).toHaveTextContent(text.copyAnswerSuccess);
});

it("does not apply in-flight clipboard feedback to a replaced result", async () => {
  let resolveClipboard!: () => void;
  const writePromise = new Promise<void>((resolve) => {
    resolveClipboard = resolve;
  });
  const writeText = vi.fn().mockReturnValue(writePromise);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });

  const { rerender } = render(<AnswerResult result={syntheticResultA} text={text} />);

  // Trigger copy while writeText is unresolved
  await userEvent.click(screen.getByRole("button", { name: text.copyAnswer }));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();

  // Replace result before clipboard promise finishes
  rerender(<AnswerResult result={syntheticResultB} text={text} />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();

  // Complete the in-flight clipboard write
  resolveClipboard();
  await Promise.resolve();

  // The status must NOT be applied to resultB
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
