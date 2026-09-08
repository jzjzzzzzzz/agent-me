import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PersonalWorkspace } from "./PersonalWorkspace";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each([[42, 42], [undefined, 8000], [12000, 8000]])("enforces configured limit %s with an effective boundary of %s", async (configured, limit) => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify([]), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} maxQuestionChars={configured} />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "synthetic-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  const question = await screen.findByLabelText(/Private question/);
  expect(question).toHaveAttribute("maxlength", String(limit));
  const form = question.closest("form")!;
  fireEvent.change(question, { target: { value: "x".repeat(limit + 1) } });
  fireEvent.submit(form);
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(question).toHaveValue("x".repeat(limit + 1));
  fireEvent.change(question, { target: { value: "x".repeat(limit) } });
  fireEvent.submit(form);
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/chat"), expect.objectContaining({ body: JSON.stringify({ question: "x".repeat(limit) }) })));
  await waitFor(() => expect(question).toHaveValue(""));
});

it("preserves a draft when the limit shrinks and allows sending after shortening", async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify([]), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const { rerender } = render(<PersonalWorkspace external={false} maxQuestionChars={100} />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "synthetic-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  const question = await screen.findByLabelText(/Private question/);
  fireEvent.change(question, { target: { value: "x".repeat(43) } });
  rerender(<PersonalWorkspace external={false} maxQuestionChars={42} />);
  expect(question).toHaveValue("x".repeat(43));
  expect(screen.getByRole("button", { name: /Send/ })).toBeDisabled();
  fireEvent.submit(question.closest("form")!);
  expect(fetcher).toHaveBeenCalledTimes(2);
  fireEvent.change(question, { target: { value: "shortened question" } });
  expect(screen.getByRole("button", { name: /Send/ })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: /Send/ }));
  await waitFor(() => expect(question).toHaveValue(""));
});

it("requires a token, loads persisted memory, and clears private state on lock", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith("/entries") ? [{ id: "one", key: "identity.name", kind: "fact", content: "Alex Example", status: "confirmed", source: "manual", updated_at: "2026-01-01" }] : [{ id: "turn", role: "user", content: "Saved question" }],
  ), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} />);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "local-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  expect(await screen.findByText("Alex Example")).toBeInTheDocument();
  expect(screen.getByText("Saved question")).toBeInTheDocument();
  const options = (fetcher.mock.calls[0] as unknown as [string, RequestInit])[1];
  expect(options.headers).toMatchObject({ Authorization: "Bearer local-token" });
  fireEvent.click(screen.getByRole("button", { name: /Lock/ }));
  expect(screen.queryByText("Alex Example")).not.toBeInTheDocument();
  expect(screen.getByLabelText(/Workspace token/)).toHaveValue("");
});

it("does not expose the workspace after authentication failure", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Private workspace token required" }), { status: 401 })));
  render(<PersonalWorkspace external />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "bad" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Private workspace token required"));
  expect(screen.queryByRole("button", { name: /Send/ })).not.toBeInTheDocument();
});
